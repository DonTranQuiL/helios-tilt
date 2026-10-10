"""Two relays (open + close) driving a dumb linear actuator by time.

The actuator has no position feedback, only internal limit switches. The
position is estimated from how long each relay was on, and re-synced by
driving into an end stop now and then (homing).

Safety rules, in order of importance:

* Never both relays on. The opposite relay is always switched off (and its
  off state confirmed) before one is switched on, with a short interlock pause,
  and a longer dead time when the direction changes.
* Every run is time-limited: by our own timer, by the relay's countdown when
  the device has one (a hardware fail-safe that works even if Home Assistant
  stops), and by a maximum continuous run time.
* If a relay doesn't confirm a command, both relays are switched off and the
  position is marked uncertain.
* Nothing is attempted while a relay (or a configured countdown) is
  unavailable, e.g. a Zigbee device that is offline. Faults back off.

The timing math is in plain functions at the top so it can be tested alone.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import HOME_CLOSED, HOME_NEAREST, HOME_OPEN, LOGGER

OPEN = 1
CLOSE = -1
END_ZONE = 2.0  # % stroke: a target this close to an end drives into the end stop
INTERLOCK_DELAY = 0.3  # s between "other relay off" and "this relay on"
CONFIRM_TIMEOUT = 5.0  # s for a relay to report the state we asked for
COUNTDOWN_MARGIN = 2.0  # s added to the hardware countdown
COUNTDOWN_MAX = 43200  # s, Tuya countdown limit
CALIBRATION_MAX = 300.0  # s, longest a calibration run may take
BACKOFF_FIRST = 60.0  # s before retrying after a fault, doubling each time
BACKOFF_MAX = 1800.0


class RelayFault(Exception):
    """A relay did not do what it was told."""


class RelayUnavailable(RelayFault):
    """A relay or countdown entity is unavailable (device offline?)."""

    def __init__(self, entities: list[str]) -> None:
        """Name the unavailable entities."""
        super().__init__(", ".join(entities) + " unavailable")
        self.entities = entities


@dataclass(frozen=True, slots=True)
class RelayConfig:
    """How the two relays and the actuator behave."""

    open_switch: str
    close_switch: str
    open_countdown: str | None = None
    close_countdown: str | None = None
    open_time: float = 30.0  # s for a full stroke, closed -> open
    close_time: float = 30.0  # s for a full stroke, open -> closed
    start_delay: float = 0.0  # s the motor needs before it moves
    home_overrun: float = 15.0  # % of the full travel time past an end stop
    reverse_delay: float = 1.0  # s of dead time before changing direction
    home_after_moves: int = 20  # home again after this many moves (0 = never)
    home_end: str = HOME_CLOSED
    interlock_delay: float = INTERLOCK_DELAY
    confirm_timeout: float = CONFIRM_TIMEOUT

    def full_time(self, direction: int) -> float:
        """Seconds for a full stroke in a direction."""
        return self.open_time if direction == OPEN else self.close_time

    @property
    def max_run(self) -> float:
        """Longest any relay may stay on in one go (a homing run plus slack)."""
        longest = max(self.open_time, self.close_time)
        return longest * (1.0 + self.home_overrun / 100.0) + self.start_delay + 5.0

    def switch(self, direction: int) -> str:
        """The relay for a direction."""
        return self.open_switch if direction == OPEN else self.close_switch

    def countdown(self, direction: int) -> str | None:
        """The countdown number for a direction, if any."""
        return self.open_countdown if direction == OPEN else self.close_countdown


@dataclass(frozen=True, slots=True)
class RunPlan:
    """One relay run."""

    direction: int  # OPEN or CLOSE
    seconds: float  # how long the relay stays on
    end: float  # stroke % when done
    homing: bool  # drives into an end stop (re-syncs the position)


def snap_to_end(target: float) -> float:
    """Targets within END_ZONE of an end go all the way to that end."""
    if target <= END_ZONE:
        return 0.0
    if target >= 100.0 - END_ZONE:
        return 100.0
    return target


def plan_run(start: float | None, target: float, cfg: RelayConfig) -> RunPlan | None:
    """How to get from `start` to `target` (stroke %, 0 = closed, 100 = open).

    A target at (or within END_ZONE of) an end drives into the end stop and
    on for `home_overrun` % of the full travel time, so drift is cancelled.
    With an unknown start only an end can be reached, by a full homing run.
    Returns None when there is nothing to do.
    """
    target = snap_to_end(max(0.0, min(100.0, target)))
    homing = target in (0.0, 100.0)
    if start is None:
        if not homing:
            return None  # can't reach a mid position from an unknown one
        direction = OPEN if target == 100.0 else CLOSE
        full = cfg.full_time(direction)
        seconds = full * (1.0 + cfg.home_overrun / 100.0) + cfg.start_delay
        return RunPlan(direction, min(seconds, cfg.max_run), target, True)
    distance = target - start
    if abs(distance) < 0.05 and not homing:
        return None
    direction = OPEN if distance > 0 or (distance == 0 and target == 100.0) else CLOSE
    full = cfg.full_time(direction)
    seconds = abs(distance) / 100.0 * full + cfg.start_delay
    if homing:
        seconds += full * cfg.home_overrun / 100.0
    return RunPlan(direction, min(seconds, cfg.max_run), target, homing)


def position_after(
    start: float, direction: int, elapsed: float, cfg: RelayConfig
) -> float:
    """Stroke % after a relay was on for `elapsed` seconds."""
    moving = max(0.0, elapsed - cfg.start_delay)
    full = cfg.full_time(direction)
    moved = 100.0 if full <= 0 else moving / full * 100.0
    return max(0.0, min(100.0, start + direction * moved))


def home_target(position: float | None, cfg: RelayConfig) -> float:
    """Which end to home against."""
    if cfg.home_end == HOME_OPEN:
        return 100.0
    if cfg.home_end == HOME_NEAREST and position is not None and position >= 50.0:
        return 100.0
    return 0.0


def countdown_seconds(remaining: float) -> int:
    """Hardware countdown for a run: the rest of it plus a margin, whole seconds."""
    return max(1, min(COUNTDOWN_MAX, math.ceil(remaining + COUNTDOWN_MARGIN)))


@dataclass(slots=True)
class _Run:
    direction: int
    start: datetime
    from_pos: float | None
    plan: RunPlan | None  # None for an external run or calibration


class RelayDriver:
    """Drives one actuator through two relays and keeps the position estimate."""

    def __init__(
        self,
        hass: HomeAssistant,
        cfg: RelayConfig,
        name: str,
        on_change: Callable[[], None],
        on_external: Callable[[int], None],
        on_persist: Callable[[], None],
        on_fault: Callable[[str | None], None],
        on_availability: Callable[[list[str]], None] | None = None,
    ) -> None:
        """Set up; call async_start once Home Assistant runs."""
        self.hass = hass
        self.cfg = cfg
        self.name = name
        self._on_change = on_change
        self._on_external = on_external
        self._on_persist = on_persist
        self._on_fault = on_fault
        self._on_availability = on_availability or (lambda _missing: None)
        # persisted
        self.position: float | None = None  # stroke %, 0 = closed
        self.uncertain = True
        self.moves_since_home = 0
        self.travel_since_home = 0.0  # % of stroke
        self.in_motion = False
        self.last_homed: datetime | None = None
        # runtime
        self.fault: str | None = None
        self.calibration: dict[str, Any] | None = None
        self._run: _Run | None = None
        self._external: _Run | None = None
        self._task: asyncio.Task[None] | None = None
        self._expect: dict[str, str] = {}
        self._last_stop: datetime | None = None
        self._last_direction = 0
        self._unsubs: list[CALLBACK_TYPE] = []
        self._cap_unsub: CALLBACK_TYPE | None = None
        self._mark: asyncio.Future[None] | None = None
        self.unavailable: list[str] = []  # entities offline right now
        self._fault_count = 0
        self.retry_after: datetime | None = None  # back off after a fault

    # ---- persistence ------------------------------------------------------------

    def store_data(self) -> dict[str, Any]:
        """What survives a restart."""
        return {
            "position": None if self.position is None else round(self.position, 2),
            "uncertain": self.uncertain,
            "moves_since_home": self.moves_since_home,
            "travel_since_home": round(self.travel_since_home, 1),
            "in_motion": self.in_motion,
            "last_homed": self.last_homed.isoformat() if self.last_homed else None,
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Load the last estimate. A restart mid-move makes it uncertain."""
        position = data.get("position")
        self.position = None if position is None else float(position)
        self.uncertain = bool(data.get("uncertain", True)) or self.position is None
        self.moves_since_home = int(data.get("moves_since_home", 0))
        self.travel_since_home = float(data.get("travel_since_home", 0.0))
        if data.get("in_motion"):
            LOGGER.warning(
                "%s: Home Assistant stopped while the actuator was moving; "
                "the position is uncertain until the next homing run",
                self.name,
            )
            self.uncertain = True
        self.in_motion = False
        if homed := data.get("last_homed"):
            self.last_homed = dt_util.parse_datetime(homed)

    # ---- state ------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        """A run (ours, external or calibration) is going on."""
        return (
            self._run is not None
            or self._external is not None
            or (self._task is not None and not self._task.done())
        )

    @property
    def calibrating(self) -> bool:
        """A travel calibration is running."""
        return self.calibration is not None and self.calibration["phase"] != "done"

    @property
    def needs_home(self) -> bool:
        """Home before the next move: uncertain, or drift may have built up."""
        if self.uncertain or self.position is None:
            return True
        limit = self.cfg.home_after_moves
        return bool(limit) and self.moves_since_home >= limit

    def current_position(self, now: datetime | None = None) -> float | None:
        """Estimated stroke % right now (also during a run)."""
        run = self._run or self._external
        if run is None or run.from_pos is None:
            return self.position if run is None else None
        elapsed = ((now or dt_util.utcnow()) - run.start).total_seconds()
        return position_after(run.from_pos, run.direction, elapsed, self.cfg)

    @property
    def direction(self) -> int:
        """Direction of the current run (0 = still)."""
        run = self._run or self._external
        return run.direction if run else 0

    @property
    def entities(self) -> list[str]:
        """Every entity the driver uses."""
        return [
            e
            for e in (
                self.cfg.open_switch,
                self.cfg.close_switch,
                self.cfg.open_countdown,
                self.cfg.close_countdown,
            )
            if e
        ]

    def missing(self) -> list[str]:
        """Entities that can't be used now (offline, unknown, or not there)."""
        out = []
        for entity_id in self.entities:
            state = self.hass.states.get(entity_id)
            bad = (STATE_UNAVAILABLE,)
            if entity_id in (self.cfg.open_switch, self.cfg.close_switch):
                bad = (STATE_UNAVAILABLE, STATE_UNKNOWN)  # can't confirm a state
            if state is None or state.state in bad:
                out.append(entity_id)
        return out

    @property
    def available(self) -> bool:
        """Both relays (and the countdowns) can be used."""
        return not self.unavailable

    def backing_off(self, now: datetime | None = None) -> bool:
        """A recent fault: automatic moves wait a while."""
        return self.retry_after is not None and (now or dt_util.utcnow()) < (
            self.retry_after
        )

    @callback
    def async_check_available(self) -> bool:
        """Re-read availability; tell the controller when it changed."""
        missing = self.missing()
        if missing != self.unavailable:
            if missing:
                for entity_id in missing:
                    if entity_id not in self.unavailable:
                        LOGGER.warning(
                            "%s: relay %s is unavailable (Zigbee device offline?); "
                            "no runs until it is back",
                            self.name,
                            entity_id,
                        )
            else:
                LOGGER.info("%s: relays available again", self.name)
                self.retry_after = None
                self._fault_count = 0
            self.unavailable = missing
            self._on_availability(missing)
        return not missing

    def _require_available(self) -> None:
        if not self.async_check_available():
            raise RelayUnavailable(self.unavailable)

    def set_position(self, position: float) -> None:
        """The user says where it is (calibrate)."""
        self.position = max(0.0, min(100.0, position))
        self.uncertain = False
        self.moves_since_home = 0
        self.travel_since_home = 0.0
        self._on_persist()

    # ---- lifecycle --------------------------------------------------------------

    async def async_start(self) -> None:
        """Watch the relays; switch them off if anything is on."""
        self._unsubs.append(
            async_track_state_change_event(
                self.hass,
                [self.cfg.open_switch, self.cfg.close_switch],
                self._async_relay_changed,  # type: ignore[arg-type]
            )
        )
        self._unsubs.append(
            async_track_state_change_event(
                self.hass,
                self.entities,
                self._async_entity_changed,  # type: ignore[arg-type]
            )
        )
        self.async_check_available()
        if self._is_on(self.cfg.open_switch) or self._is_on(self.cfg.close_switch):
            LOGGER.warning("%s: a relay was on at start; switching both off", self.name)
            self.uncertain = True
            await self._async_all_off()

    async def async_shutdown(self) -> None:
        """Stop everything (Home Assistant stops or the entry unloads)."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._cancel_cap()
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.wait([task])
        moving = self._run is not None or self._external is not None
        if moving:
            self._finish_run(dt_util.utcnow(), uncertain=True)
        self._external = None
        await self._async_all_off()
        self.in_motion = False

    # ---- moving -------------------------------------------------------------------

    @callback
    def async_request(self, target: float, home_first: bool = False) -> None:
        """Drive to a stroke %; replaces any run in progress."""
        self._replace_task(self._async_go(target, home_first), "move")

    @callback
    def async_home(self, then: float | None) -> None:
        """Drive into the home end stop, then on to `then` (if given)."""
        self._replace_task(self._async_go(then, True), "home")

    def _replace_task(self, coro: Any, what: str) -> None:
        old = self._task
        self._task = self.hass.async_create_background_task(
            self._async_after(old, coro), f"helios_tilt {self.name} {what}"
        )
        # Replaced before it started: don't leave the coroutine un-awaited.
        self._task.add_done_callback(lambda _task: coro.close())

    async def _async_after(self, old: asyncio.Task[None] | None, coro: Any) -> None:
        if old is not None and not old.done():
            old.cancel()
            await asyncio.wait([old])
        await coro

    async def _async_go(self, target: float | None, home_first: bool) -> None:
        try:
            self._require_available()
            if self._external is not None:
                await self._async_stop_external()
            home = home_target(self.position, self.cfg)
            if (home_first or self.needs_home) and (
                target is None or snap_to_end(target) != home
            ):
                await self._async_run(home)
            elif home_first and target is not None:
                target = home  # the target is the home end: one homing run
            if target is not None:
                await self._async_run(target)
            self._clear_fault()
        except RelayUnavailable as err:
            # Logged (once) by the availability check; nothing was switched on,
            # unless it went offline mid-run.
            if self._run is not None:
                self._finish_run(dt_util.utcnow(), uncertain=True)
                await self._async_all_off()
            LOGGER.debug("%s: not moving: %s", self.name, err)
        except RelayFault as err:
            LOGGER.error("%s: %s; both relays switched off", self.name, err)
            self._finish_run(dt_util.utcnow(), uncertain=True)
            await self._async_all_off()
            self._set_fault(str(err))
        except asyncio.CancelledError:
            if self._run is not None:
                self._finish_run(dt_util.utcnow(), uncertain=False)
            await self._async_all_off()
            await self._async_disarm_all()
            raise
        finally:
            self._on_change()

    def _set_fault(self, fault: str) -> None:
        self.fault = fault
        delay = min(BACKOFF_MAX, BACKOFF_FIRST * 2**self._fault_count)
        self._fault_count += 1
        self.retry_after = dt_util.utcnow() + timedelta(seconds=delay)
        self._on_fault(fault)

    def _clear_fault(self) -> None:
        self._fault_count = 0
        self.retry_after = None
        if self.fault is not None:
            self.fault = None
            self._on_fault(None)

    async def _async_run(self, target: float) -> None:
        plan = plan_run(self.position, target, self.cfg)
        if plan is None:
            return
        relay = self.cfg.switch(plan.direction)
        await self._async_prepare(plan.direction)
        self.in_motion = True
        self._on_persist()
        self._run = _Run(plan.direction, dt_util.utcnow(), self.position, plan)
        self._on_change()
        await self._async_set(relay, True)
        await self._async_arm_countdown(plan.direction, plan.seconds)
        remaining = plan.seconds - self._elapsed()
        if remaining > 0:
            await self._sleep(remaining)
        await self._async_set(relay, False)
        self._finish_run(dt_util.utcnow(), uncertain=False)
        await self._async_disarm_countdown(plan.direction)

    async def _async_prepare(self, direction: int) -> None:
        """Interlock: the opposite relay off (confirmed), then the dead time."""
        other = self.cfg.switch(-direction)
        await self._async_set(other, False)
        wait = self.cfg.interlock_delay
        if self._last_stop is not None and self._last_direction not in (0, direction):
            since = (dt_util.utcnow() - self._last_stop).total_seconds()
            wait = max(wait, self.cfg.reverse_delay - since)
        if wait > 0:
            await self._sleep(wait)
        if self._is_on(other):
            raise RelayFault(f"{other} is still on")

    def _elapsed(self) -> float:
        assert self._run is not None
        return (dt_util.utcnow() - self._run.start).total_seconds()

    def _finish_run(self, now: datetime, uncertain: bool) -> None:
        """Book a run that ended (normally or not) into the estimate."""
        run, self._run = self._run, None
        if run is None:
            run, self._external = self._external, None
        if run is None:
            self.in_motion = False
            return
        elapsed = (now - run.start).total_seconds()
        complete = (
            run.plan is not None
            and not uncertain
            and elapsed >= run.plan.seconds - 0.05
        )
        full_run = elapsed >= self.cfg.full_time(run.direction) + self.cfg.start_delay
        end = 100.0 if run.direction == OPEN else 0.0
        if complete:
            assert run.plan is not None
            new = run.plan.end
        elif full_run:
            new = end  # long enough to reach the end stop from anywhere
        elif run.from_pos is not None:
            new = position_after(run.from_pos, run.direction, elapsed, self.cfg)
        else:
            new = None
        homed = new == end and (full_run or (complete and run.plan.homing))  # type: ignore[union-attr]
        if new is not None and run.from_pos is not None:
            self.travel_since_home += abs(new - run.from_pos)
        self.moves_since_home += 1
        self.position = new
        if homed:
            self.uncertain = False
            self.moves_since_home = 0
            self.travel_since_home = 0.0
            self.last_homed = now
        elif new is None or uncertain:
            self.uncertain = True
        self.in_motion = False
        self._last_stop = now
        self._last_direction = run.direction
        self._on_persist()

    # ---- relays -------------------------------------------------------------------

    def _is_on(self, entity_id: str) -> bool:
        state = self.hass.states.get(entity_id)
        return state is not None and state.state == STATE_ON

    async def _async_set(self, entity_id: str, on: bool) -> None:
        """Switch a relay and wait until it reports that state."""
        want = STATE_ON if on else STATE_OFF
        self._expect[entity_id] = want
        try:
            await self.hass.services.async_call(
                entity_id.split(".", 1)[0],
                "turn_on" if on else "turn_off",
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
        except Exception as err:  # the switch's own error  # noqa: BLE001
            raise RelayFault(f"{entity_id} refused turn_{want}: {err}") from err
        if not await self._async_wait_state(entity_id, want):
            if not self.async_check_available():
                raise RelayUnavailable(self.unavailable)
            raise RelayFault(f"{entity_id} did not confirm {want}")

    async def _async_wait_state(self, entity_id: str, want: str) -> bool:
        state = self.hass.states.get(entity_id)
        if state is not None and state.state == want:
            return True
        done: asyncio.Future[bool] = self.hass.loop.create_future()

        @callback
        def _changed(event: Event) -> None:
            new: State | None = event.data.get("new_state")
            if new is not None and new.state == want and not done.done():
                done.set_result(True)

        @callback
        def _timeout(_now: datetime) -> None:
            if not done.done():
                done.set_result(False)

        unsub = async_track_state_change_event(self.hass, [entity_id], _changed)
        cancel = async_call_later(self.hass, self.cfg.confirm_timeout, _timeout)
        try:
            return await done
        finally:
            unsub()
            cancel()

    async def _async_all_off(self) -> None:
        """Both relays off, best effort (never raises)."""
        for entity_id in (self.cfg.open_switch, self.cfg.close_switch):
            self._expect[entity_id] = STATE_OFF
            try:
                await self.hass.services.async_call(
                    entity_id.split(".", 1)[0],
                    "turn_off",
                    {ATTR_ENTITY_ID: entity_id},
                    blocking=True,
                )
            except Exception as err:  # noqa: BLE001
                LOGGER.error(
                    "%s: could not switch %s off: %s", self.name, entity_id, err
                )

    async def _async_arm_countdown(self, direction: int, seconds: float) -> None:
        """Hardware fail-safe: the relay switches itself off after the run.

        Tuya countdowns toggle the relay once the time is up, so it is set
        right after the relay confirmed on (set while off, it would switch the
        relay on later).
        """
        entity_id = self.cfg.countdown(direction)
        if not entity_id:
            return
        remaining = seconds - self._elapsed() if self._run else seconds
        await self._async_set_number(entity_id, countdown_seconds(remaining))

    async def _async_disarm_countdown(self, direction: int) -> None:
        """Clear a countdown that is still running (it would switch back on)."""
        entity_id = self.cfg.countdown(direction)
        if not entity_id:
            return
        state = self.hass.states.get(entity_id)
        if state is not None and state.state in ("0", "0.0"):
            return
        await self._async_set_number(entity_id, 0)

    async def _async_disarm_all(self) -> None:
        for direction in (OPEN, CLOSE):
            await self._async_disarm_countdown(direction)

    async def _async_set_number(self, entity_id: str, value: float) -> None:
        try:
            await self.hass.services.async_call(
                entity_id.split(".", 1)[0],
                "set_value",
                {ATTR_ENTITY_ID: entity_id, "value": value},
                blocking=True,
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("%s: could not set %s: %s", self.name, entity_id, err)

    async def _sleep(self, seconds: float) -> None:
        """Wait on Home Assistant's clock (testable, cancellable)."""
        done: asyncio.Future[None] = self.hass.loop.create_future()

        @callback
        def _wake(_now: datetime) -> None:
            if not done.done():
                done.set_result(None)

        cancel = async_call_later(self.hass, seconds, _wake)
        try:
            await done
        finally:
            cancel()

    # ---- relays switched by someone else -------------------------------------------

    @callback
    def _async_entity_changed(self, event: Event) -> None:
        """Availability of a relay or countdown changed?"""
        was = self.available
        now = self.async_check_available()
        if was and not now and (self._run is not None or self.calibrating):
            # Gone mid-run: stop (best effort) and distrust the estimate.
            self._replace_task(self._async_offline_stop(), "offline")

    async def _async_offline_stop(self) -> None:
        if self._run is not None or self._external is not None:
            self._finish_run(dt_util.utcnow(), uncertain=True)
        self.calibration = None
        self.uncertain = True
        await self._async_all_off()
        self._on_persist()
        self._on_change()

    @callback
    def _async_relay_changed(self, event: Event) -> None:
        entity_id: str = event.data["entity_id"]
        new: State | None = event.data.get("new_state")
        if new is None or new.state not in (STATE_ON, STATE_OFF):
            return
        expected = self._expect.get(entity_id)
        if expected == new.state:
            return  # what we asked for
        self._expect.pop(entity_id, None)
        if self._is_on(self.cfg.open_switch) and self._is_on(self.cfg.close_switch):
            LOGGER.error("%s: both relays on; switching both off", self.name)
            self.uncertain = True
            self._replace_task(self._async_interlock_trip(), "interlock")
            return
        direction = OPEN if entity_id == self.cfg.open_switch else CLOSE
        if new.state == STATE_ON:
            self._external_started(direction, new.last_changed)
        else:
            self._external_stopped(direction, new.last_changed)

    async def _async_interlock_trip(self) -> None:
        self._finish_run(dt_util.utcnow(), uncertain=True)
        self._cancel_cap()
        self.calibration = None
        await self._async_all_off()
        await self._async_disarm_all()
        self.uncertain = True
        self._on_persist()
        self._on_change()

    def _external_started(self, direction: int, when: datetime) -> None:
        if (
            self._run is not None
            or self.calibrating
            or (self._task is not None and not self._task.done())
        ):
            # Someone else switched a relay during our run: stop everything.
            LOGGER.warning("%s: relay switched on during a run; stopping", self.name)
            self._replace_task(self._async_interlock_trip(), "interlock")
            return
        LOGGER.info(
            "%s: %s switched on outside Helios Tilt (wall switch or remote?)",
            self.name,
            self.cfg.switch(direction),
        )
        self._external = _Run(direction, when, self.position, None)
        self.in_motion = True
        self._on_persist()
        self._cancel_cap()
        self._cap_unsub = async_call_later(
            self.hass, self.cfg.max_run, self._async_cap_reached
        )
        self._on_external(direction)
        self._on_change()

    def _external_stopped(self, direction: int, when: datetime) -> None:
        if self._run is not None and self._run.direction == direction:
            # Our relay went off early (countdown, remote, power): book it.
            LOGGER.info("%s: relay switched off before the run ended", self.name)
            task = self._task
            self._finish_run(when, uncertain=False)
            if task is not None and not task.done():
                task.cancel()
            self._on_change()
            return
        if self._external is None or self._external.direction != direction:
            return
        self._cancel_cap()
        self._finish_run(when, uncertain=False)
        self._on_change()

    async def _async_stop_external(self) -> None:
        self._cancel_cap()
        self._finish_run(dt_util.utcnow(), uncertain=False)
        await self._async_all_off()

    @callback
    def _async_cap_reached(self, _now: datetime) -> None:
        self._cap_unsub = None
        LOGGER.warning(
            "%s: a relay was on for over %.0f s; switching it off",
            self.name,
            self.cfg.max_run,
        )
        self._replace_task(self._async_stop_external(), "cap")

    def _cancel_cap(self) -> None:
        if self._cap_unsub is not None:
            self._cap_unsub()
            self._cap_unsub = None

    # ---- travel calibration -----------------------------------------------------------

    @callback
    def async_calibration_start(self, homing_seconds: float) -> None:
        """Close fully, then open while the user times it (see async_calibration_mark)."""
        self.calibration = {
            "phase": "homing",
            "homing_seconds": round(homing_seconds, 1),
            "open_time": None,
            "close_time": None,
            "phase_started": dt_util.utcnow().isoformat(),
        }
        self._replace_task(self._async_calibrate(homing_seconds), "calibration")
        self._on_change()

    @callback
    def async_calibration_mark(self) -> bool:
        """The user saw the end stop. False if nothing is being timed."""
        if (
            self.calibration is None
            or self.calibration["phase"] not in ("opening", "closing")
            or self._mark is None
            or self._mark.done()
        ):
            return False
        started = dt_util.parse_datetime(self.calibration["timing_started"])
        assert started is not None
        key = "open_time" if self.calibration["phase"] == "opening" else "close_time"
        self.calibration[key] = round((dt_util.utcnow() - started).total_seconds(), 1)
        self._mark.set_result(None)
        return True

    @callback
    def async_calibration_cancel(self) -> None:
        """Stop the calibration and both relays."""
        if self.calibration is None:
            return
        self.calibration = None
        self.uncertain = True
        self._replace_task(self._async_stop_all(), "calibration cancel")

    async def _async_stop_all(self) -> None:
        self._run = None
        self._external = None
        self.in_motion = False
        await self._async_all_off()
        self._on_persist()
        self._on_change()

    async def _async_calibrate(self, homing_seconds: float) -> None:
        cal = self.calibration
        assert cal is not None
        try:
            self._require_available()
            if self._external is not None:
                await self._async_stop_external()
            # 1. Home: close for the given time (past the end stop).
            await self._async_timed(CLOSE, homing_seconds)
            self.position, self.uncertain = 0.0, False
            # 2. Open while the user watches; 3. close again.
            for phase, direction, key in (
                ("opening", OPEN, "open_time"),
                ("closing", CLOSE, "close_time"),
            ):
                cal["phase"] = phase
                cal.pop("timing_started", None)
                cal["phase_started"] = dt_util.utcnow().isoformat()
                self._on_change()
                measured = await self._async_timed(direction, None)
                cal[key] = cal.get(key) or measured
            cal["phase"] = "done"
            self.position = 0.0
            self.uncertain = False
            self.moves_since_home = 0
            self.travel_since_home = 0.0
            self.last_homed = dt_util.utcnow()
            self._on_persist()
        except RelayUnavailable as err:
            LOGGER.warning("%s: calibration not possible: %s", self.name, err)
            if self.calibration is cal:
                self.calibration = None
            if self._run is not None:
                self.uncertain = True
                await self._async_all_off()
        except RelayFault as err:
            LOGGER.error("%s: calibration stopped: %s", self.name, err)
            if self.calibration is cal:
                self.calibration = None
            self.uncertain = True
            await self._async_all_off()
            await self._async_disarm_all()
        except asyncio.CancelledError:
            if self.calibration is cal:
                self.calibration = None
            self.uncertain = True
            await self._async_all_off()
            await self._async_disarm_all()
            raise
        finally:
            self._run = None
            self.in_motion = False
            self._mark = None
            self._on_change()

    async def _async_timed(self, direction: int, seconds: float | None) -> float:
        """Run one relay for `seconds`, or until the user marks the end.

        Returns the measured seconds from the relay confirming on.
        """
        relay = self.cfg.switch(direction)
        await self._async_prepare(direction)
        limit = seconds if seconds is not None else CALIBRATION_MAX
        self.in_motion = True
        self._run = _Run(direction, dt_util.utcnow(), None, None)
        await self._async_set(relay, True)
        started = dt_util.utcnow()
        await self._async_arm_countdown(direction, limit)
        if seconds is None:
            assert self.calibration is not None
            self.calibration["timing_started"] = started.isoformat()
            self._mark = self.hass.loop.create_future()
            waiter = asyncio.ensure_future(self._sleep(limit))
            try:
                await asyncio.wait(
                    [self._mark, waiter], return_when=asyncio.FIRST_COMPLETED
                )
            finally:
                waiter.cancel()
            timed_out = not self._mark.done()
            self._mark = None
            if timed_out:
                await self._async_set(relay, False)
                raise RelayFault(f"no end reached within {limit:.0f} s")
        else:
            await self._sleep(
                max(0.0, limit - (dt_util.utcnow() - started).total_seconds())
            )
        measured = (dt_util.utcnow() - started).total_seconds()
        await self._async_set(relay, False)
        self._run = None
        self._last_stop = dt_util.utcnow()
        self._last_direction = direction
        await self._async_disarm_countdown(direction)
        return round(measured, 1)
