"""Weather safety: wind stow, storm latch, snow/rain/frost, stale data.

Pure state machine (no Home Assistant imports). Feed it a `Readings` every
tick and on every relevant state change; it returns a `SafetyState`.
Priority inside: storm > wind > no data > snow > rain > frost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

# States, most to least severe.
STORM = "storm"
WIND = "wind"
STARTUP = "startup"  # no valid data yet since start: don't move
STALE = "stale"  # data went missing: freeze (unless already stowed)
SNOW = "snow"
RAIN = "rain"
FROST = "frost"
OK = "ok"

STOWING = (STORM, WIND)
# storm_until value meaning "until cleared by hand" (timezone-aware, so it
# compares cleanly with real timestamps).
UNTIL_CLEARED = datetime.max.replace(tzinfo=UTC)
FROZEN = (STARTUP, STALE)

SNOW_CONDITIONS = {"snowy", "snowy-rainy"}
HEAVY_RAIN_CONDITIONS = {"pouring", "lightning-rainy", "hail"}


@dataclass(slots=True)
class SafetySettings:
    """Thresholds (wind in km/h)."""

    wind_stow: float = 50.0
    wind_resume: float = 35.0
    calm_minutes: float = 10.0
    storm_speed: float = 75.0
    storm_hold_hours: float = 6.0  # 0 = clear by hand only
    stale_minutes: float = 120.0
    snow: bool = True
    rain: bool = False
    frost: bool = False
    frost_temperature: float = -2.0
    wind_required: bool = True  # a wind source is configured


@dataclass(slots=True)
class Readings:
    """What the weather sources say right now. None = unknown."""

    wind: float | None = None  # km/h, max of all sources
    wind_age: timedelta | None = None  # age of the freshest wind reading
    condition: str | None = None
    temperature: float | None = None  # degC
    cloud: float | None = None  # %


@dataclass(slots=True)
class SafetyState:
    """Outcome for one evaluation."""

    state: str
    detail: str = ""

    @property
    def stow(self) -> bool:
        """Panels must go to their stow angle."""
        return self.state in STOWING

    @property
    def frozen(self) -> bool:
        """Panels must not move at all."""
        return self.state in FROZEN


@dataclass(slots=True)
class SafetyEngine:
    """Remembers what it needs between evaluations (latches, timers)."""

    settings: SafetySettings
    wind_stowed: bool = False
    calm_since: datetime | None = None
    storm_until: datetime | None = None  # UNTIL_CLEARED = by hand only
    last_wind: float | None = None
    had_valid_data: bool = False
    last: SafetyState = field(default_factory=lambda: SafetyState(STARTUP))

    # ---- commands --------------------------------------------------------

    def latch_storm(self, now: datetime, hours: float | None = None) -> None:
        """Enter storm mode (also used by the stow action)."""
        hold = self.settings.storm_hold_hours if hours is None else hours
        self.storm_until = UNTIL_CLEARED if hold <= 0 else now + timedelta(hours=hold)

    def clear_storm(self) -> None:
        """Leave storm mode by hand. Wind stow still applies if it is windy."""
        self.storm_until = None

    @property
    def storm(self) -> bool:
        """Storm latch active."""
        return self.storm_until is not None

    # ---- evaluation ------------------------------------------------------

    def evaluate(self, now: datetime, readings: Readings) -> SafetyState:
        """Update the latches and return the current safety state."""
        s = self.settings
        wind_valid = readings.wind is not None and (
            readings.wind_age is None
            or readings.wind_age <= timedelta(minutes=s.stale_minutes)
        )

        if wind_valid:
            wind = float(readings.wind)  # type: ignore[arg-type]
            self.last_wind = wind
            self.had_valid_data = True
            if wind >= s.storm_speed:
                self.latch_storm(now)
            if wind >= s.wind_stow:
                self.wind_stowed = True
                self.calm_since = None
            elif self.wind_stowed:
                if wind <= s.wind_resume:
                    self.calm_since = self.calm_since or now
                    if now - self.calm_since >= timedelta(minutes=s.calm_minutes):
                        self.wind_stowed = False
                        self.calm_since = None
                else:
                    self.calm_since = None
        elif not s.wind_required:
            self.had_valid_data = True

        if self.storm_until is not None and self.storm_until != UNTIL_CLEARED:
            # The hold timer runs from the last stormy reading.
            if (
                wind_valid
                and self.last_wind is not None
                and self.last_wind >= s.wind_stow
            ):
                self.storm_until = max(
                    self.storm_until, now + timedelta(hours=s.storm_hold_hours)
                )
            if now >= self.storm_until:
                self.storm_until = None

        self.last = self._state(now, readings, wind_valid)
        return self.last

    def _state(self, now: datetime, r: Readings, wind_valid: bool) -> SafetyState:
        s = self.settings
        if self.storm:
            return SafetyState(STORM, self._wind_text())
        if self.wind_stowed:
            if wind_valid and self.calm_since is not None:
                left = timedelta(minutes=s.calm_minutes) - (now - self.calm_since)
                return SafetyState(
                    WIND,
                    f"{self._wind_text()}, calm for {max(0, int(left.total_seconds() // 60))} more min",
                )
            return SafetyState(WIND, self._wind_text())
        if s.wind_required and not wind_valid:
            if not self.had_valid_data:
                return SafetyState(STARTUP, "waiting for wind data")
            return SafetyState(STALE, "wind data missing or stale")
        condition = (r.condition or "").lower()
        if s.snow and condition in SNOW_CONDITIONS:
            return SafetyState(SNOW, condition)
        if s.rain and condition in HEAVY_RAIN_CONDITIONS:
            return SafetyState(RAIN, condition)
        if (
            s.frost
            and r.temperature is not None
            and r.temperature <= s.frost_temperature
        ):
            return SafetyState(FROST, f"{r.temperature:g} \u00b0C")
        return SafetyState(OK)

    def _wind_text(self) -> str:
        if self.last_wind is None:
            return "storm mode"
        return f"wind {self.last_wind:.0f} km/h"
