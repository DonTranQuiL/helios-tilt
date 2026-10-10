"""Safety state machine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.helios_tilt.safety import (
    FROST,
    OK,
    RAIN,
    SNOW,
    STALE,
    STARTUP,
    STORM,
    TRIGGER,
    UNTIL_CLEARED,
    WIND,
    Readings,
    SafetyEngine,
    SafetySettings,
)

T0 = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)


def engine(**kwargs) -> SafetyEngine:
    return SafetyEngine(SafetySettings(**kwargs))


def wind(speed: float | None, age: float = 0, **kwargs) -> Readings:
    return Readings(
        wind=speed,
        wind_age=None if speed is None else timedelta(minutes=age),
        **kwargs,
    )


def test_startup_until_data() -> None:
    """No valid wind yet: frozen in startup."""
    e = engine()
    s = e.evaluate(T0, wind(None))
    assert s.state == STARTUP and s.frozen and not s.stow
    assert e.evaluate(T0, wind(10)).state == OK


def test_wind_stow_and_calm_resume() -> None:
    """Stow at the threshold, resume only after the calm period below the resume speed."""
    e = engine(wind_stow=50, wind_resume=35, calm_minutes=10)
    assert e.evaluate(T0, wind(49)).state == OK
    s = e.evaluate(T0, wind(50))
    assert s.state == WIND and s.stow
    # Between resume and stow: stays stowed, no calm timer.
    assert e.evaluate(T0 + timedelta(minutes=1), wind(40)).state == WIND
    assert e.calm_since is None
    # Below resume: timer starts.
    s = e.evaluate(T0 + timedelta(minutes=2), wind(30))
    assert s.state == WIND and "10 more min" in s.detail
    # A gust resets the timer.
    e.evaluate(T0 + timedelta(minutes=5), wind(38))
    assert e.calm_since is None
    e.evaluate(T0 + timedelta(minutes=6), wind(20))
    assert e.evaluate(T0 + timedelta(minutes=15), wind(20)).state == WIND
    assert e.evaluate(T0 + timedelta(minutes=16), wind(20)).state == OK


def test_storm_latch_hold_and_clear() -> None:
    """Storm speed latches storm mode for the hold time after the last strong wind."""
    e = engine(storm_speed=75, storm_hold_hours=6, calm_minutes=0)
    assert e.evaluate(T0, wind(80)).state == STORM
    assert e.storm
    # Calm again: still storm for 6 h.
    assert e.evaluate(T0 + timedelta(hours=1), wind(5)).state == STORM
    # Strong (stow-level) wind extends the hold.
    e.evaluate(T0 + timedelta(hours=5), wind(55))
    assert e.evaluate(T0 + timedelta(hours=10), wind(5)).state == STORM
    assert e.evaluate(T0 + timedelta(hours=11, minutes=1), wind(5)).state == OK
    # Manual clear.
    e.evaluate(T0 + timedelta(hours=12), wind(90))
    e.clear_storm()
    # Wind stow still applies while it blows.
    assert e.evaluate(T0 + timedelta(hours=12), wind(60)).state == WIND


def test_storm_by_hand_only() -> None:
    """Hold 0: storm stays until cleared."""
    e = engine(storm_hold_hours=0)
    e.latch_storm(T0)
    assert e.storm_until == UNTIL_CLEARED
    assert e.evaluate(T0 + timedelta(days=30), wind(0)).state == STORM
    e.clear_storm()
    assert e.evaluate(T0 + timedelta(days=30), wind(0)).state == OK


def test_stale_freezes_but_stays_stowed() -> None:
    """Missing or old data: freeze; but never leave a wind stow without data."""
    e = engine(stale_minutes=60)
    e.evaluate(T0, wind(10))
    assert e.evaluate(T0, wind(10, age=61)).state == STALE
    assert e.evaluate(T0, wind(None)).state == STALE
    e.evaluate(T0, wind(60))
    s = e.evaluate(T0 + timedelta(hours=2), wind(None))
    assert s.state == WIND and s.stow


def test_no_wind_source_configured() -> None:
    """Without a wind source nothing freezes (the config flow requires one anyway)."""
    e = engine(wind_required=False)
    assert e.evaluate(T0, wind(None)).state == OK


def test_snow_rain_frost() -> None:
    """Weather positions, in priority order, each switchable."""
    e = engine(snow=True, rain=True, frost=True, frost_temperature=-2)
    assert e.evaluate(T0, wind(5, condition="snowy")).state == SNOW
    assert e.evaluate(T0, wind(5, condition="pouring")).state == RAIN
    assert e.evaluate(T0, wind(5, condition="cloudy", temperature=-3)).state == FROST
    assert e.evaluate(T0, wind(5, condition="cloudy", temperature=-1)).state == OK
    # Wind beats snow.
    assert e.evaluate(T0, wind(60, condition="snowy")).state == WIND
    off = engine(snow=False, rain=False, frost=False)
    assert off.evaluate(T0, wind(5, condition="snowy", temperature=-10)).state == OK


def test_trigger_priority() -> None:
    """Triggers stow after wind/storm, before missing data and weather."""
    e = engine(rain=True)
    s = e.evaluate(T0, wind(None, triggers=["Party", "Hail"]))
    assert (s.state, s.detail, s.stow) == (TRIGGER, "Party, Hail", True)
    s = e.evaluate(T0, wind(60, triggers=["Party"]))
    assert s.state == WIND
    s = e.evaluate(T0, wind(80, triggers=["Party"]))
    assert s.state == STORM


def test_dedicated_sensors_override_condition() -> None:
    e = engine(rain=True)
    assert e.evaluate(T0, wind(5, condition="sunny", rain=True)).state == RAIN
    assert e.evaluate(T0, wind(5, condition="pouring", rain=False)).state == OK
    assert e.evaluate(T0, wind(5, condition="pouring", rain=None)).state == RAIN
    assert e.evaluate(T0, wind(5, condition="sunny", snow=True)).state == SNOW
    assert e.evaluate(T0, wind(5, condition="snowy", snow=False)).state == OK


def test_without_wind() -> None:
    """The direction rule's view: wind ignored, storm and the rest kept."""
    e = engine()
    assert e.evaluate(T0, wind(60, condition="snowy")).state == WIND
    assert e.without_wind(T0, wind(60, condition="snowy")).state == SNOW
    assert e.evaluate(T0, wind(80)).state == STORM
    assert e.without_wind(T0, wind(80)).state == STORM
