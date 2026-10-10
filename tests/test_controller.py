"""The site controller end to end: strategies, safety, actuators."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from homeassistant.const import EVENT_LOGBOOK_ENTRY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.helios_tilt.const import DOMAIN, EVENT_MOVE

from .conftest import PANEL_DATA, FakeCover, panel_of

TARGET = "sensor.panel_1_target_angle"
CURRENT = "sensor.panel_1_current_angle"


async def advance(hass: HomeAssistant, freezer, minutes: float) -> None:
    """Move time on and let the 60 s tick run."""
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


def attr(hass: HomeAssistant, entity_id: str, name: str) -> Any:
    return hass.states.get(entity_id).attributes.get(name)


async def test_first_move_daily_optimum(hass: HomeAssistant, setup_site, cover) -> None:
    """Midsummer: the daily optimum (14 deg) rounded to the 5 deg step."""
    events = async_capture_events(hass, EVENT_LOGBOOK_ENTRY)
    moves = async_capture_events(hass, EVENT_MOVE)
    await setup_site()
    assert cover.positions == [25]
    assert hass.states.get(TARGET).state == "15.0"
    assert hass.states.get(CURRENT).state == "15.0"
    assert attr(hass, CURRENT, "source") == "cover"
    assert hass.states.get("sensor.panel_1_moves_today").state == "1"
    assert hass.states.get("sensor.panel_1_last_move").state == "strategy"
    history = attr(hass, "sensor.panel_1_last_move", "history")
    assert history[0]["angle"] == 15.0
    assert events[0].data["domain"] == DOMAIN
    assert events[0].data["entity_id"] == TARGET
    assert "moved to 15" in events[0].data["message"]
    assert "Daily optimum" in events[0].data["message"]
    assert moves[0].data["reason"] == "strategy"
    assert len(attr(hass, TARGET, "today_curve")) == 49
    assert attr(hass, TARGET, "fixed_optimum") == pytest.approx(40, abs=5)


async def test_strategies(hass: HomeAssistant, setup_site, cover) -> None:
    """Every strategy through the mode select, applied at once."""
    await setup_site()
    for mode, expected in (
        ("fixed", None),
        ("seasonal", 20),
        ("tracking", 25),
        ("daily", 15),
    ):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": "select.panel_1_mode", "option": mode},
            blocking=True,
        )
        await hass.async_block_till_done()
        state = hass.states.get(TARGET)
        assert state.attributes["mode"] == mode
        if expected is not None:
            assert float(state.state) == expected, mode
    fixed = attr(hass, TARGET, "fixed_optimum")
    assert cover.positions[1] == round(fixed / 60 * 100)


async def test_rate_limit_for_non_urgent_moves(
    hass: HomeAssistant, setup_site, weather, cover, freezer
) -> None:
    """Snow position waits for the minimum move interval."""
    await setup_site()
    weather("snowy")
    await hass.async_block_till_done()
    assert hass.states.get(TARGET).state == "60.0"
    assert cover.positions == [25]
    await advance(hass, freezer, 5)
    assert cover.positions == [25, 100]
    assert hass.states.get("sensor.panel_1_last_move").state == "snow"


async def test_wind_stow_and_resume(
    hass: HomeAssistant, setup_site, weather, cover, freezer
) -> None:
    """Wind stows at once; back to the strategy only after the calm period."""
    await setup_site()
    weather(wind_speed=40, wind_gust_speed=62)
    await hass.async_block_till_done()
    assert cover.positions == [25, 0]
    assert hass.states.get("binary_sensor.panel_1_wind_stow").state == "on"
    assert attr(hass, "binary_sensor.panel_1_wind_stow", "wind_speed") == 62
    assert hass.states.get("sensor.panel_1_last_move").state == "wind"
    weather(wind_speed=20, wind_gust_speed=25)
    await hass.async_block_till_done()
    await advance(hass, freezer, 5)
    assert cover.positions == [25, 0]
    await advance(hass, freezer, 6)
    assert hass.states.get("binary_sensor.panel_1_wind_stow").state == "off"
    assert cover.positions == [25, 0, 25]


async def test_wind_units_and_sensor(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    """m/s weather and an mph anemometer: the highest, in km/h, decides."""
    hass.states.async_set("sensor.wind", "20", {"unit_of_measurement": "mph"})
    await setup_site(site={"wind_sensor": "sensor.wind"})
    assert cover.positions == [25]
    weather(wind_speed=10, wind_gust_speed=12, wind_speed_unit="m/s")  # 43 km/h
    await hass.async_block_till_done()
    assert cover.positions == [25]
    hass.states.async_set(
        "sensor.wind", "33", {"unit_of_measurement": "mph"}
    )  # 53 km/h
    await hass.async_block_till_done()
    assert cover.positions == [25, 0]
    assert attr(hass, "binary_sensor.panel_1_wind_stow", "wind_speed") == pytest.approx(
        53.1, abs=0.1
    )


async def test_never_command_while_moving(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    """A moving cover is not interrupted; the move follows when it stops."""
    await setup_site()
    cover.set(40, "opening")
    await hass.async_block_till_done()
    weather(wind_speed=70)
    await hass.async_block_till_done()
    assert cover.positions == [25]
    assert attr(hass, CURRENT, "moving") is True
    cover.set(25, "open")
    await hass.async_block_till_done()
    assert cover.positions == [25, 0]


async def test_startup_waits_for_valid_data(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    """No movement until the wind is known."""
    hass.states.async_set("weather.home", "unavailable")
    await setup_site()
    assert cover.positions == []
    assert attr(hass, TARGET, "safety") == "startup"
    weather()
    await hass.async_block_till_done()
    assert cover.positions == [25]


async def test_stale_data_freezes(
    hass: HomeAssistant, setup_site, weather, cover, freezer
) -> None:
    """Old wind data: hold; old data after a windy spell: stay stowed."""
    await setup_site(panels=[{**PANEL_DATA, "strategy": "tracking"}])
    first = list(cover.positions)
    await advance(hass, freezer, 121)
    assert attr(hass, TARGET, "safety") == "stale"
    assert cover.positions == first  # tracking would have moved by now
    weather(wind_speed=60)
    await hass.async_block_till_done()
    assert cover.positions[-1] == 0
    hass.states.async_set("weather.home", "unavailable")
    await advance(hass, freezer, 120)
    assert attr(hass, TARGET, "safety") == "wind"
    assert cover.positions[-1] == 0


async def test_manual_move_pauses_auto(
    hass: HomeAssistant, setup_site, weather, cover, freezer
) -> None:
    """Moving the cover by hand pauses automatic control for an hour."""
    await setup_site()
    cover.set(50)
    await hass.async_block_till_done()
    panel = panel_of(hass.config_entries.async_entries(DOMAIN)[0])
    assert panel.manual_until is not None
    assert hass.states.get("sensor.panel_1_last_move").state == "manual"
    assert hass.states.get("sensor.panel_1_moves_today").state == "1"
    assert hass.states.get(TARGET).state == "30.0"
    await advance(hass, freezer, 30)
    assert cover.positions == [25]
    weather()  # fresh data
    await advance(hass, freezer, 31)
    assert cover.positions == [25, 25]


async def test_own_moves_are_not_manual(
    hass: HomeAssistant, setup_site, cover, freezer
) -> None:
    """Intermediate positions during our own move don't count as manual."""
    await setup_site()
    cover.follow = False
    await hass.services.async_call(
        DOMAIN, "set_tilt", {"entity_id": TARGET, "angle": 45}, blocking=True
    )
    for pos in (40, 55, 75):
        cover.set(pos, "opening")
        cover.set(pos, "open")
    await hass.async_block_till_done()
    panel = panel_of(hass.config_entries.async_entries(DOMAIN)[0])
    assert panel.manual_until is None
    assert (
        hass.states.get("sensor.panel_1_last_move").state == "manual"
    )  # manual *mode*
    assert attr(hass, TARGET, "mode") == "manual"


async def test_stuck_actuator_repair(
    hass: HomeAssistant, setup_site, cover, freezer
) -> None:
    """No arrival within 1.5x the travel time: a repair issue, cleared on arrival."""
    cover.follow = False
    await setup_site()
    assert cover.positions == [25]
    await advance(hass, freezer, 1)
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(
        DOMAIN,
        f"actuator_stuck_{panel_of(hass.config_entries.async_entries(DOMAIN)[0]).id}",
    )
    assert issue is not None
    assert issue.translation_placeholders["target"] == "15"
    assert attr(hass, CURRENT, "stuck") is True
    cover.set(25)
    await hass.async_block_till_done()
    assert issues.async_get_issue(DOMAIN, issue.issue_id) is None


async def test_number_actuator_open_loop(
    hass: HomeAssistant, setup_site, freezer
) -> None:
    """An input_number without feedback: position from the travel time."""
    calls = async_mock_service(hass, "input_number", "set_value")
    hass.states.async_set("input_number.actuator", "0")
    await setup_site(
        panels=[
            {
                **PANEL_DATA,
                "actuator_entity": "input_number.actuator",
                "position_at_max": 300,
            }
        ]
    )
    assert calls[0].data == {"entity_id": "input_number.actuator", "value": 75.0}
    assert attr(hass, CURRENT, "source") == "estimate"
    # Before the actuator could have arrived: still moving, no new command.
    await hass.services.async_call(
        DOMAIN, "set_tilt", {"entity_id": TARGET, "angle": 30}, blocking=True
    )
    assert len(calls) == 1
    await advance(hass, freezer, 1)
    assert len(calls) == 2
    assert calls[1].data["value"] == 150.0


async def test_script_actuator(hass: HomeAssistant, setup_site) -> None:
    """Scripts get angle, position and panel name."""
    calls = async_mock_service(hass, "script", "turn_on")
    hass.states.async_set("script.tilt", "off")
    await setup_site(
        panels=[{**PANEL_DATA, "actuator_entity": "script.tilt", "title": "Shed"}]
    )
    assert calls[0].data["variables"] == {
        "angle": 15.0,
        "position": 25.0,
        "panel": "Shed",
    }


async def test_feedback_sensor_angle(hass: HomeAssistant, setup_site, cover) -> None:
    """An angle sensor overrides the cover position."""
    hass.states.async_set("sensor.inclinometer", "12.3")
    await setup_site(
        panels=[
            {
                **PANEL_DATA,
                "feedback_entity": "sensor.inclinometer",
                "feedback_kind": "angle",
            }
        ]
    )
    assert hass.states.get(CURRENT).state == "12.3"
    assert attr(hass, CURRENT, "source") == "feedback"


async def test_tracking_night_and_diffuse(
    hass: HomeAssistant, setup_site, weather, freezer
) -> None:
    """Tracking parks at night and goes flat under heavy cloud."""
    await setup_site(panels=[{**PANEL_DATA, "strategy": "tracking"}])
    assert attr(hass, TARGET, "reason") == "strategy"
    weather(cloud_coverage=95)
    await advance(hass, freezer, 5)
    assert hass.states.get(TARGET).state == "10.0"
    assert attr(hass, TARGET, "reason") == "diffuse"
    freezer.move_to("2026-06-21 23:30:00+00:00")
    weather(cloud_coverage=95)
    await advance(hass, freezer, 1)
    assert hass.states.get(TARGET).state == "15.0"
    assert attr(hass, TARGET, "reason") == "night"


async def test_roll_tracker(hass: HomeAssistant, setup_site, cover, freezer) -> None:
    """Single-axis roll tracker: negative angles in the morning."""
    freezer.move_to("2026-06-21 05:00:00+00:00")
    await setup_site(
        panels=[
            {
                **PANEL_DATA,
                "axis": "roll",
                "azimuth": 270,
                "min_angle": -50,
                "max_angle": 50,
                "strategy": "tracking",
            }
        ]
    )
    assert float(hass.states.get(TARGET).state) == -50.0
    assert cover.positions == [0]


async def test_auto_switch_off_still_stows(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    """Automatic control off: no strategy moves, but wind still stows."""
    await setup_site()
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.panel_1_automatic_control"},
        blocking=True,
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.panel_1_mode", "option": "fixed"},
        blocking=True,
    )
    assert cover.positions == [25]
    weather(wind_speed=80)
    await hass.async_block_till_done()
    assert cover.positions == [25, 0]
    assert hass.states.get("binary_sensor.panel_1_storm_mode").state == "on"


async def test_manual_angle_number(hass: HomeAssistant, setup_site, cover) -> None:
    """The manual angle number goes manual and moves at once (no rate limit)."""
    await setup_site()
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.panel_1_manual_angle", "value": 33},
        blocking=True,
    )
    assert cover.positions == [25, 55]
    assert hass.states.get("select.panel_1_mode").state == "manual"
    assert hass.states.get("number.panel_1_manual_angle").state == "33.0"


async def test_gain_and_pv(hass: HomeAssistant, setup_site, freezer) -> None:
    """Gain vs the fixed optimum accumulates; PV actual vs model."""
    hass.states.async_set("sensor.pv", "1500", {"unit_of_measurement": "W"})
    await setup_site(
        panels=[{**PANEL_DATA, "pv_power_entity": "sensor.pv", "pv_peak_power": 2000}]
    )
    await advance(hass, freezer, 10)
    gain = float(hass.states.get("sensor.panel_1_estimated_gain").state)
    assert -20 < gain < 20
    pv = hass.states.get("sensor.panel_1_pv_actual_vs_model")
    assert pv is not None
    assert 50 < float(pv.state) < 150
    assert attr(hass, "sensor.panel_1_pv_actual_vs_model", "actual_power") == 1500


async def test_state_survives_restart(hass: HomeAssistant, setup_site, cover) -> None:
    """Mode, history and the storm latch are restored."""
    entry = await setup_site()
    await hass.services.async_call(
        DOMAIN, "set_mode", {"mode": "seasonal"}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "stow", {"storm": True}, blocking=True)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert attr(hass, TARGET, "mode") == "seasonal"
    assert hass.states.get("binary_sensor.panel_1_storm_mode").state == "on"
    assert len(attr(hass, "sensor.panel_1_last_move", "history")) == 3
    assert cover.positions == [25, 33, 0]


async def test_gain_over_a_clear_day_ignores_the_wind_stow(
    hass: HomeAssistant, setup_site, weather, cover, freezer
) -> None:
    """Tracking and daily end a clear day ahead of fixed, despite a stow.

    The stow is a safety hold, not the strategy: it is left out of both sides
    and reported as excluded minutes.
    """
    freezer.move_to("2026-09-12 04:30:00+00:00")
    FakeCover(hass, "cover.rack")
    weather(wind_speed=12, wind_gust_speed=18)
    await setup_site(
        panels=[
            {**PANEL_DATA, "strategy": "tracking", "min_angle": 5, "max_angle": 65},
            {
                **PANEL_DATA,
                "title": "Rack",
                "actuator_entity": "cover.rack",
                "strategy": "daily",
            },
        ]
    )
    instant = []
    for i in range(14 * 12):  # 04:30 to 18:30 UTC in 5 minute rounds
        gusty = 96 <= i < 99  # 12:30 to 12:45 UTC
        if gusty:
            weather(wind_speed=38, wind_gust_speed=58)
        else:
            weather(wind_speed=12, wind_gust_speed=18)
        await advance(hass, freezer, 5)
        instant.append(attr(hass, "sensor.panel_1_estimated_gain", "instant_gain"))
    for gain_id in ("sensor.panel_1_estimated_gain", "sensor.rack_estimated_gain"):
        state = hass.states.get(gain_id)
        assert float(state.state) >= 0.0, gain_id
        assert state.attributes["excluded_minutes"] >= 15, gain_id
        assert state.attributes["counted_since"] is not None
        assert state.attributes["fixed_angle"] == 40.0
    assert any(v is not None for v in instant)
    assert hass.states.get("sensor.panel_1_last_move").state == "night"
