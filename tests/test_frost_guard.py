"""Frost guard: park once, lock, thaw, announcements, and the snow remover."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_get_persistent_notifications,
)

from custom_components.helios_tilt.const import (
    DOMAIN,
    EVENT_FROST_LOCK,
    EVENT_FROST_SENSOR,
    EVENT_FROST_SENSOR_RECOVERED,
    EVENT_SNOW_REMOVER,
    EVENT_SNOW_REMOVER_REFUSED,
)
from custom_components.helios_tilt.frost_guard import FrostGuard, FrostGuardSettings

from .test_controller import TARGET, advance, attr

FROST_LOCK = "binary_sensor.panel_1_frost_lock"
WEATHER = "sensor.panel_1_weather"
SNOW_BTN = "button.panel_1_snow_remover"
OUTSIDE = "sensor.outside"
T0 = datetime(2026, 6, 21, 10, 0, tzinfo=UTC)

GUARD_OPTS = {
    "frost_guard": True,
    "frost_guard_park_temperature": 1.0,
    "frost_guard_unlock_temperature": 2.0,
    "frost_guard_unlock_hold": 45,
    "frost_guard_angle": 20,
    "frost_guard_allow_storm": True,
    "temperature_sensor": OUTSIDE,
}


def _guard(**kwargs: object) -> FrostGuard:
    return FrostGuard(FrostGuardSettings(**kwargs))


def test_park_once_then_lock() -> None:
    g = _guard(enabled=True)
    first = g.evaluate(T0, 1.0)
    assert first.locked and first.should_park and first.locked_since == T0
    second = g.evaluate(T0 + timedelta(minutes=1), 0.5)
    assert second.locked and not second.should_park


def test_no_chatter_between_park_and_unlock() -> None:
    """1.0 locks; 1.5 is still below unlock 2.0, so no unlock and no second park."""
    g = _guard(enabled=True)
    g.evaluate(T0, 1.0)
    later = g.evaluate(T0 + timedelta(hours=1), 1.5)
    assert later.locked and not later.should_park and later.above_since is None


def test_unlock_only_after_hold() -> None:
    g = _guard(enabled=True)
    g.evaluate(T0, 0.0)
    mid = g.evaluate(T0 + timedelta(minutes=10), 3.0)
    assert mid.locked and mid.unlock_eta == T0 + timedelta(minutes=55)
    early = g.evaluate(T0 + timedelta(minutes=54), 3.0)
    assert early.locked
    done = g.evaluate(T0 + timedelta(minutes=55), 3.0)
    assert not done.locked and not done.should_park


def test_thaw_timer_resets_if_it_drops_again() -> None:
    g = _guard(enabled=True)
    g.evaluate(T0, 0.0)
    g.evaluate(T0 + timedelta(minutes=1), 3.0)
    g.evaluate(T0 + timedelta(minutes=30), 1.5)
    again = g.evaluate(T0 + timedelta(minutes=31), 3.0)
    assert again.locked
    assert again.above_since == T0 + timedelta(minutes=31)


def test_missing_temperature_keeps_the_lock() -> None:
    g = _guard(enabled=True)
    g.evaluate(T0, 0.0)
    missing = g.evaluate(T0 + timedelta(minutes=10), None)
    assert missing.locked and missing.above_since is None
    # A later warm reading starts the thaw timer from that moment, not from
    # the gap.
    warm = g.evaluate(T0 + timedelta(minutes=11), 5.0)
    assert warm.locked and warm.above_since == T0 + timedelta(minutes=11)


def test_disabled_clears_the_lock() -> None:
    g = _guard(enabled=True)
    g.evaluate(T0, 0.0)
    g.settings.enabled = False
    assert not g.evaluate(T0 + timedelta(minutes=1), 0.0).locked


def test_restore_does_not_repark() -> None:
    g = _guard(enabled=True)
    g.evaluate(T0, 0.0)
    data = g.store_data()
    other = _guard(enabled=True)
    other.restore(data)
    status = other.evaluate(T0 + timedelta(minutes=5), 0.0)
    assert status.locked and not status.should_park


# ---- Home Assistant ----------------------------------------------------------


def _set_temp(hass: HomeAssistant, value: float | str, unit: str = "°C") -> None:
    hass.states.async_set(
        OUTSIDE,
        value,
        {"unit_of_measurement": unit, "device_class": "temperature"},
    )


async def test_parks_once_and_exposes_sensors(
    hass: HomeAssistant, setup_site, cover, weather
) -> None:
    _set_temp(hass, 8)
    await setup_site(options=GUARD_OPTS)
    assert cover.positions == [25]  # daily optimum, not yet cold
    assert hass.states.get(FROST_LOCK).state == "off"
    assert hass.states.get(WEATHER).state == "sunny"
    assert attr(hass, WEATHER, "weather_entity") == "weather.home"
    assert attr(hass, WEATHER, "cloud_coverage") == 20
    assert attr(hass, WEATHER, "cloud_threshold") == 80
    _set_temp(hass, 1)
    await hass.async_block_till_done()
    assert hass.states.get(FROST_LOCK).state == "on"
    assert cover.positions == [25, 33]  # 20° of 0–60 is 33%
    assert attr(hass, TARGET, "reason") == "frost_lock"
    assert hass.states.get("sensor.panel_1_last_move").state == "frost_lock"
    assert attr(hass, FROST_LOCK, "park_temperature") == 1.0
    assert attr(hass, FROST_LOCK, "unlock_temperature") == 2.0
    assert attr(hass, FROST_LOCK, "temperature_sensor") == OUTSIDE
    assert attr(hass, FROST_LOCK, "locked_since") is not None
    # Still at 0.5 °C: no second move.
    _set_temp(hass, 0.5)
    await hass.async_block_till_done()
    assert cover.positions == [25, 33]
    assert hass.states.get(FROST_LOCK).state == "on"


async def test_mode_change_and_night_park_are_locked(
    hass: HomeAssistant, setup_site, cover, freezer
) -> None:
    _set_temp(hass, 8)
    await setup_site(options=GUARD_OPTS)
    _set_temp(hass, 0)
    await hass.async_block_till_done()
    parked = list(cover.positions)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.panel_1_mode", "option": "tracking"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert cover.positions == parked
    assert attr(hass, TARGET, "reason") == "frost_lock"
    # Night, still locked: no night park move.
    freezer.move_to("2026-06-21 22:00:00+00:00")
    await advance(hass, freezer, 1)
    assert cover.positions == parked
    assert attr(hass, TARGET, "reason") == "frost_lock"


async def test_storm_exception_allowed(
    hass: HomeAssistant, setup_site, cover, weather
) -> None:
    _set_temp(hass, 8)
    await setup_site(options=GUARD_OPTS)
    _set_temp(hass, 0)
    await hass.async_block_till_done()
    parked = list(cover.positions)
    weather(wind_speed=90, wind_gust_speed=100)
    await hass.async_block_till_done()
    assert cover.positions == parked + [0]  # stow angle 0
    assert attr(hass, TARGET, "reason") == "storm"


async def test_storm_exception_off(
    hass: HomeAssistant, setup_site, cover, weather
) -> None:
    _set_temp(hass, 8)
    await setup_site(options={**GUARD_OPTS, "frost_guard_allow_storm": False})
    _set_temp(hass, 0)
    await hass.async_block_till_done()
    parked = list(cover.positions)
    weather(wind_speed=90, wind_gust_speed=100)
    await hass.async_block_till_done()
    assert cover.positions == parked
    assert attr(hass, TARGET, "reason") == "frost_lock"


async def test_unlock_timing(hass: HomeAssistant, setup_site, cover, freezer) -> None:
    _set_temp(hass, 8)
    await setup_site(options=GUARD_OPTS)
    _set_temp(hass, 0)
    await hass.async_block_till_done()
    parked = list(cover.positions)
    _set_temp(hass, 3)
    await hass.async_block_till_done()
    assert hass.states.get(FROST_LOCK).state == "on"
    await advance(hass, freezer, 44)
    assert hass.states.get(FROST_LOCK).state == "on"
    assert cover.positions == parked
    await advance(hass, freezer, 2)
    assert hass.states.get(FROST_LOCK).state == "off"
    # Automatic control may move again (daily optimum).
    assert cover.positions != parked or attr(hass, TARGET, "reason") != "frost_lock"
    assert attr(hass, TARGET, "reason") != "frost_lock"


async def test_unavailable_temp_stays_locked_and_announces(
    hass: HomeAssistant, setup_site, cover
) -> None:
    _set_temp(hass, 8)
    unavailable = async_capture_events(hass, EVENT_FROST_SENSOR)
    recovered = async_capture_events(hass, EVENT_FROST_SENSOR_RECOVERED)
    await setup_site(options=GUARD_OPTS)
    _set_temp(hass, 0)
    await hass.async_block_till_done()
    parked = list(cover.positions)
    hass.states.async_set(OUTSIDE, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(FROST_LOCK).state == "on"
    assert cover.positions == parked
    assert attr(hass, FROST_LOCK, "temperature_status") == "unavailable"
    assert len(unavailable) == 1
    assert unavailable[0].data["entity_id"] == OUTSIDE
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "frost_sensor_site1")
    assert issue is not None
    assert issue.translation_key == "frost_sensor_unavailable"
    notes = async_get_persistent_notifications(hass)
    assert "helios_tilt_frost_sensor_site1" in notes
    _set_temp(hass, 0)
    await hass.async_block_till_done()
    # Still at or below park: recovered event, issue gone, lock remains.
    assert ir.async_get(hass).async_get_issue(DOMAIN, "frost_sensor_site1") is None
    assert "helios_tilt_frost_sensor_site1" not in async_get_persistent_notifications(
        hass
    )
    assert len(recovered) == 1
    assert hass.states.get(FROST_LOCK).state == "on"
    assert cover.positions == parked


async def test_lock_events_and_restart_persistence(
    hass: HomeAssistant, setup_site, cover
) -> None:
    _set_temp(hass, 8)
    locks = async_capture_events(hass, EVENT_FROST_LOCK)
    entry = await setup_site(options=GUARD_OPTS)
    _set_temp(hass, 0)
    await hass.async_block_till_done()
    assert [e.data["action"] for e in locks] == ["engaged"]
    parked = list(cover.positions)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(FROST_LOCK).state == "on"
    # No extra park after the restart.
    assert cover.positions == parked
    assert attr(hass, TARGET, "reason") == "frost_lock"


async def test_old_frost_mode_untouched(hass: HomeAssistant, setup_site, cover) -> None:
    """frost_mode still moves to the frost angle when frost guard is off."""
    _set_temp(hass, -3)
    await setup_site(
        options={
            "frost_mode": True,
            "temperature_sensor": OUTSIDE,
            "frost_temperature": -2,
        }
    )
    assert attr(hass, TARGET, "reason") == "frost"
    assert hass.states.get(FROST_LOCK).state == "off"
    assert cover.positions[-1] == 50  # default frost_angle 30° of 0–60


async def test_snow_remover_holds_then_resumes(
    hass: HomeAssistant, setup_site, cover, freezer
) -> None:
    _set_temp(hass, 8)
    started = async_capture_events(hass, EVENT_SNOW_REMOVER)
    await setup_site(options={**GUARD_OPTS, "snow_remover_hold": 10})
    daily = list(cover.positions)
    await hass.services.async_call(
        DOMAIN, "snow_remover", {"entity_id": TARGET}, blocking=True
    )
    await hass.async_block_till_done()
    assert cover.positions == daily + [100]
    assert attr(hass, TARGET, "reason") == "snow_remover"
    assert started and started[0].data["action"] == "started"
    await advance(hass, freezer, 9)
    assert cover.positions == daily + [100]
    await advance(hass, freezer, 2)
    assert attr(hass, TARGET, "reason") != "snow_remover"


async def test_snow_remover_refused_when_locked_or_cold(
    hass: HomeAssistant, setup_site, cover
) -> None:
    _set_temp(hass, 8)
    refused = async_capture_events(hass, EVENT_SNOW_REMOVER_REFUSED)
    await setup_site(options=GUARD_OPTS)
    _set_temp(hass, 0)
    await hass.async_block_till_done()
    parked = list(cover.positions)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "snow_remover", {"entity_id": TARGET}, blocking=True
        )
    assert cover.positions == parked
    assert refused and refused[0].data["reason"] == "frost_lock"
    notes = async_get_persistent_notifications(hass)
    assert any(nid.startswith("helios_tilt_snow_remover") for nid in notes)


async def test_snow_remover_refused_when_cold(
    hass: HomeAssistant, setup_site, cover
) -> None:
    """Without frost guard, a reading at or below the default park temp is enough."""
    _set_temp(hass, 0.5)
    refused = async_capture_events(hass, EVENT_SNOW_REMOVER_REFUSED)
    await setup_site(options={"temperature_sensor": OUTSIDE, "snow_remover_hold": 10})
    before = list(cover.positions)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "snow_remover", {"entity_id": TARGET}, blocking=True
        )
    assert cover.positions == before
    assert refused and refused[0].data["reason"] == "at_or_below_park_temp"


async def test_snow_remover_refused_when_temperature_unavailable(
    hass: HomeAssistant, setup_site, cover
) -> None:
    _set_temp(hass, 8)
    refused = async_capture_events(hass, EVENT_SNOW_REMOVER_REFUSED)
    await setup_site(options={"temperature_sensor": OUTSIDE})
    hass.states.async_set(OUTSIDE, "unavailable")
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "button", "press", {"entity_id": SNOW_BTN}, blocking=True
        )
    assert refused and refused[0].data["reason"] == "temperature_unavailable"


async def test_wind_stow_beats_snow_remover(
    hass: HomeAssistant, setup_site, cover, weather
) -> None:
    _set_temp(hass, 8)
    await setup_site(options={"temperature_sensor": OUTSIDE, "snow_remover_hold": 10})
    await hass.services.async_call(
        DOMAIN, "snow_remover", {"entity_id": TARGET}, blocking=True
    )
    await hass.async_block_till_done()
    assert attr(hass, TARGET, "reason") == "snow_remover"
    weather(wind_speed=60, wind_gust_speed=70)
    await hass.async_block_till_done()
    assert attr(hass, TARGET, "reason") == "wind"
    assert cover.positions[-1] == 0
