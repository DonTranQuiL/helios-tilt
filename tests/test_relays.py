"""Two relays (timed): timing math, interlock, countdown, homing, restore, faults."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed_exact

from custom_components.helios_tilt.const import DOMAIN
from custom_components.helios_tilt.relays import (
    CLOSE,
    OPEN,
    RelayConfig,
    countdown_seconds,
    home_target,
    plan_run,
    position_after,
    snap_to_end,
)

from .conftest import PANEL_DATA, panel_of

CFG = RelayConfig(
    open_switch="relay.open",
    close_switch="relay.close",
    open_time=20.0,
    close_time=16.0,
    home_overrun=15.0,
)

# ---- timing math ------------------------------------------------------------------


def test_plan_uses_the_speed_of_each_direction() -> None:
    """Opening and closing take different times; the start delay is added."""
    up = plan_run(25.0, 50.0, CFG)
    assert up is not None
    assert (up.direction, up.seconds, up.end, up.homing) == (OPEN, 5.0, 50.0, False)
    down = plan_run(50.0, 25.0, CFG)
    assert down is not None
    assert (down.direction, down.seconds) == (CLOSE, 4.0)
    slow = RelayConfig("a", "b", open_time=20, close_time=16, start_delay=0.5)
    assert plan_run(25.0, 50.0, slow).seconds == pytest.approx(5.5)  # type: ignore[union-attr]
    assert plan_run(25.0, 25.02, CFG) is None


def test_plan_homes_into_an_end_with_overrun() -> None:
    """Near an end the run goes into the end stop and on for the overrun."""
    assert snap_to_end(1.5) == 0.0 and snap_to_end(98.5) == 100.0
    assert snap_to_end(50.0) == 50.0
    up = plan_run(25.0, 99.0, CFG)
    assert up is not None
    assert up.homing and up.end == 100.0
    assert up.seconds == pytest.approx(0.75 * 20 + 0.15 * 20)
    down = plan_run(25.0, 0.0, CFG)
    assert down is not None
    assert down.homing and down.direction == CLOSE
    assert down.seconds == pytest.approx(0.25 * 16 + 0.15 * 16)
    # Already at the end: just the overrun (re-sync in place).
    again = plan_run(0.0, 0.0, CFG)
    assert again is not None and again.seconds == pytest.approx(2.4)


def test_plan_from_an_unknown_position() -> None:
    """Unknown start: only a full homing run is possible, capped at max_run."""
    assert plan_run(None, 40.0, CFG) is None
    run = plan_run(None, 0.0, CFG)
    assert run is not None
    assert run.seconds == pytest.approx(16 * 1.15)
    assert run.seconds <= CFG.max_run
    assert CFG.max_run == pytest.approx(20 * 1.15 + 5)


def test_position_estimate_and_helpers() -> None:
    """Elapsed time to stroke, clamped; countdown rounding; home end."""
    assert position_after(25.0, OPEN, 5.0, CFG) == pytest.approx(50.0)
    assert position_after(25.0, CLOSE, 2.0, CFG) == pytest.approx(12.5)
    assert position_after(90.0, OPEN, 60.0, CFG) == 100.0
    slow = RelayConfig("a", "b", open_time=20, close_time=16, start_delay=1.0)
    assert position_after(25.0, OPEN, 0.5, slow) == 25.0
    assert countdown_seconds(5.0) == 7
    assert countdown_seconds(5.1) == 8
    assert countdown_seconds(10**6) == 43200
    assert home_target(80.0, CFG) == 0.0
    nearest = RelayConfig("a", "b", home_end="nearest")
    assert home_target(80.0, nearest) == 100.0
    assert home_target(None, nearest) == 0.0
    assert home_target(10.0, RelayConfig("a", "b", home_end="open")) == 100.0


# ---- fakes --------------------------------------------------------------------------


class FakeRelays:
    """Relay switches (domain 'relay') and countdowns (domain 'countdown').

    Records every call with its time, flags both relays on at once, and can
    ignore commands to one relay (to test the confirm timeout).
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.t0 = dt_util.utcnow()
        self.log: list[tuple[float, str, Any]] = []
        self.ignore: set[str] = set()
        self.both_on = False
        for entity_id in ("relay.open", "relay.close"):
            hass.states.async_set(entity_id, "off")
        for entity_id in ("countdown.open", "countdown.close"):
            hass.states.async_set(entity_id, "0")

        async def _switch(call: ServiceCall) -> None:
            on = call.service == "turn_on"
            for entity_id in _ids(call):
                self.log.append((self.now(), entity_id, "on" if on else "off"))
                offline = hass.states.get(entity_id).state == "unavailable"
                if entity_id not in self.ignore and not offline:
                    self.set(entity_id, on)

        async def _countdown(call: ServiceCall) -> None:
            for entity_id in _ids(call):
                self.log.append((self.now(), entity_id, call.data["value"]))
                hass.states.async_set(entity_id, str(call.data["value"]))

        hass.services.async_register("relay", "turn_on", _switch)
        hass.services.async_register("relay", "turn_off", _switch)
        hass.services.async_register("countdown", "set_value", _countdown)

    def now(self) -> float:
        return round((dt_util.utcnow() - self.t0).total_seconds(), 2)

    def set(self, entity_id: str, on: bool) -> None:
        self.hass.states.async_set(entity_id, "on" if on else "off")
        if self.on("relay.open") and self.on("relay.close"):
            self.both_on = True

    def on(self, entity_id: str) -> bool:
        return self.hass.states.get(entity_id).state == "on"

    def calls(self, entity_id: str) -> list[tuple[float, Any]]:
        return [(t, a) for t, e, a in self.log if e == entity_id]

    def sequence(self) -> list[tuple[str, Any]]:
        return [(e, a) for _t, e, a in self.log]


def _ids(call: ServiceCall) -> list[str]:
    ids = call.data["entity_id"]
    return [ids] if isinstance(ids, str) else list(ids)


RELAY_PANEL = {
    **{k: v for k, v in PANEL_DATA.items() if k != "actuator_entity"},
    "actuator_type": "relays",
    "open_switch": "relay.open",
    "close_switch": "relay.close",
    "open_countdown": "countdown.open",
    "close_countdown": "countdown.close",
    "open_time": 20.0,
    "close_time": 16.0,
    "angle_closed": 0.0,
    "angle_open": 60.0,
    "home_overrun": 15.0,
    "reverse_delay": 1.0,
}
CURRENT = "sensor.panel_1_current_angle"


async def run(hass: HomeAssistant, freezer, seconds: float, step: float = 0.1) -> None:
    """Let time pass in small steps so every timer fires near its time."""
    left = seconds
    while left > 1e-9:
        dt = min(step, left)
        freezer.tick(timedelta(seconds=dt))
        async_fire_time_changed_exact(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        left -= dt


@pytest.fixture
def relays(hass: HomeAssistant, frozen) -> FakeRelays:
    """The two relays and their countdowns."""
    return FakeRelays(hass)


@pytest.fixture
async def relay_site(hass, setup_site, relays, freezer):
    """A site whose panel is on two relays; the first move (home + go) done."""
    entry = await setup_site(panels=[{**RELAY_PANEL}])
    await run(hass, freezer, 30)
    return entry


def _assert_interlock(relays: FakeRelays) -> None:
    """Before every 'on', the other relay was told off at least 0.3 s earlier."""
    assert not relays.both_on
    other = {"relay.open": "relay.close", "relay.close": "relay.open"}
    for t, entity_id, action in relays.log:
        if action != "on":
            continue
        offs = [
            tt for tt, a in relays.calls(other[entity_id]) if a == "off" and tt <= t
        ]
        assert offs, f"{entity_id} on at {t} without the other relay off first"
        assert t - offs[-1] >= 0.3 - 1e-6, (entity_id, t, offs[-1])


# ---- behaviour ------------------------------------------------------------------------


async def test_first_move_homes_then_drives(
    hass: HomeAssistant, relay_site, relays
) -> None:
    """Unknown start: close into the end stop first, then open to 25 %.

    Midsummer noon: the daily optimum is 15 deg = 25 % stroke on 0..60 deg.
    """
    seq = relays.sequence()
    assert seq == [
        ("relay.open", "off"),  # interlock
        ("relay.close", "on"),  # homing: 16 s * 1.15 = 18.4 s
        ("countdown.close", 21),  # ceil(18.4 + 2) - the hardware fail-safe
        ("relay.close", "off"),
        ("countdown.close", 0),  # disarm: a Tuya countdown would switch it back on
        ("relay.close", "off"),  # interlock for the next run
        ("relay.open", "on"),  # 25 % of 20 s = 5 s
        ("countdown.open", 7),
        ("relay.open", "off"),
        ("countdown.open", 0),
    ]
    times = dict(((e, a, i), t) for i, (t, e, a) in enumerate(relays.log))
    close_on = times[("relay.close", "on", 1)]
    close_off = times[("relay.close", "off", 3)]
    open_on = times[("relay.open", "on", 6)]
    open_off = times[("relay.open", "off", 8)]
    assert close_off - close_on == pytest.approx(18.4, abs=0.15)
    assert open_off - open_on == pytest.approx(5.0, abs=0.15)
    assert open_on - close_off >= 1.0  # direction change dead time
    _assert_interlock(relays)
    panel = panel_of(relay_site)
    assert panel.driver.position == pytest.approx(25.0)
    assert not panel.driver.uncertain
    state = hass.states.get(CURRENT)
    assert float(state.state) == 15.0
    assert state.attributes["source"] == "estimate"
    assert state.attributes["estimated"] is True
    assert state.attributes["position_uncertain"] is False
    assert hass.states.get("binary_sensor.panel_1_position_uncertain").state == "off"


async def test_countdown_is_armed_after_the_relay_is_on(relay_site, relays) -> None:
    """The countdown follows the confirmed 'on' (Tuya countdowns toggle)."""
    seq = relays.sequence()
    for relay, countdown in (
        ("relay.close", "countdown.close"),
        ("relay.open", "countdown.open"),
    ):
        on = seq.index((relay, "on"))
        armed = next(i for i, (e, a) in enumerate(seq) if e == countdown and a)
        assert armed == on + 1


async def test_homing_overrun_at_the_end(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """Setting the maximum angle drives into the open end stop with overrun."""
    relays.log.clear()
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 60}, blocking=True)
    await run(hass, freezer, 25)
    on = next(t for t, a in relays.calls("relay.open") if a == "on")
    off = next(t for t, a in relays.calls("relay.open") if a == "off" and t > on)
    assert off - on == pytest.approx(0.75 * 20 + 0.15 * 20, abs=0.15)
    driver = panel_of(relay_site).driver
    assert driver.position == 100.0
    assert driver.moves_since_home == 0  # re-synced
    assert driver.last_homed is not None
    assert float(hass.states.get(CURRENT).state) == 60.0
    _assert_interlock(relays)


async def test_restart_mid_move_is_uncertain_and_homes_next_move(
    hass: HomeAssistant, relay_site, relays, freezer, hass_storage
) -> None:
    """In motion when Home Assistant stopped: uncertain until the next move homes."""
    entry = relay_site
    panel = panel_of(entry)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    stored = hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"]
    stored["panels"][panel.id]["relay"].update({"in_motion": True, "position": 40.0})
    relays.log.clear()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await run(hass, freezer, 2)
    panel = panel_of(entry)
    assert panel.driver.uncertain
    assert panel.driver.position == 40.0
    assert hass.states.get("binary_sensor.panel_1_position_uncertain").state == "on"
    # Same target as before the restart: nothing moves yet (only when safe).
    assert ("relay.open", "on") not in relays.sequence()
    assert ("relay.close", "on") not in relays.sequence()
    # The next move homes first.
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 30}, blocking=True)
    await run(hass, freezer, 40)
    ons = [e for e, a in relays.sequence() if a == "on"]
    assert ons == ["relay.close", "relay.open"]
    assert not panel.driver.uncertain
    assert panel.driver.position == pytest.approx(50.0)
    _assert_interlock(relays)


async def test_external_operation_updates_the_estimate(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """A wall switch or remote runs a relay: track it and pause automatic control."""
    relays.set("relay.open", True)
    await hass.async_block_till_done()
    await run(hass, freezer, 4)
    relays.set("relay.open", False)
    await hass.async_block_till_done()
    panel = panel_of(relay_site)
    assert panel.driver.position == pytest.approx(25 + 4 / 20 * 100, abs=1)
    assert not panel.driver.uncertain
    assert float(hass.states.get(CURRENT).state) == pytest.approx(27, abs=0.5)
    assert panel.manual_until is not None
    assert hass.states.get("sensor.panel_1_last_move").state == "manual"


async def test_external_run_is_capped(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """A relay left on by someone else is switched off after the maximum run."""
    relays.log.clear()
    relays.set("relay.close", True)
    await hass.async_block_till_done()
    cap = panel_of(relay_site).driver.cfg.max_run
    await run(hass, freezer, cap - 1, step=0.5)
    assert relays.on("relay.close")
    await run(hass, freezer, 2, step=0.25)
    assert not relays.on("relay.close")
    driver = panel_of(relay_site).driver
    assert driver.position == 0.0  # ran long enough to reach the end stop
    assert not driver.uncertain


async def test_no_confirm_aborts_and_marks_uncertain(
    hass: HomeAssistant, setup_site, relays, freezer
) -> None:
    """A relay that doesn't report 'on' stops everything and raises a repair."""
    relays.ignore.add("relay.open")
    entry = await setup_site(panels=[{**RELAY_PANEL}])
    await run(hass, freezer, 30, step=0.25)
    panel = panel_of(entry)
    assert panel.driver.uncertain
    assert panel.driver.fault and "relay.open" in panel.driver.fault
    assert not relays.on("relay.close") and not relays.on("relay.open")
    seq = relays.sequence()
    last_on = max(i for i, (e, a) in enumerate(seq) if (e, a) == ("relay.open", "on"))
    assert ("relay.open", "off") in seq[last_on:]
    assert ("relay.close", "off") in seq[last_on:]
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"relay_fault_{panel.id}")
    assert issue is not None


async def test_wind_interrupts_a_run(
    hass: HomeAssistant, relay_site, relays, freezer, weather
) -> None:
    """A wind stow during a run stops it and drives to stow (with dead time)."""
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 50}, blocking=True)
    await run(hass, freezer, 3)
    assert relays.on("relay.open")
    relays.log.clear()
    weather(wind_speed=60, wind_gust_speed=80)
    await hass.async_block_till_done()
    await run(hass, freezer, 25, step=0.25)
    seq = relays.sequence()
    assert seq[0] == ("relay.open", "off")
    close_on = next(t for t, a in relays.calls("relay.close") if a == "on")
    open_off = relays.calls("relay.open")[0][0]
    assert close_on - open_off >= 1.0
    driver = panel_of(relay_site).driver
    assert driver.position == 0.0  # stow angle 0 deg = fully closed (homed)
    assert hass.states.get("binary_sensor.panel_1_wind_stow").state == "on"
    _assert_interlock(relays)


async def test_unload_mid_run_switches_both_off(
    hass: HomeAssistant, relay_site, relays, freezer, hass_storage
) -> None:
    """Unloading (or stopping Home Assistant) never leaves a relay on."""
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 45}, blocking=True)
    await run(hass, freezer, 2)
    assert relays.on("relay.open")
    await hass.config_entries.async_unload(relay_site.entry_id)
    await hass.async_block_till_done()
    assert not relays.on("relay.open") and not relays.on("relay.close")
    assert hass.states.get("countdown.open").state == "0"
    stored = hass_storage[f"{DOMAIN}.{relay_site.entry_id}"]["data"]
    relay = next(iter(stored["panels"].values()))["relay"]
    assert relay["in_motion"] is False
    assert 25 < relay["position"] < 50


async def test_home_now_button(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """Home now: into the closed end stop, then back to the target."""
    relays.log.clear()
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.panel_1_home_now"}, blocking=True
    )
    await run(hass, freezer, 30)
    ons = [e for e, a in relays.sequence() if a == "on"]
    assert ons == ["relay.close", "relay.open"]
    driver = panel_of(relay_site).driver
    assert driver.position == pytest.approx(25.0)
    assert driver.moves_since_home == 1
    _assert_interlock(relays)


async def test_travel_calibration_service(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """Start closes (homing), then opens; stop marks each end; times are saved."""
    await hass.services.async_call(
        DOMAIN,
        "calibrate_travel",
        {"entity_id": CURRENT, "action": "start", "homing_seconds": 10},
        blocking=True,
    )
    await run(hass, freezer, 9)
    panel = panel_of(relay_site)
    assert panel.driver.calibration["phase"] == "homing"
    assert relays.on("relay.close")
    await run(hass, freezer, 2.7)  # end of homing, reverse dead time, opening
    assert panel.driver.calibration["phase"] == "opening"
    assert relays.on("relay.open")
    opened = relays.calls("relay.open")[-1][0]
    await run(hass, freezer, 21)
    open_time = relays.now() - opened
    await hass.services.async_call(
        DOMAIN,
        "calibrate_travel",
        {"entity_id": CURRENT, "action": "stop"},
        blocking=True,
    )
    await run(hass, freezer, 1.5)
    assert panel.driver.calibration["phase"] == "closing"
    assert relays.on("relay.close")
    closed = relays.calls("relay.close")[-1][0]
    await run(hass, freezer, 17)
    close_time = relays.now() - closed
    await hass.services.async_call(
        DOMAIN,
        "calibrate_travel",
        {"entity_id": CURRENT, "action": "stop"},
        blocking=True,
    )
    await run(hass, freezer, 1)
    await hass.async_block_till_done()
    sub = next(iter(relay_site.subentries.values()))
    assert sub.data["open_time"] == pytest.approx(open_time, abs=0.11)
    assert sub.data["close_time"] == pytest.approx(close_time, abs=0.11)
    assert not relays.on("relay.open") and not relays.on("relay.close")
    assert not relays.both_on
    # Reloaded with the new times; position known (homed at closed).
    panel = panel_of(relay_site)
    assert panel.driver.cfg.open_time == sub.data["open_time"]
    assert panel.driver.position == 0.0


async def test_no_moves_during_calibration(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """While calibrating, strategy moves wait; cancel stops both relays."""
    await hass.services.async_call(
        DOMAIN,
        "calibrate_travel",
        {"entity_id": CURRENT, "action": "start", "homing_seconds": 5},
        blocking=True,
    )
    await run(hass, freezer, 3)
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 40}, blocking=True)
    await run(hass, freezer, 1)
    assert relays.on("relay.close")  # still the calibration's homing run
    await hass.services.async_call(
        DOMAIN,
        "calibrate_travel",
        {"entity_id": CURRENT, "action": "cancel"},
        blocking=True,
    )
    await run(hass, freezer, 0.5)
    assert not relays.on("relay.close") and not relays.on("relay.open")
    assert panel_of(relay_site).driver.calibration is None
    assert panel_of(relay_site).driver.uncertain


async def test_wind_cancels_a_calibration(
    hass: HomeAssistant, relay_site, relays, freezer, weather
) -> None:
    """Safety wins over a travel calibration: cancel it and stow."""
    await hass.services.async_call(
        DOMAIN,
        "calibrate_travel",
        {"entity_id": CURRENT, "action": "start", "homing_seconds": 5},
        blocking=True,
    )
    await run(hass, freezer, 8)
    assert relays.on("relay.open")  # timing the open run
    weather(wind_speed=60, wind_gust_speed=80)
    await hass.async_block_till_done()
    await run(hass, freezer, 30, step=0.25)
    driver = panel_of(relay_site).driver
    assert driver.calibration is None
    assert driver.position == 0.0
    assert not driver.uncertain  # homed while stowing to fully closed
    assert not relays.on("relay.open") and not relays.on("relay.close")
    _assert_interlock(relays)


async def test_relay_services_need_a_relay_panel(
    hass: HomeAssistant, setup_site
) -> None:
    """home and calibrate_travel refuse panels on an entity actuator."""
    from homeassistant.exceptions import ServiceValidationError

    await setup_site()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "home", {"entity_id": CURRENT}, blocking=True
        )
    assert hass.states.get("button.panel_1_home_now") is None


# ---- config flow ------------------------------------------------------------------------


def test_positions_outside_the_limits_are_refused() -> None:
    """Backstop for the selector limits, and the latitude suggestion."""
    from custom_components.helios_tilt.config_flow import (
        _validate_positions,
        season_suggestion,
    )
    from custom_components.helios_tilt.const import PANEL_DEFAULTS

    data = {**PANEL_DEFAULTS, "min_angle": 10, "max_angle": 40, "stow_angle": 10}
    data.update({k: 20 for k in ("night_angle", "diffuse_angle", "snow_angle")})
    data.update({k: 20 for k in ("rain_angle", "frost_angle", "winter_angle")})
    data["summer_angle"] = 15
    assert _validate_positions(data) == {}
    assert _validate_positions({**data, "stow_angle": 0}) == {
        "stow_angle": "outside_limits"
    }
    assert season_suggestion(52.37, 0, 90) == (67, 17)
    assert season_suggestion(-33.9, 0, 90) == (49, 0)  # southern hemisphere: abs
    assert season_suggestion(52.37, 10, 40) == (40, 17)
    assert season_suggestion(20, 10, 40) == (35, 10)


async def test_add_relay_panel_validates(hass: HomeAssistant, setup_site) -> None:
    """The user's attic window: ZG-2002-RF relays, 10..40 deg, in three steps."""
    from homeassistant import config_entries
    from homeassistant.data_entry_flow import FlowResultType, InvalidData

    from custom_components.helios_tilt.const import SUBENTRY_PANEL

    from .test_config_flow import relays_input, type_input

    entry = await setup_site()
    for entity_id in ("switch.windowswitch_l1", "switch.windowswitch_l2"):
        hass.states.async_set(entity_id, "off")
    for entity_id in (
        "number.windowswitch_countdown_l1",
        "number.windowswitch_countdown_l2",
    ):
        hass.states.async_set(entity_id, "0")
    good = {
        "open_switch": "switch.windowswitch_l1",
        "close_switch": "switch.windowswitch_l2",
        "open_countdown": "number.windowswitch_countdown_l1",
        "close_countdown": "number.windowswitch_countdown_l2",
        "angle_closed": 10,
        "angle_open": 40,
        "min_angle": 10,
        "max_angle": 40,
    }

    def form(**kw):
        return relays_input(**{**good, **kw})

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_PANEL), context={"source": config_entries.SOURCE_USER}
    )
    flow = result["flow_id"]
    configure = hass.config_entries.subentries.async_configure
    assert {str(k) for k in result["data_schema"].schema} == {"name", "actuator_type"}
    result = await configure(flow, type_input("Attic", "relays"))
    assert result["step_id"] == "relays"
    schema = {str(k) for k in result["data_schema"].schema}
    assert "actuator_entity" not in schema
    assert "mapping_feedback" not in schema
    assert {"open_switch", "close_countdown", "angle_open", "relay_advanced"} <= schema
    with pytest.raises(InvalidData):
        await configure(flow, form(open_switch=None))
    result = await configure(flow, form(close_switch="switch.windowswitch_l1"))
    assert result["errors"] == {"close_switch": "same_relay"}
    result = await configure(
        flow, form(close_countdown="number.windowswitch_countdown_l1")
    )
    assert result["errors"] == {"close_countdown": "same_countdown"}
    result = await configure(flow, form(angle_open=10))
    assert result["errors"] == {"angle_open": "same_end_angles"}
    result = await configure(flow, form(max_angle=60))
    assert result["errors"] == {"base": "limits_outside_stroke"}
    result = await configure(flow, form())
    assert result["step_id"] == "positions"
    defaults = {
        str(k): k.default()
        for k in result["data_schema"].schema
        if hasattr(k, "default") and callable(k.default)
    }
    assert defaults["stow_angle"] == 10  # 0 clamped to the minimum
    assert defaults["snow_angle"] == 40
    assert defaults["winter_angle"] == 40  # 52.4 + 15, clamped
    assert defaults["summer_angle"] == 17
    defaults.pop("pv", None)
    result = await configure(flow, {**defaults, "pv": {"pv_peak_power": 0}})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    sub = next(s for s in entry.subentries.values() if s.title == "Attic")
    assert sub.unique_id == "switch.windowswitch_l1"
    assert sub.data["actuator_type"] == "relays"
    assert "actuator_entity" not in sub.data
    assert sub.data["close_countdown"] == "number.windowswitch_countdown_l2"
    assert sub.data["min_angle"] == 10 and sub.data["stow_angle"] == 10
    assert hass.states.get("button.attic_home_now") is not None
    assert hass.states.get("binary_sensor.attic_position_uncertain") is not None
    # The entity panel has no relay keys, and needs its actuator.
    first = next(s for s in entry.subentries.values() if s.title != "Attic")
    assert "open_switch" not in first.data
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_guided_travel_flow(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """Reconfigure > Time the travel: home, mark open, mark closed, save."""
    from homeassistant.data_entry_flow import FlowResultType

    entry = relay_site
    sub = next(iter(entry.subentries.values()))
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["settings", "travel"]
    configure = hass.config_entries.subentries.async_configure
    result = await configure(result["flow_id"], {"next_step_id": "travel"})
    assert result["step_id"] == "travel"
    flow = result["flow_id"]
    result = await configure(flow, {"homing_seconds": 8})
    assert result["step_id"] == "travel_open"
    await run(hass, freezer, 3)
    result = await configure(flow, {})
    assert result["errors"] == {"base": "still_homing"}
    await run(hass, freezer, 7)
    assert relays.on("relay.open")
    opened = relays.calls("relay.open")[-1][0]
    await run(hass, freezer, 22)
    expected_open = relays.now() - opened
    result = await configure(flow, {})
    assert result["step_id"] == "travel_close"
    await run(hass, freezer, 1.5)
    assert relays.on("relay.close")
    closed = relays.calls("relay.close")[-1][0]
    await run(hass, freezer, 18)
    expected_close = relays.now() - closed
    result = await configure(flow, {})
    assert result["step_id"] == "travel_result"
    schema = {str(k): k for k in result["data_schema"].schema}
    open_time = schema["open_time"].default()
    close_time = schema["close_time"].default()
    assert open_time == pytest.approx(expected_open, abs=0.11)
    assert close_time == pytest.approx(expected_close, abs=0.11)
    await run(hass, freezer, 1)
    assert not relays.on("relay.open") and not relays.on("relay.close")
    result = await configure(
        flow,
        {
            "open_time": open_time,
            "close_time": close_time,
            "angle_closed": 0,
            "angle_open": 60,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.subentries[sub.subentry_id].data["open_time"] == open_time
    assert panel_of(entry).driver.cfg.close_time == close_time
    _assert_interlock(relays)


async def test_closing_the_travel_dialog_stops_the_relays(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """Abandoning the guided flow cancels the calibration."""
    entry = relay_site
    sub = next(iter(entry.subentries.values()))
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    configure = hass.config_entries.subentries.async_configure
    result = await configure(result["flow_id"], {"next_step_id": "travel"})
    result = await configure(result["flow_id"], {"homing_seconds": 8})
    await run(hass, freezer, 2)
    assert relays.on("relay.close")
    hass.config_entries.subentries.async_abort(result["flow_id"])
    await run(hass, freezer, 0.5)
    assert not relays.on("relay.close") and not relays.on("relay.open")
    assert panel_of(entry).driver.calibration is None


# ---- offline relays ------------------------------------------------------------------


async def test_offline_relay_blocks_runs_and_recovers(
    hass: HomeAssistant, relay_site, relays, freezer, caplog
) -> None:
    """Offline: no attempts, a repair and a sensor; back: it moves by itself."""
    panel = panel_of(relay_site)
    hass.states.async_set("relay.open", "unavailable")
    await hass.async_block_till_done()
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(DOMAIN, f"relay_unavailable_{panel.id}")
    assert issue is not None
    assert issue.translation_placeholders["entities"] == "relay.open"
    assert "relay.open is unavailable (Zigbee device offline?)" in caplog.text
    assert hass.states.get("binary_sensor.panel_1_actuator_available").state == "off"
    attrs = hass.states.get(CURRENT).attributes
    assert attrs["actuator_available"] is False
    assert attrs["unavailable_entities"] == ["relay.open"]

    relays.log.clear()
    caplog.clear()
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 40}, blocking=True)
    await run(hass, freezer, 600, step=5)
    assert relays.log == []  # not a single attempt
    assert "did not confirm" not in caplog.text
    assert "did not reach" not in caplog.text
    assert caplog.text.count("is unavailable") == 0  # logged once, earlier
    assert issues.async_get_issue(DOMAIN, f"relay_fault_{panel.id}") is None

    # Back online: the issue clears and the pending target is driven.
    hass.states.async_set("relay.open", "off")
    await hass.async_block_till_done()
    assert issues.async_get_issue(DOMAIN, f"relay_unavailable_{panel.id}") is None
    assert hass.states.get("binary_sensor.panel_1_actuator_available").state == "on"
    await run(hass, freezer, 30, step=0.25)
    assert ("relay.open", "on") in relays.sequence()
    assert panel.driver.position == pytest.approx(100 * 40 / 60, abs=0.5)
    _assert_interlock(relays)


async def test_offline_countdown_also_blocks(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """A configured countdown that is offline counts as well."""
    hass.states.async_set("countdown.close", "unavailable")
    await hass.async_block_till_done()
    assert not panel_of(relay_site).driver.available
    relays.log.clear()
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 5}, blocking=True)
    await run(hass, freezer, 60, step=1)
    assert relays.log == []


async def test_buttons_while_offline_raise_a_translated_error(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """Home now and calibration start tell the user (a toast), do nothing."""
    from homeassistant.exceptions import HomeAssistantError

    hass.states.async_set("relay.close", "unavailable")
    await hass.async_block_till_done()
    relays.log.clear()
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.panel_1_home_now"}, blocking=True
        )
    assert err.value.translation_key == "relays_unavailable"
    assert err.value.translation_placeholders["entities"] == "relay.close"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.panel_1_travel_calibration_start"},
            blocking=True,
        )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "calibrate_travel",
            {"entity_id": CURRENT, "action": "start"},
            blocking=True,
        )
    await run(hass, freezer, 5)
    assert relays.log == []
    assert panel_of(relay_site).driver.calibration is None


async def test_travel_dialog_while_offline_shows_an_error(
    hass: HomeAssistant, relay_site, relays
) -> None:
    """The guided calibration stays on its first form with a clear error."""
    hass.states.async_set("relay.open", "unavailable")
    await hass.async_block_till_done()
    sub = next(iter(relay_site.subentries.values()))
    result = await relay_site.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    configure = hass.config_entries.subentries.async_configure
    result = await configure(result["flow_id"], {"next_step_id": "travel"})
    result = await configure(result["flow_id"], {"homing_seconds": 10})
    assert result["step_id"] == "travel"
    assert result["errors"] == {"base": "relays_unavailable"}
    assert result["description_placeholders"]["entities"] == "relay.open"


async def test_relay_going_offline_mid_run(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """Gone during a run: stop, mark uncertain, no fault spam, home when back."""
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 50}, blocking=True)
    await run(hass, freezer, 3)
    assert relays.on("relay.open")
    hass.states.async_set("relay.close", "unavailable")
    await run(hass, freezer, 2)
    driver = panel_of(relay_site).driver
    assert driver.uncertain
    assert not relays.on("relay.open")
    assert driver.fault is None
    relays.log.clear()
    await run(hass, freezer, 120, step=2)
    assert relays.log == [], (relays.log, driver.fault, driver.unavailable)
    hass.states.async_set("relay.close", "off")
    await run(hass, freezer, 60, step=0.25)
    seq = relays.sequence()
    assert ("relay.close", "on") in seq  # homes first (uncertain)
    assert not driver.uncertain
    _assert_interlock(relays)


async def test_already_off_counts_as_confirmed(
    hass: HomeAssistant, relay_site, relays, freezer
) -> None:
    """The other relay is already off: no wait for a state change."""
    relays.ignore.add("relay.close")  # a turn_off would never produce an event
    relays.log.clear()
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 50}, blocking=True)
    await run(hass, freezer, 2)
    off = [t for t, a in relays.calls("relay.close") if a == "off"]
    on = [t for t, a in relays.calls("relay.open") if a == "on"]
    assert off and on
    assert on[0] - off[0] < 1.5  # interlock pause only, not the 5 s timeout
    assert panel_of(relay_site).driver.fault is None


async def test_faults_back_off(
    hass: HomeAssistant, setup_site, relays, freezer
) -> None:
    """A relay that never confirms is retried after 1, 2, 4... minutes."""
    relays.ignore.add("relay.open")
    entry = await setup_site(panels=[{**RELAY_PANEL}])
    await run(hass, freezer, 30, step=0.5)
    driver = panel_of(entry).driver
    assert driver.fault is not None

    def tries() -> int:
        return sum(1 for _t, e, a in relays.log if (e, a) == ("relay.open", "on"))

    first = tries()
    await run(hass, freezer, 40, step=1)
    assert tries() == first  # backing off
    await run(hass, freezer, 60, step=1)
    assert tries() == first + 1  # retried after the first back-off
    await run(hass, freezer, 100, step=1)
    assert tries() == first + 1  # now waiting 2 minutes


async def test_no_stuck_warning_without_a_reading(
    hass: HomeAssistant, setup_site, cover, freezer, caplog
) -> None:
    """An offline cover gives no 'did not reach ... (at None)' warning."""
    entry = await setup_site()
    hass.states.async_set("cover.panel", "unavailable")
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 40}, blocking=True)
    await run(hass, freezer, 900, step=30)
    assert "did not reach" not in caplog.text
    panel = panel_of(entry)
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"actuator_stuck_{panel.id}") is None
    )
