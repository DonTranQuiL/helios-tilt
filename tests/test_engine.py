"""Angle strategies."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.helios_tilt.engine import (
    PanelGeometry,
    annual_optimum,
    daily_optimum,
    is_night,
    round_to_step,
    seasonal_angle,
    tracking_target,
)
from custom_components.helios_tilt.solar import (
    SunPosition,
    best_angle,
    plane_irradiance,
    sun_position,
)

AMS = ZoneInfo("Europe/Amsterdam")
GEO = PanelGeometry(52.3676, 4.9041, 180.0, 0.0, 90.0)


def test_annual_optimum_amsterdam() -> None:
    """Clear-sky annual optimum is steeper than latitude minus a bit, below latitude."""
    angle = annual_optimum(GEO, 2026, AMS)
    assert 34 <= angle <= 45


def test_annual_optimum_respects_limits() -> None:
    """Never outside the soft limits."""
    geo = PanelGeometry(52.37, 4.9, 180.0, 0.0, 25.0)
    assert annual_optimum(geo, 2026, AMS) == 25.0


def test_daily_optimum_follows_season() -> None:
    """Flat in summer, steep in winter, equinox near latitude."""
    summer = daily_optimum(GEO, date(2026, 6, 21), AMS)
    winter = daily_optimum(GEO, date(2026, 12, 21), AMS)
    equinox = daily_optimum(GEO, date(2026, 3, 20), AMS)
    assert summer < equinox < winter
    assert summer <= 20
    assert winter >= 65
    assert 40 <= equinox <= 60


def test_daily_optimum_southern_hemisphere() -> None:
    """Sydney panels face north; June is winter there."""
    geo = PanelGeometry(-33.87, 151.21, 0.0, 0.0, 90.0)
    tz = ZoneInfo("Australia/Sydney")
    assert daily_optimum(geo, date(2026, 6, 21), tz) > daily_optimum(
        geo, date(2026, 12, 21), tz
    )


def test_seasonal_angle() -> None:
    """Winter angle at the winter solstice, summer angle at the summer solstice."""
    assert seasonal_angle(date(2026, 12, 21), 52, 60, 20, 50) == pytest.approx(
        60, abs=0.1
    )
    assert seasonal_angle(date(2026, 6, 21), 52, 60, 20, 50) == pytest.approx(
        20, abs=0.2
    )
    mid = seasonal_angle(date(2026, 3, 21), 52, 60, 20, 50)
    assert 35 < mid < 45
    # Weight leans the curve.
    assert seasonal_angle(date(2026, 3, 21), 52, 60, 20, 80) > mid
    assert seasonal_angle(date(2026, 3, 21), 52, 60, 20, 20) < mid
    assert seasonal_angle(date(2026, 3, 21), 52, 60, 20, 100) == pytest.approx(60)
    assert seasonal_angle(date(2026, 3, 21), 52, 60, 20, 0) == pytest.approx(20)
    # Southern hemisphere: June is winter.
    assert seasonal_angle(date(2026, 6, 21), -33, 60, 20, 50) == pytest.approx(
        60, abs=0.2
    )


def test_tracking_target_clamped() -> None:
    """Tracking follows the sun within the limits.

    It points a little flatter than straight at the sun (50 deg here), since
    tilting further loses more sky diffuse than it gains beam.
    """
    geo = PanelGeometry(52, 5, 180.0, 0.0, 60.0)
    assert 46.0 < tracking_target(geo, SunPosition(180.0, 40.0)) < 50.0
    assert tracking_target(geo, SunPosition(180.0, 10.0)) == 60.0
    roll = PanelGeometry(52, 5, 270.0, -45.0, 45.0)
    assert tracking_target(roll, SunPosition(90.0, 20.0)) == -45.0
    assert tracking_target(roll, SunPosition(180.0, 60.0)) == pytest.approx(
        0.0, abs=1e-6
    )


def test_round_to_step_with_hysteresis() -> None:
    """Rounds to the step; sticks to the current step near a boundary."""
    assert round_to_step(13.0, 5, None, 1) == 15
    assert round_to_step(12.4, 5, None, 1) == 10
    # Current 10: 13.4 is within 2.5 + 1 -> stay.
    assert round_to_step(13.4, 5, 10, 1) == 10
    assert round_to_step(13.6, 5, 10, 1) == 15
    # Falling back just under the boundary does not flip back.
    assert round_to_step(12.0, 5, 15, 1) == 15
    assert round_to_step(11.4, 5, 15, 1) == 10
    assert round_to_step(13.3, 0, 10, 1) == 13.3
    assert round_to_step(-12.6, 5, None, 0) == -15


def test_is_night() -> None:
    """Night below -1 degree."""
    assert is_night(SunPosition(0, -5))
    assert not is_night(SunPosition(0, 0))


# (latitude, longitude, azimuth, min, max): south- and north-facing racks in
# both hemispheres, east/west skewed racks and a single-axis (roll) tracker.
CLEAR_DAY_SITES = [
    (52.37, 4.9, 180.0, 0.0, 60.0),
    (52.37, 4.9, 180.0, 5.0, 65.0),
    (60.0, 10.0, 135.0, 0.0, 70.0),
    (40.0, -3.7, 225.0, 0.0, 60.0),
    (25.0, 55.0, 180.0, 0.0, 45.0),
    (0.5, 32.5, 180.0, 0.0, 30.0),
    (-33.9, 151.2, 0.0, 0.0, 60.0),
    (52.37, 4.9, 90.0, -60.0, 60.0),
]
CLEAR_DAYS = [
    date(2026, 1, 15),
    date(2026, 3, 20),
    date(2026, 6, 21),
    date(2026, 9, 12),
]
UTC_TZ = ZoneInfo("UTC")


def _clear_day(geo: PanelGeometry, day: date, angle_of, minutes: int = 10) -> float:
    """Clear-sky Wh/m2 over a day for an angle chosen per moment."""
    energy, when = 0.0, datetime.combine(day, time(0, 0), UTC_TZ)
    while when.date() == day:
        sun = sun_position(when, geo.latitude, geo.longitude)
        if sun.elevation > 0:
            energy += plane_irradiance(angle_of(sun), geo.azimuth, sun) * minutes / 60
        when += timedelta(minutes=minutes)
    return energy


def _stepped(geo: PanelGeometry, step: float = 5.0, hysteresis: float = 1.0):
    """Tracking as the controller does it: step, hysteresis and deadband."""
    held: list[float] = []

    def angle_of(sun: SunPosition) -> float:
        current = held[-1] if held else None
        angle = geo.clamp(
            round_to_step(tracking_target(geo, sun), step, current, hysteresis)
        )
        if current is not None and abs(angle - current) < 2.0:
            angle = current
        held.append(angle)
        return angle

    return angle_of


@pytest.mark.parametrize("site", CLEAR_DAY_SITES)
def test_tracking_and_daily_beat_fixed_on_a_clear_day(site) -> None:
    """Over a clear day neither tracking nor the daily angle loses to fixed."""
    geo = PanelGeometry(*site)
    fixed = annual_optimum(geo, 2026, UTC_TZ)
    fixed_stepped = geo.clamp(round(fixed / 5.0) * 5.0)
    for day in CLEAR_DAYS:
        ref = _clear_day(geo, day, lambda _sun: fixed)
        if ref <= 0:
            continue
        tracking = _clear_day(geo, day, lambda sun: tracking_target(geo, sun))
        best_today = daily_optimum(geo, day, UTC_TZ)
        daily = _clear_day(geo, day, lambda _sun, a=best_today: a)
        assert tracking >= ref * (1 - 1e-9), (site, day)
        assert daily >= ref * (1 - 1e-3), (site, day)  # 10 min vs 30 min samples
        # With 5 deg steps both sides are rounded; the stepped tracker may only
        # trail by the rounding (a few tenths of a percent at most).
        ref_stepped = _clear_day(geo, day, lambda _sun: fixed_stepped)
        stepped = _clear_day(geo, day, _stepped(geo))
        assert stepped >= ref_stepped * (1 - 0.003), (site, day)


@pytest.mark.parametrize(
    "sun", [SunPosition(180, 40), SunPosition(110, 12), SunPosition(250, 25)]
)
@pytest.mark.parametrize("azimuth", [180.0, 135.0, 90.0])
def test_best_angle_maximises_irradiance(sun, azimuth) -> None:
    """The closed form matches a brute-force search over the angle."""
    best = best_angle(azimuth, sun)
    brute = max(
        (a / 10 for a in range(-900, 901)),
        key=lambda a: plane_irradiance(a, azimuth, sun),
    )
    assert best == pytest.approx(brute, abs=0.11)
