"""Angle strategies: which tilt a panel should have, and when to move.

Pure Python (no Home Assistant imports) so it is easy to test and reason
about. Times are timezone-aware datetimes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from functools import lru_cache

from .solar import SunPosition, best_angle, plane_irradiance, sun_position

NIGHT_ELEVATION = -1.0  # sun below this: night park
DAY_STEP = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class PanelGeometry:
    """What the engine needs to know about one panel."""

    latitude: float
    longitude: float
    azimuth: float
    min_angle: float
    max_angle: float

    def clamp(self, angle: float) -> float:
        """Keep an angle inside the soft limits."""
        return max(self.min_angle, min(self.max_angle, angle))

    def candidates(self) -> list[float]:
        """Whole-degree angles within the limits."""
        lo, hi = math.ceil(self.min_angle), math.floor(self.max_angle)
        return [float(a) for a in range(lo, hi + 1)] or [self.min_angle]


def _day_samples(
    geo: PanelGeometry, day: date, tz: tzinfo, step: timedelta = DAY_STEP
) -> list[SunPosition]:
    """Sun positions above the horizon over a local day."""
    start = datetime.combine(day, time(0, 0), tz)
    samples = []
    when = start
    while when < start + timedelta(days=1):
        sun = sun_position(when, geo.latitude, geo.longitude)
        if sun.elevation > 0:
            samples.append(sun)
        when += step
    return samples


def _best_angle(geo: PanelGeometry, samples: list[SunPosition]) -> float:
    """Angle with the most clear-sky energy over the samples."""
    if not samples:
        return geo.clamp(0.0)
    best, best_energy = geo.candidates()[0], -1.0
    for angle in geo.candidates():
        energy = sum(plane_irradiance(angle, geo.azimuth, s) for s in samples)
        if energy > best_energy + 1e-9:
            best, best_energy = angle, energy
    return best


@lru_cache(maxsize=64)
def daily_optimum(geo: PanelGeometry, day: date, tz: tzinfo) -> float:
    """One angle for the whole day that collects the most clear-sky energy."""
    return _best_angle(geo, _day_samples(geo, day, tz))


@lru_cache(maxsize=16)
def annual_optimum(geo: PanelGeometry, year: int, tz: tzinfo) -> float:
    """The best fixed angle for the year (clear-sky, irradiance weighted).

    Samples 24 days spread over the year every 30 minutes; plenty for a
    whole-degree answer. Takes a few hundred milliseconds: call it in the
    executor.
    """
    samples: list[SunPosition] = []
    for i in range(24):
        day = date(year, 1, 1) + timedelta(days=int(i * 365 / 24) + 7)
        samples.extend(_day_samples(geo, day, tz, timedelta(minutes=30)))
    return _best_angle(geo, samples)


def seasonal_angle(
    day: date, latitude: float, winter: float, summer: float, weight: float
) -> float:
    """Smooth cosine curve between the winter and summer angle.

    `weight` (0..100) leans the curve: 50 is the plain cosine, higher keeps
    the panel at the winter angle longer, lower at the summer angle.
    """
    # 1.0 at the winter solstice, 0.0 at the summer solstice.
    winter_day = 355 if latitude >= 0 else 172
    doy = day.timetuple().tm_yday
    f = (1.0 + math.cos(2.0 * math.pi * (doy - winter_day) / 365.25)) / 2.0
    w = max(0.0, min(100.0, weight)) / 100.0
    f = f * (2.0 * w) if w < 0.5 else f + (1.0 - f) * (2.0 * w - 1.0)
    return summer + (winter - summer) * max(0.0, min(1.0, f))


def tracking_target(geo: PanelGeometry, sun: SunPosition) -> float:
    """Follow the sun within the limits (most clear-sky irradiance)."""
    return geo.clamp(best_angle(geo.azimuth, sun))


def round_to_step(
    raw: float, step: float, current: float | None, hysteresis: float
) -> float:
    """Round to the step, but keep `current` while `raw` stays near it.

    `current` is kept as long as `raw` is within half a step plus the
    hysteresis, so a value sitting on a rounding boundary does not make the
    panel move back and forth.
    """
    if step <= 0:
        return raw
    if current is not None and abs(raw - current) <= step / 2.0 + hysteresis:
        return current
    return round(raw / step) * step


@dataclass(slots=True)
class Plan:
    """The engine's answer for one moment."""

    angle: float
    reason: str  # strategy | night | diffuse


def is_night(sun: SunPosition) -> bool:
    """Sun below the horizon (with a small margin)."""
    return sun.elevation < NIGHT_ELEVATION
