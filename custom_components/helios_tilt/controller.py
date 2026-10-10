"""The site controller: reads the weather, runs safety and strategies, moves panels."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, fields
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_LOGBOOK_ENTRY,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import SpeedConverter, TemperatureConverter

from .actuator import AngleMapping, estimate_angle, travel_seconds
from .const import (
    ACTUATOR_RELAYS,
    CONF_CALM_MINUTES,
    CONF_CLOUD_THRESHOLD,
    CONF_DEADBAND,
    CONF_DIRECTION_RULE,
    CONF_DIRECTION_SECTOR,
    CONF_DIRECTION_SENSOR,
    CONF_DIRECTION_SIDES,
    CONF_FROST_MODE,
    CONF_FROST_TEMP,
    CONF_HYSTERESIS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MANUAL_PAUSE,
    CONF_MIN_INTERVAL,
    CONF_QUIET_END,
    CONF_QUIET_SAFETY,
    CONF_QUIET_START,
    CONF_RAIN_MODE,
    CONF_RAIN_SENSOR,
    CONF_RAIN_THRESHOLD,
    CONF_SNOW_MODE,
    CONF_SNOW_SENSOR,
    CONF_SNOW_THRESHOLD,
    CONF_STALE_MINUTES,
    CONF_STORM_HOLD,
    CONF_STORM_SPEED,
    CONF_TEMP_SENSOR,
    CONF_TRIGGER_ANGLE,
    CONF_TRIGGERS,
    CONF_WEATHER,
    CONF_WIND_RESUME,
    CONF_WIND_SENSOR,
    CONF_WIND_STOW,
    DOMAIN,
    EVENT_MOVE,
    FEEDBACK_ANGLE,
    LOGGER,
    MAPPING_TABLE,
    MODE_AUTO,
    MODE_MANUAL,
    PANEL_DEFAULTS,
    REASON_CALIBRATE,
    REASON_DIFFUSE,
    REASON_FROST,
    REASON_MANUAL,
    REASON_NIGHT,
    REASON_QUIET,
    REASON_RAIN,
    REASON_SNOW,
    REASON_STORM,
    REASON_STOW,
    REASON_STRATEGY,
    REASON_TRIGGER,
    REASON_WIND,
    SIDES_FRONT,
    SIDES_REAR,
    SITE_DEFAULTS,
    STORE_VERSION,
    STRATEGY_DAILY,
    STRATEGY_FIXED,
    STRATEGY_SEASONAL,
    STRATEGY_TRACKING,
    SUBENTRY_PANEL,
    TICK_SECONDS,
)
from .engine import (
    PanelGeometry,
    annual_optimum,
    daily_optimum,
    is_night,
    round_to_step,
    seasonal_angle,
    tracking_target,
)
from .relays import RelayConfig, RelayDriver
from .safety import (
    FROST,
    RAIN,
    SNOW,
    STORM,
    TRIGGER,
    UNTIL_CLEARED,
    WIND,
    Readings,
    SafetyEngine,
    SafetySettings,
    SafetyState,
)
from .solar import SunPosition, plane_irradiance, sun_position

COVER_MOVING = ("opening", "closing")
MANUAL_TOLERANCE = 3.0  # degrees between expected and reported angle
SETTLE_GRACE = timedelta(seconds=30)
HISTORY_LEN = 10
REFRESH_WHILE_MOVING = timedelta(seconds=2)
REASON_TEXT = {
    REASON_STRATEGY: "{strategy}",
    REASON_NIGHT: "Night park",
    REASON_DIFFUSE: "Cloudy: flatter angle",
    REASON_MANUAL: "Manual",
    REASON_WIND: "Wind stow ({detail})",
    REASON_STORM: "Storm mode ({detail})",
    REASON_STOW: "Stowed by hand",
    REASON_SNOW: "Snow: shedding angle",
    REASON_RAIN: "Heavy rain",
    REASON_FROST: "Frost ({detail})",
    REASON_CALIBRATE: "Calibration",
    REASON_TRIGGER: "Stow trigger ({detail})",
    REASON_QUIET: "Quiet hours",
}
SAFETY_REASONS = (REASON_WIND, REASON_STORM, REASON_TRIGGER)
CARDINALS = {
    name: i * 22.5
    for i, name in enumerate(
        [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
    )
}
RAIN_RATE_MM_H = {"mm/h": 1.0, "mm/d": 1 / 24, "in/h": 25.4, "in/d": 25.4 / 24}
DEPTH_CM = {"cm": 1.0, "mm": 0.1, "m": 100.0, "in": 2.54, "ft": 30.48}
SOURCE_WEATHER_WIND = "weather_wind"
SOURCE_WEATHER_GUST = "weather_gust"
SOURCE_SENSOR = "wind_sensor"
STRATEGY_TEXT = {
    STRATEGY_FIXED: "Annual optimum",
    STRATEGY_SEASONAL: "Seasonal curve",
    STRATEGY_DAILY: "Daily optimum",
    STRATEGY_TRACKING: "Tracking the sun",
}


def _float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None  # NaN


def _usable(state: State | None) -> bool:
    return state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


def _bearing(value: Any) -> float | None:
    """Degrees (0 = from the north) from a number or a cardinal like 'SW'."""
    if (number := _float(value)) is not None:
        return number % 360.0
    if isinstance(value, str):
        return CARDINALS.get(value.strip().upper())
    return None


def _angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _parse_time(value: Any) -> time | None:
    if isinstance(value, time):
        return value
    if not value:
        return None
    try:
        return time.fromisoformat(str(value))
    except ValueError:
        LOGGER.warning("Invalid quiet hours time %s, ignoring it", value)
        return None


def in_window(now: time, start: time, end: time) -> bool:
    """Is `now` in [start, end)? The window may cross midnight."""
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def _converted(
    value: float, unit: str | None, table: dict[str, float], default: str
) -> float | None:
    """Value in the table's base unit, or None for an unknown unit."""
    factor = table.get((unit or default).strip().lower())
    return None if factor is None else value * factor


def _speed_kmh(value: Any, unit: str | None) -> float | None:
    speed = _float(value)
    if speed is None:
        return None
    try:
        return SpeedConverter.convert(
            speed,
            unit or UnitOfSpeed.KILOMETERS_PER_HOUR,
            UnitOfSpeed.KILOMETERS_PER_HOUR,
        )
    except Exception:  # unknown unit
        LOGGER.warning("Unknown wind speed unit %s, ignoring the reading", unit)
        return None


@dataclass(slots=True)
class PanelConfig:
    """A panel's settings (subentry data with defaults filled in)."""

    actuator_entity: str = ""
    axis: str = "tilt"
    azimuth: float = 180.0
    min_angle: float = 0.0
    max_angle: float = 60.0
    step: float = 5.0
    strategy: str = STRATEGY_DAILY
    mapping: str = "linear"
    position_at_min: float = 0.0
    position_at_max: float = 100.0
    calibration: str = ""
    feedback_entity: str | None = None
    feedback_kind: str = "position"
    travel_time: float = 60.0
    stow_angle: float = 0.0
    night_angle: float = 15.0
    diffuse_angle: float = 10.0
    snow_angle: float = 60.0
    rain_angle: float = 30.0
    frost_angle: float = 30.0
    winter_angle: float = 60.0
    summer_angle: float = 20.0
    season_weight: float = 50.0
    pv_power_entity: str | None = None
    pv_peak_power: float = 0.0
    actuator_type: str = "entity"
    open_switch: str = ""
    close_switch: str = ""
    open_countdown: str | None = None
    close_countdown: str | None = None
    open_time: float = 30.0
    close_time: float = 30.0
    angle_closed: float = 0.0
    angle_open: float = 60.0
    start_delay: float = 0.0
    home_overrun: float = 15.0
    reverse_delay: float = 1.0
    home_after_moves: int = 20
    home_at_night: bool = True
    home_end: str = "closed"

    @property
    def relays(self) -> bool:
        """Two relays (timed) instead of an entity."""
        return self.actuator_type == ACTUATOR_RELAYS

    def relay_config(self) -> RelayConfig:
        """Settings for the relay driver."""
        return RelayConfig(
            open_switch=self.open_switch,
            close_switch=self.close_switch,
            open_countdown=self.open_countdown or None,
            close_countdown=self.close_countdown or None,
            open_time=self.open_time,
            close_time=self.close_time,
            start_delay=self.start_delay,
            home_overrun=self.home_overrun,
            reverse_delay=self.reverse_delay,
            home_after_moves=int(self.home_after_moves),
            home_end=self.home_end,
        )

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> PanelConfig:
        """Build from subentry data, ignoring unknown keys."""
        merged = {**PANEL_DEFAULTS, **data}
        values: dict[str, Any] = {}
        for f in fields(cls):
            value = merged.get(f.name)
            if value is None:
                continue
            if f.type in ("float", float) and not isinstance(value, bool):
                value = float(value)
            values[f.name] = value
        if values.get("actuator_type") == ACTUATOR_RELAYS:
            # Never command (or watch) a generic actuator entity on relay panels.
            values["actuator_entity"] = ""
            values["feedback_entity"] = None
        return cls(**values)

    def build_mapping(self) -> AngleMapping:
        """Angle <-> position mapping.

        For two relays the position is the stroke in % (0 = fully closed,
        100 = fully open), linear between the angles at both ends, or from a
        table of angle:stroke% pairs.
        """
        if self.mapping == MAPPING_TABLE:
            return AngleMapping.table(self.calibration)
        if self.relays:
            points = sorted([(self.angle_closed, 0.0), (self.angle_open, 100.0)])
            return AngleMapping.linear(
                points[0][0], points[1][0], points[0][1], points[1][1]
            )
        return AngleMapping.linear(
            self.min_angle, self.max_angle, self.position_at_min, self.position_at_max
        )


@dataclass(slots=True)
class Move:
    """One entry in the move history."""

    time: datetime
    angle: float
    reason: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        """For attributes and storage."""
        return {
            "time": self.time.isoformat(),
            "angle": self.angle,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(slots=True)
class Panel:
    """Runtime state of one panel."""

    id: str
    title: str
    cfg: PanelConfig
    mapping: AngleMapping
    geometry: PanelGeometry
    # persisted
    mode: str = MODE_AUTO
    auto_enabled: bool = True
    manual_angle: float | None = None
    stowed: bool = False
    stowed_until: datetime | None = None
    commanded: float | None = None
    move_from: float | None = None
    move_started: datetime | None = None
    estimate: float | None = None
    moves_day: date | None = None
    moves_today: int = 0
    history: list[Move] = field(default_factory=list)
    manual_until: datetime | None = None
    # runtime
    target: float | None = None
    target_reason: str = REASON_STRATEGY
    target_detail: str = ""
    current: float | None = None
    current_source: str = "unknown"
    moving: bool = False
    stuck: bool = False
    fixed_angle: float | None = None
    daily: tuple[date, float] | None = None
    energy_day: date | None = None
    energy_actual: float = 0.0
    energy_fixed: float = 0.0
    energy_since: datetime | None = None
    excluded_seconds: float = 0.0
    instant_gain: float | None = None
    # The last decision followed the strategy (not safety, stow, manual,
    # diffuse, a freeze or automatic control off): only then does the
    # time until the next round count toward the gain.
    following_strategy: bool = False
    wind_exempt: bool = False  # wind direction rule: this wind passes by
    pv_actual: float | None = None
    pv_model: float | None = None
    today_curve: list[tuple[str, float]] = field(default_factory=list)
    curve_key: tuple | None = None
    expected_position: float | None = None
    user_pending: bool = False  # a user change waits for the actuator to stop
    driver: RelayDriver | None = None

    @property
    def strategy(self) -> str:
        """Strategy in use when automatic."""
        return self.cfg.strategy if self.mode in (MODE_AUTO, MODE_MANUAL) else self.mode

    @property
    def last_move(self) -> Move | None:
        """Most recent move."""
        return self.history[-1] if self.history else None

    @property
    def gain(self) -> float | None:
        """Clear-sky energy today vs a panel fixed at the annual optimum (%).

        Only time the panel followed its strategy counts: safety and manual
        stows, manual mode, diffuse parking and data freezes are left out of
        both sides, since a fixed rack would not have stowed either.
        """
        if self.energy_fixed <= 0:
            return None
        return round((self.energy_actual / self.energy_fixed - 1.0) * 100.0, 1)

    @property
    def pv_performance(self) -> float | None:
        """Actual PV power as % of the clear-sky model."""
        if self.pv_actual is None or not self.pv_model:
            return None
        if self.pv_model < 0.05 * self.cfg.pv_peak_power:
            return None
        return round(self.pv_actual / self.pv_model * 100.0, 1)

    def store_data(self) -> dict[str, Any]:
        """What survives a restart."""
        return {
            "mode": self.mode,
            "auto_enabled": self.auto_enabled,
            "manual_angle": self.manual_angle,
            "stowed": self.stowed,
            "stowed_until": self.stowed_until.isoformat()
            if self.stowed_until
            else None,
            "commanded": self.commanded,
            "estimate": self.current if self.current is not None else self.estimate,
            "moves_day": self.moves_day.isoformat() if self.moves_day else None,
            "moves_today": self.moves_today,
            "history": [m.as_dict() for m in self.history],
            "manual_until": self.manual_until.isoformat()
            if self.manual_until
            else None,
            "relay": self.driver.store_data() if self.driver else None,
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Load persisted state."""
        self.mode = data.get("mode", MODE_AUTO)
        self.auto_enabled = bool(data.get("auto_enabled", True))
        self.manual_angle = _float(data.get("manual_angle"))
        self.stowed = bool(data.get("stowed", False))
        until = data.get("stowed_until")
        self.stowed_until = dt_util.parse_datetime(until) if until else None
        self.commanded = _float(data.get("commanded"))
        self.estimate = _float(data.get("estimate"))
        self.current = self.estimate
        if day := data.get("moves_day"):
            self.moves_day = date.fromisoformat(day)
        self.moves_today = int(data.get("moves_today", 0))
        self.history = []
        for item in data.get("history", [])[-HISTORY_LEN:]:
            when = dt_util.parse_datetime(item.get("time", ""))
            if when is not None:
                self.history.append(
                    Move(
                        when,
                        float(item["angle"]),
                        item["reason"],
                        item.get("detail", ""),
                    )
                )
        if until := data.get("manual_until"):
            self.manual_until = dt_util.parse_datetime(until)
        if self.driver is not None and (relay := data.get("relay")):
            self.driver.restore(relay)


class HeliosSite:
    """Everything for one config entry (a site with one or more panels)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Set up from the config entry; call async_start next."""
        self.hass = hass
        self.entry = entry
        site = {**SITE_DEFAULTS, **entry.data, **entry.options}
        self.site = site
        self.latitude = float(site.get(CONF_LATITUDE, hass.config.latitude))
        self.longitude = float(site.get(CONF_LONGITUDE, hass.config.longitude))
        self.weather_entity: str | None = site.get(CONF_WEATHER) or None
        self.wind_sensor: str | None = site.get(CONF_WIND_SENSOR) or None
        self.safety = SafetyEngine(
            SafetySettings(
                wind_stow=float(site[CONF_WIND_STOW]),
                wind_resume=float(site[CONF_WIND_RESUME]),
                calm_minutes=float(site[CONF_CALM_MINUTES]),
                storm_speed=float(site[CONF_STORM_SPEED]),
                storm_hold_hours=float(site[CONF_STORM_HOLD]),
                stale_minutes=float(site[CONF_STALE_MINUTES]),
                snow=bool(site[CONF_SNOW_MODE]),
                rain=bool(site[CONF_RAIN_MODE]),
                frost=bool(site[CONF_FROST_MODE]),
                frost_temperature=float(site[CONF_FROST_TEMP]),
                wind_required=bool(self.weather_entity or self.wind_sensor),
            )
        )
        self.min_interval = timedelta(minutes=float(site[CONF_MIN_INTERVAL]))
        self.manual_pause = timedelta(minutes=float(site[CONF_MANUAL_PAUSE]))
        self.deadband = float(site[CONF_DEADBAND])
        self.hysteresis = float(site[CONF_HYSTERESIS])
        self.cloud_threshold = float(site[CONF_CLOUD_THRESHOLD])
        # optional dedicated sources
        self.rain_sensor: str | None = site.get(CONF_RAIN_SENSOR) or None
        self.rain_threshold = float(site[CONF_RAIN_THRESHOLD])
        self.snow_sensor: str | None = site.get(CONF_SNOW_SENSOR) or None
        self.snow_threshold = float(site[CONF_SNOW_THRESHOLD])
        self.temp_sensor: str | None = site.get(CONF_TEMP_SENSOR) or None
        # custom stow triggers
        self.triggers: list[str] = list(site.get(CONF_TRIGGERS) or [])
        angle = site.get(CONF_TRIGGER_ANGLE)
        self.trigger_angle = _float(angle) if angle not in (None, "") else None
        # quiet hours
        self.quiet_start = _parse_time(site.get(CONF_QUIET_START))
        self.quiet_end = _parse_time(site.get(CONF_QUIET_END))
        self.quiet_safety = bool(site[CONF_QUIET_SAFETY])
        self.quiet = False
        self.quiet_until: datetime | None = None
        # wind direction rule
        self.direction_rule = bool(site[CONF_DIRECTION_RULE])
        self.direction_sensor: str | None = site.get(CONF_DIRECTION_SENSOR) or None
        self.direction_sides: str = site[CONF_DIRECTION_SIDES]
        self.direction_sector = float(site[CONF_DIRECTION_SECTOR])
        self.bearing: float | None = None
        # what the readings came from (transparency attributes)
        self.sources: dict[str, Any] = {}

        self.panels: dict[str, Panel] = {}
        for subentry in entry.subentries.values():
            if subentry.subentry_type == SUBENTRY_PANEL:
                self.panels[subentry.subentry_id] = self._make_panel(subentry)

        self.readings = Readings()
        self.sun: SunPosition | None = None
        self.sun_path: list[tuple[str, float, float]] = []
        self.sun_path_day: date | None = None
        self.started = False
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._last_tick: datetime | None = None
        self._refresh_unsub: CALLBACK_TYPE | None = None
        self._evaluating = False
        self._again = False
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )

    def _make_panel(self, subentry: ConfigSubentry) -> Panel:
        cfg = PanelConfig.from_data(dict(subentry.data))
        geometry = PanelGeometry(
            self.latitude, self.longitude, cfg.azimuth, cfg.min_angle, cfg.max_angle
        )
        panel = Panel(
            subentry.subentry_id, subentry.title, cfg, cfg.build_mapping(), geometry
        )
        if cfg.relays:
            panel.driver = RelayDriver(
                self.hass,
                cfg.relay_config(),
                subentry.title,
                on_change=lambda: self._driver_changed(panel),
                on_external=lambda direction: self._driver_external(panel, direction),
                on_persist=self._save_now,
                on_fault=lambda fault: self._driver_fault(panel, fault),
                on_availability=lambda missing: self._driver_availability(
                    panel, missing
                ),
            )
        return panel

    # ---- lifecycle -----------------------------------------------------------

    async def async_start(self) -> None:
        """Restore state, precompute, subscribe and start ticking."""
        stored = await self._store.async_load() or {}
        site = stored.get("site", {})
        if until := site.get("storm_until"):
            self.safety.storm_until = (
                UNTIL_CLEARED if until == "manual" else dt_util.parse_datetime(until)
            )
        self.safety.wind_stowed = bool(site.get("wind_stowed", False))
        self.safety.last_wind = _float(site.get("last_wind"))
        for panel_id, data in stored.get("panels", {}).items():
            if panel := self.panels.get(panel_id):
                panel.restore(data)

        tz = dt_util.get_default_time_zone()
        year = dt_util.now().year
        for panel in self.panels.values():
            panel.fixed_angle = await self.hass.async_add_executor_job(
                annual_optimum, panel.geometry, year, tz
            )
            if panel.driver is not None:
                await panel.driver.async_start()
        await self.async_evaluate()  # fill in targets; nothing moves yet

    @callback
    def async_activate(self) -> None:
        """Subscribe and start ticking (after the entities exist)."""
        entities = {self.weather_entity, self.wind_sensor, *self._site_inputs()}
        for panel in self.panels.values():
            entities |= {
                panel.cfg.actuator_entity,
                panel.cfg.feedback_entity,
                panel.cfg.pv_power_entity,
            }
        entities.discard(None)
        entities.discard("")
        entities.discard("")
        self._unsubs.append(
            async_track_state_change_event(
                self.hass,
                sorted(entities),
                self._async_state_changed,  # type: ignore[arg-type]
            )
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_tick, timedelta(seconds=TICK_SECONDS)
            )
        )
        # Nothing moves before Home Assistant has fully started.
        self._unsubs.append(async_at_started(self.hass, self._async_on_started))
        if any(p.driver for p in self.panels.values()):
            self._unsubs.append(
                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STOP, self._async_relays_off
                )
            )

    async def _async_relays_off(self, _event: Event | None = None) -> None:
        """Home Assistant stops: both relays of every panel off."""
        for panel in self.panels.values():
            if panel.driver is not None:
                await panel.driver.async_shutdown()
        await self._store.async_save(self._store_data())

    async def _async_on_started(self, _hass: HomeAssistant) -> None:
        self.started = True
        await self.async_evaluate()

    async def async_stop(self) -> None:
        """Unsubscribe, switch relays off and save."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._refresh_unsub is not None:
            self._refresh_unsub()
            self._refresh_unsub = None
        for panel in self.panels.values():
            if panel.driver is not None:
                await panel.driver.async_shutdown()
        await self._store.async_save(self._store_data())

    def _store_data(self) -> dict[str, Any]:
        until = self.safety.storm_until
        return {
            "site": {
                "storm_until": None
                if until is None
                else ("manual" if until == UNTIL_CLEARED else until.isoformat()),
                "wind_stowed": self.safety.wind_stowed,
                "last_wind": self.safety.last_wind,
            },
            "panels": {pid: p.store_data() for pid, p in self.panels.items()},
        }

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(self._store_data, 5)

    @callback
    def _save_now(self) -> None:
        """Save at once (a relay run starts or ends: survive a crash)."""
        self.hass.async_create_task(
            self._store.async_save(self._store_data()), eager_start=True
        )

    # ---- relay driver callbacks ---------------------------------------------------

    def _require_relays(self, panel: Panel) -> None:
        """Refuse a button or action while a relay is offline (shows a toast)."""
        driver = panel.driver
        if driver is not None and not driver.async_check_available():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="relays_unavailable",
                translation_placeholders={
                    "panel": panel.title,
                    "entities": ", ".join(driver.unavailable),
                },
            )

    @callback
    def async_home(self, panel: Panel) -> None:
        """Home now: into the end stop, then back to the current target."""
        if panel.driver is None:
            return
        self._require_relays(panel)
        then = panel.target if panel.target is not None else panel.commanded
        position = None if then is None else panel.mapping.to_position(then)
        now = dt_util.utcnow()
        panel.move_started = now
        panel.commanded = then
        panel.driver.async_home(position)
        self._record(
            panel,
            now,
            then if then is not None else 0.0,
            REASON_CALIBRATE,
            "homing against the end stop",
        )

    @callback
    def async_travel_calibration(
        self,
        panel: Panel,
        action: str,
        homing_seconds: float | None = None,
        autosave: bool = True,
    ) -> dict[str, Any] | None:
        """Start, mark (end reached) or cancel the travel-time calibration."""
        driver = panel.driver
        if driver is None:
            return None
        if action == "start":
            self._require_relays(panel)
            seconds = homing_seconds or driver.cfg.max_run
            driver.async_calibration_start(seconds)
            assert driver.calibration is not None
            driver.calibration["autosave"] = autosave
        elif action == "stop":
            driver.async_calibration_mark()
        elif action == "cancel":
            driver.async_calibration_cancel()
        return driver.calibration

    @callback
    def _save_calibration(self, panel: Panel) -> None:
        driver = panel.driver
        assert driver is not None and driver.calibration is not None
        cal = driver.calibration
        cal["autosave"] = False
        subentry = self.entry.subentries.get(panel.id)
        if subentry is None or not cal.get("open_time") or not cal.get("close_time"):
            return
        LOGGER.info(
            "%s: measured %.1f s to open and %.1f s to close",
            panel.title,
            cal["open_time"],
            cal["close_time"],
        )
        self.hass.config_entries.async_update_subentry(
            self.entry,
            subentry,
            data={
                **subentry.data,
                "open_time": cal["open_time"],
                "close_time": cal["close_time"],
            },
        )

    @callback
    def _driver_changed(self, panel: Panel) -> None:
        now = dt_util.utcnow()
        driver = panel.driver
        if (
            driver is not None
            and driver.calibration is not None
            and driver.calibration["phase"] == "done"
            and driver.calibration.get("autosave")
        ):
            self._save_calibration(panel)
        self._read_panel(panel, now)
        if panel.driver is not None and not panel.driver.busy:
            panel.move_started = None
            self.hass.async_create_task(self.async_evaluate(), eager_start=False)
        else:
            self._notify()
            if self._refresh_unsub is None:
                self._refresh_unsub = async_track_time_interval(
                    self.hass, self._async_refresh_moving, REFRESH_WHILE_MOVING
                )

    @callback
    def _async_refresh_moving(self, _now: datetime) -> None:
        """Keep the estimate on the card fresh while a relay runs."""
        now = dt_util.utcnow()
        busy = False
        for panel in self.panels.values():
            if panel.driver is not None and panel.driver.busy:
                busy = True
                self._read_panel(panel, now)
        if not busy and self._refresh_unsub is not None:
            self._refresh_unsub()
            self._refresh_unsub = None
        self._notify()

    @callback
    def _driver_external(self, panel: Panel, direction: int) -> None:
        """A relay was switched outside Helios Tilt: pause automatic control."""
        now = dt_util.utcnow()
        panel.manual_until = now + self.manual_pause
        self._record(
            panel,
            now,
            panel.current if panel.current is not None else 0.0,
            REASON_MANUAL,
            "relay switched by hand ({}), automatic control paused".format(
                "opening" if direction > 0 else "closing"
            ),
            commanded=False,
        )

    @callback
    def _driver_availability(self, panel: Panel, missing: list[str]) -> None:
        """A relay or countdown went offline, or everything is back."""
        issue_id = f"relay_unavailable_{panel.id}"
        if missing:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="relay_unavailable",
                translation_placeholders={
                    "panel": panel.title,
                    "entities": ", ".join(missing),
                },
            )
            self._notify()
            return
        ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        panel.commanded = None  # send the current target again
        panel.move_started = None
        self.hass.async_create_task(self.async_evaluate(), eager_start=False)

    @callback
    def _driver_fault(self, panel: Panel, fault: str | None) -> None:
        issue_id = f"relay_fault_{panel.id}"
        if fault is None:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        panel.commanded = None  # retry once the back-off has passed
        panel.move_started = None
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="relay_fault",
            translation_placeholders={"panel": panel.title, "fault": fault},
        )

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> CALLBACK_TYPE:
        """Entities register here to be told about changes."""
        self._listeners.append(update)

        @callback
        def _remove() -> None:
            self._listeners.remove(update)

        return _remove

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()

    # ---- inputs --------------------------------------------------------------

    def _site_inputs(self) -> list[str]:
        """Optional site entities that trigger a re-evaluation."""
        return [
            e
            for e in (
                self.rain_sensor,
                self.snow_sensor,
                self.temp_sensor,
                self.direction_sensor,
                *self.triggers,
            )
            if e
        ]

    def _read_weather(self, now: datetime) -> Readings:
        speeds: dict[str, float] = {}
        ages: list[timedelta] = []
        condition = temperature = cloud = bearing = None
        temp_source = bearing_source = None
        weather = (
            self.hass.states.get(self.weather_entity) if self.weather_entity else None
        )
        if _usable(weather):
            assert weather is not None
            attrs = weather.attributes
            unit = attrs.get("wind_speed_unit")
            for key, source in (
                ("wind_speed", SOURCE_WEATHER_WIND),
                ("wind_gust_speed", SOURCE_WEATHER_GUST),
            ):
                if (speed := _speed_kmh(attrs.get(key), unit)) is not None:
                    speeds[source] = round(speed, 1)
            if speeds:
                ages.append(max(timedelta(0), now - weather.last_reported))
            condition = weather.state
            if (temp := _float(attrs.get("temperature"))) is not None:
                temperature = TemperatureConverter.convert(
                    temp,
                    attrs.get("temperature_unit") or UnitOfTemperature.CELSIUS,
                    UnitOfTemperature.CELSIUS,
                )
                temp_source = self.weather_entity
            cloud = _float(attrs.get("cloud_coverage"))
            if (bearing := _bearing(attrs.get("wind_bearing"))) is not None:
                bearing_source = self.weather_entity
        sensor = self.hass.states.get(self.wind_sensor) if self.wind_sensor else None
        if _usable(sensor):
            assert sensor is not None
            if (
                speed := _speed_kmh(
                    sensor.state, sensor.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                )
            ) is not None:
                speeds[SOURCE_SENSOR] = round(speed, 1)
                ages.append(max(timedelta(0), now - sensor.last_reported))
        if self.direction_sensor:
            state = self.hass.states.get(self.direction_sensor)
            if _usable(state):
                assert state is not None
                if (value := _bearing(state.state)) is not None:
                    bearing, bearing_source = value, self.direction_sensor
        if self.temp_sensor:
            state = self.hass.states.get(self.temp_sensor)
            if _usable(state):
                assert state is not None
                if (value := self._temperature(state)) is not None:
                    temperature, temp_source = value, self.temp_sensor
        rain, rain_value = self._read_level(
            self.rain_sensor, self.rain_threshold, RAIN_RATE_MM_H, "mm/h"
        )
        snow, snow_value = self._read_level(
            self.snow_sensor, self.snow_threshold, DEPTH_CM, "cm"
        )
        triggers = []
        for entity_id in self.triggers:
            state = self.hass.states.get(entity_id)
            if state is not None and state.state == STATE_ON:
                triggers.append(state.name)
        driving = max(speeds, key=lambda k: speeds[k]) if speeds else None
        self.bearing = bearing
        self.sources = {
            "weather_entity": self.weather_entity,
            "wind_sensor": self.wind_sensor,
            "wind_source": driving,
            "weather_wind": speeds.get(SOURCE_WEATHER_WIND),
            "weather_gust": speeds.get(SOURCE_WEATHER_GUST),
            "sensor_wind": speeds.get(SOURCE_SENSOR),
            "wind_bearing": None if bearing is None else round(bearing, 1),
            "wind_bearing_source": bearing_source,
            "direction_rule": self.direction_rule,
            "temperature": None if temperature is None else round(temperature, 1),
            "temperature_source": temp_source,
            "rain_sensor": self.rain_sensor,
            "rain_sensor_value": rain_value,
            "snow_sensor": self.snow_sensor,
            "snow_sensor_value": snow_value,
            "stow_triggers": list(self.triggers),
            "active_triggers": triggers,
        }
        return Readings(
            wind=speeds[driving] if driving else None,
            wind_age=min(ages) if ages else None,
            condition=condition,
            temperature=temperature,
            cloud=cloud,
            rain=rain,
            snow=snow,
            triggers=triggers,
        )

    def _temperature(self, state: State) -> float | None:
        if (value := _float(state.state)) is None:
            return None
        try:
            return TemperatureConverter.convert(
                value,
                state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                or UnitOfTemperature.CELSIUS,
                UnitOfTemperature.CELSIUS,
            )
        except Exception:  # unknown unit  # noqa: BLE001
            LOGGER.warning("Unknown temperature unit on %s", state.entity_id)
            return None

    def _read_level(
        self,
        entity_id: str | None,
        threshold: float,
        table: dict[str, float],
        default: str,
    ) -> tuple[bool | None, Any]:
        """(active, value) from an on/off or a numeric sensor; None = unknown."""
        if not entity_id:
            return None, None
        state = self.hass.states.get(entity_id)
        if not _usable(state):
            return None, None
        assert state is not None
        if state.state in (STATE_ON, "off"):
            return state.state == STATE_ON, state.state
        if (value := _float(state.state)) is None:
            return None, None
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        level = _converted(value, unit, table, default)
        if level is None:
            LOGGER.warning("Unknown unit %s on %s, ignoring it", unit, entity_id)
            return None, None
        return level >= threshold, f"{round(level, 2)} {default}"

    def _wind_hits(self, panel: Panel) -> bool:
        """Does the wind direction rule say this panel must stow?"""
        if not self.direction_rule or self.bearing is None:
            return True  # rule off or no direction: stow from any side
        front = panel.cfg.azimuth
        hit_front = _angle_diff(self.bearing, front) <= self.direction_sector
        hit_rear = _angle_diff(self.bearing, front + 180.0) <= self.direction_sector
        if self.direction_sides == SIDES_FRONT:
            return hit_front
        if self.direction_sides == SIDES_REAR:
            return hit_rear
        return hit_front or hit_rear

    def _update_quiet(self, now: datetime) -> None:
        start, end = self.quiet_start, self.quiet_end
        self.quiet, self.quiet_until = False, None
        if start is None or end is None:
            return
        local = dt_util.as_local(now)
        if not in_window(local.time().replace(tzinfo=None), start, end):
            return
        self.quiet = True
        until = local.replace(
            hour=end.hour, minute=end.minute, second=end.second, microsecond=0
        )
        if until <= local:
            until += timedelta(days=1)
        self.quiet_until = until

    def _read_panel(self, panel: Panel, now: datetime) -> None:
        """Current angle, moving flag and PV power."""
        cfg = panel.cfg
        if panel.driver is not None:
            position = panel.driver.current_position(now)
            panel.moving = panel.driver.busy
            angle = None if position is None else panel.mapping.to_angle(position)
            panel.current = None if angle is None else round(angle, 1)
            panel.current_source = "estimate" if angle is not None else "unknown"
            if cfg.pv_power_entity:
                pv = self.hass.states.get(cfg.pv_power_entity)
                panel.pv_actual = _float(pv.state) if _usable(pv) else None  # type: ignore[union-attr]
            return
        actuator = self.hass.states.get(cfg.actuator_entity)
        panel.moving = bool(
            actuator is not None
            and actuator.domain == "cover"
            and actuator.state in COVER_MOVING
        )
        angle = None
        source = "estimate"
        if cfg.feedback_entity:
            feedback = self.hass.states.get(cfg.feedback_entity)
            if _usable(feedback) and (value := _float(feedback.state)) is not None:  # type: ignore[union-attr]
                angle = (
                    value
                    if cfg.feedback_kind == FEEDBACK_ANGLE
                    else panel.mapping.to_angle(value)
                )
                source = "feedback"
        elif (
            actuator is not None
            and actuator.domain == "cover"
            and (pos := _float(actuator.attributes.get("current_position"))) is not None
        ):
            angle = panel.mapping.to_angle(pos)
            source = "cover"
        if angle is None:
            angle = self._estimate(panel, now)
            if panel.move_started is not None and angle != panel.commanded:
                panel.moving = True
        panel.current = round(angle, 1) if angle is not None else None
        panel.current_source = source if angle is not None else "unknown"

        if cfg.pv_power_entity:
            pv = self.hass.states.get(cfg.pv_power_entity)
            panel.pv_actual = _float(pv.state) if _usable(pv) else None  # type: ignore[union-attr]

    def _estimate(self, panel: Panel, now: datetime) -> float | None:
        if panel.commanded is None:
            return panel.estimate
        if panel.move_started is None or panel.move_from is None:
            return panel.commanded
        span = panel.cfg.max_angle - panel.cfg.min_angle
        duration = travel_seconds(
            panel.move_from, panel.commanded, span, panel.cfg.travel_time
        )
        elapsed = (now - panel.move_started).total_seconds()
        if elapsed >= duration:
            return panel.commanded
        return estimate_angle(panel.move_from, panel.commanded, elapsed, duration)

    # ---- events --------------------------------------------------------------

    async def _async_state_changed(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        now = dt_util.utcnow()
        for panel in self.panels.values():
            if entity_id in (panel.cfg.actuator_entity, panel.cfg.feedback_entity):
                self._detect_manual(panel, event, now)
        if entity_id in (
            self.weather_entity,
            self.wind_sensor,
            *self._site_inputs(),
        ) or any(
            entity_id in (p.cfg.actuator_entity, p.cfg.feedback_entity)
            for p in self.panels.values()
        ):
            await self.async_evaluate()
        else:  # PV power: just refresh the numbers
            for panel in self.panels.values():
                self._read_panel(panel, now)
                self._update_pv(panel)
            self._notify()

    def _detect_manual(self, panel: Panel, event: Event, now: datetime) -> None:
        """Someone moved the panel without us: pause automatic control."""
        new: State | None = event.data.get("new_state")
        old: State | None = event.data.get("old_state")
        if not _usable(new) or not _usable(old):
            return
        assert new is not None and old is not None
        cfg = panel.cfg
        if (
            new.domain == "cover"
            and new.entity_id == cfg.actuator_entity
            and not cfg.feedback_entity
        ):
            value = _float(new.attributes.get("current_position"))
            before = _float(old.attributes.get("current_position"))
            if new.state in COVER_MOVING:
                return  # judge the end position
        elif (
            new.domain in ("number", "input_number")
            and new.entity_id == cfg.actuator_entity
            or new.entity_id == cfg.feedback_entity
        ):
            value, before = _float(new.state), _float(old.state)
        else:
            return
        if value is None or value == before:
            return
        angle = (
            value
            if (
                new.entity_id == cfg.feedback_entity
                and cfg.feedback_kind == FEEDBACK_ANGLE
            )
            else panel.mapping.to_angle(value)
        )
        # Moving because we told it to? Then it's not manual.
        if panel.commanded is not None and panel.move_started is not None:
            span = cfg.max_angle - cfg.min_angle
            duration = travel_seconds(
                panel.move_from if panel.move_from is not None else panel.commanded,
                panel.commanded,
                span,
                cfg.travel_time,
            )
            in_move = (
                now - panel.move_started
                <= timedelta(seconds=duration * 1.5) + SETTLE_GRACE
            )
            start = panel.move_from if panel.move_from is not None else panel.commanded
            between = (
                min(start, panel.commanded) - MANUAL_TOLERANCE
                <= angle
                <= max(start, panel.commanded) + MANUAL_TOLERANCE
            )
            if in_move and between:
                return
        if panel.commanded is None:
            return  # nothing to compare with yet
        if abs(angle - panel.commanded) <= MANUAL_TOLERANCE:
            return  # where we sent it
        panel.manual_until = now + self.manual_pause
        panel.commanded = round(angle, 1)
        panel.move_started = None
        self._record(
            panel,
            now,
            angle,
            REASON_MANUAL,
            "moved by hand, automatic control paused",
            commanded=False,
        )
        LOGGER.info(
            "%s moved by hand to %.1f deg; pausing automatic control",
            panel.title,
            angle,
        )

    @callback
    def _async_tick(self, _now: datetime) -> None:
        self.hass.async_create_task(self.async_evaluate(), eager_start=True)

    # ---- decisions -----------------------------------------------------------

    def _strategy_plan(self, panel: Panel, now: datetime) -> tuple[float, str, str]:
        """(raw angle, reason, detail) from the strategy."""
        strategy = panel.strategy
        local = dt_util.as_local(now)
        cfg = panel.cfg
        geo = panel.geometry
        if strategy == STRATEGY_TRACKING:
            assert self.sun is not None
            if is_night(self.sun):
                return geo.clamp(cfg.night_angle), REASON_NIGHT, ""
            cloud = self.readings.cloud
            if cloud is not None and cloud > self.cloud_threshold:
                return (
                    geo.clamp(cfg.diffuse_angle),
                    REASON_DIFFUSE,
                    f"{cloud:.0f}% clouds",
                )
            return (
                tracking_target(geo, self.sun),
                REASON_STRATEGY,
                STRATEGY_TEXT[strategy],
            )
        if strategy == STRATEGY_SEASONAL:
            angle = seasonal_angle(
                local.date(),
                self.latitude,
                cfg.winter_angle,
                cfg.summer_angle,
                cfg.season_weight,
            )
            return geo.clamp(angle), REASON_STRATEGY, STRATEGY_TEXT[strategy]
        if (
            strategy == STRATEGY_DAILY
            and panel.daily
            and panel.daily[0] == local.date()
        ):
            return panel.daily[1], REASON_STRATEGY, STRATEGY_TEXT[strategy]
        fixed = (
            panel.fixed_angle
            if panel.fixed_angle is not None
            else geo.clamp(abs(self.latitude))
        )
        return fixed, REASON_STRATEGY, STRATEGY_TEXT[STRATEGY_FIXED]

    def _decide(
        self, panel: Panel, safety: SafetyState, now: datetime
    ) -> tuple[float | None, str, str, bool]:
        """(target or None to hold, reason, detail, urgent)."""
        cfg, geo = panel.cfg, panel.geometry
        panel.wind_exempt = False
        if safety.state == WIND and not self._wind_hits(panel):
            # wind direction rule: this wind comes from the side, no stow needed
            panel.wind_exempt = True
            safety = self.safety.without_wind(now, self.readings)
        quiet_detail = (
            f"until {dt_util.as_local(self.quiet_until):%H:%M}"
            if self.quiet_until
            else ""
        )
        # quiet hours may hold safety moves too (never storm mode)
        if (
            self.quiet
            and not self.quiet_safety
            and safety.state != STORM
            and (safety.stow or safety.state in (SNOW, RAIN, FROST))
            and not panel.stowed
        ):
            return None, REASON_QUIET, quiet_detail, False
        if safety.stow:
            if safety.state == TRIGGER:
                angle = (
                    self.trigger_angle
                    if self.trigger_angle is not None
                    else cfg.stow_angle
                )
                return geo.clamp(angle), REASON_TRIGGER, safety.detail, True
            reason = REASON_STORM if safety.state == STORM else REASON_WIND
            return geo.clamp(cfg.stow_angle), reason, safety.detail, True
        if panel.stowed:
            detail = (
                f"until {dt_util.as_local(panel.stowed_until):%H:%M}"
                if panel.stowed_until
                else ""
            )
            return geo.clamp(cfg.stow_angle), REASON_STOW, detail, True
        if safety.frozen:
            return None, panel.target_reason, safety.detail, False
        if safety.state == SNOW:
            return geo.clamp(cfg.snow_angle), REASON_SNOW, safety.detail, False
        if safety.state == RAIN:
            return geo.clamp(cfg.rain_angle), REASON_RAIN, safety.detail, False
        if safety.state == FROST:
            return geo.clamp(cfg.frost_angle), REASON_FROST, safety.detail, False
        if panel.mode == MODE_MANUAL:
            angle = (
                panel.manual_angle if panel.manual_angle is not None else panel.current
            )
            if angle is None:
                return None, REASON_MANUAL, "", False
            return geo.clamp(angle), REASON_MANUAL, "", False
        if panel.manual_until is not None and now < panel.manual_until:
            return None, REASON_MANUAL, "paused after a manual move", False
        if not panel.auto_enabled:
            return None, panel.target_reason, "automatic control off", False
        if self.quiet and not panel.user_pending:
            return None, REASON_QUIET, quiet_detail, False
        raw, reason, detail = self._strategy_plan(panel, now)
        current = panel.commanded if panel.commanded is not None else None
        angle = geo.clamp(round_to_step(raw, cfg.step, current, self.hysteresis))
        if (
            current is not None
            and reason == REASON_STRATEGY
            and abs(angle - current) < self.deadband
        ):
            angle = current
        return angle, reason, detail, False

    async def async_evaluate(self, user: Iterable[Panel] = ()) -> None:
        """Run one full decision round.

        Panels in `user` were just changed by the user (mode, angle, resume):
        they skip the minimum move interval.
        """
        for panel in user:
            panel.user_pending = True
        if self._evaluating:  # a state change arrived mid-round: run again after
            self._again = True
            return
        self._evaluating = True
        try:
            while True:
                self._again = False
                await self._async_evaluate_once()
                if not self._again:
                    break
        finally:
            self._evaluating = False

    async def _async_evaluate_once(self) -> None:
        now = dt_util.utcnow()
        local = dt_util.as_local(now)
        self.sun = sun_position(now, self.latitude, self.longitude)
        self.readings = self._read_weather(now)
        safety = self.safety.evaluate(now, self.readings)
        self._update_quiet(now)
        await self._async_daily_plans(local.date())
        for panel in self.panels.values():
            self._read_panel(panel, now)
            self._accumulate(panel, now, local.date())
            self._update_pv(panel)
            if panel.manual_until is not None and now >= panel.manual_until:
                panel.manual_until = None
            if panel.stowed_until is not None and now >= panel.stowed_until:
                panel.stowed, panel.stowed_until = False, None
            target, reason, detail, urgent = self._decide(panel, safety, now)
            panel.target = (
                target
                if target is not None
                else (panel.commanded if panel.commanded is not None else panel.current)
            )
            panel.target_reason, panel.target_detail = reason, detail
            panel.following_strategy = (
                target is not None
                and panel.mode != MODE_MANUAL
                and reason in (REASON_STRATEGY, REASON_NIGHT)
            )
            if target is None:
                panel.user_pending = False
            elif self.started:
                await self._async_maybe_move(
                    panel, target, reason, detail, urgent or panel.user_pending, now
                )
                self._read_panel(panel, now)
            self._check_stuck(panel, now)
            self._update_curve(panel, local.date())
        self._update_sun_path(local.date())
        self._last_tick = now
        self._save()
        self._notify()

    async def _async_daily_plans(self, day: date) -> None:
        tz = dt_util.get_default_time_zone()
        for panel in self.panels.values():
            if panel.strategy == STRATEGY_DAILY and (
                panel.daily is None or panel.daily[0] != day
            ):
                angle = await self.hass.async_add_executor_job(
                    daily_optimum, panel.geometry, day, tz
                )
                panel.daily = (day, angle)

    async def _async_maybe_move(
        self,
        panel: Panel,
        target: float,
        reason: str,
        detail: str,
        urgent: bool,
        now: datetime,
    ) -> None:
        driver = panel.driver
        if driver is not None and driver.calibrating:
            if reason not in SAFETY_REASONS:
                return  # travel calibration owns the relays
            driver.async_calibration_cancel()  # wind and storm win: stow
        if driver is not None and (not driver.available or driver.backing_off(now)):
            return  # offline, or a recent fault: no attempts (no log spam)
        if panel.commanded is not None and abs(target - panel.commanded) < 0.5:
            panel.user_pending = False
            return
        if panel.moving and not (driver is not None and urgent):
            return  # never command a moving actuator; next round
        last = panel.last_move
        if (
            not urgent
            and panel.commanded is not None
            and last is not None
            and now - last.time < self.min_interval
        ):
            return
        await self._async_command(panel, target, now, reason)
        panel.user_pending = False
        self._record(panel, now, target, reason, detail)

    async def _async_command(
        self, panel: Panel, angle: float, now: datetime, reason: str = REASON_STRATEGY
    ) -> None:
        cfg = panel.cfg
        position = panel.mapping.to_position(angle)
        if panel.driver is not None:
            # Night park homes now and then, so the day starts in sync.
            home = bool(
                reason == REASON_NIGHT
                and cfg.home_at_night
                and panel.driver.moves_since_home > 0
            )
            panel.commanded = angle
            panel.expected_position = position
            panel.move_started = now
            panel.move_from = panel.current
            panel.driver.async_request(position, home_first=home)
            return
        entity_id = cfg.actuator_entity
        domain = entity_id.split(".", 1)[0]
        if domain == "cover":
            service, data = (
                "set_cover_position",
                {"position": round(max(0.0, min(100.0, position)))},
            )
        elif domain in ("number", "input_number"):
            service, data = "set_value", {"value": round(position, 2)}
        elif domain == "script":
            service = "turn_on"
            data = {
                "variables": {
                    "angle": angle,
                    "position": round(position, 2),
                    "panel": panel.title,
                }
            }
        else:
            LOGGER.error(
                "%s: can't drive %s (use a cover, number or script)",
                panel.title,
                entity_id,
            )
            return
        LOGGER.debug(
            "%s: %s.%s %s -> %.1f deg", panel.title, domain, service, data, angle
        )
        panel.move_from = (
            panel.current if panel.current is not None else panel.commanded
        )
        if panel.move_from is None:  # position unknown: assume the longest travel
            lo, hi = cfg.min_angle, cfg.max_angle
            panel.move_from = lo if abs(angle - lo) > abs(angle - hi) else hi
        panel.commanded = angle
        panel.expected_position = position
        panel.move_started = now
        await self.hass.services.async_call(
            domain, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=False
        )

    def _record(
        self,
        panel: Panel,
        now: datetime,
        angle: float,
        reason: str,
        detail: str,
        commanded: bool = True,
    ) -> None:
        local_day = dt_util.as_local(now).date()
        if panel.moves_day != local_day:
            panel.moves_day, panel.moves_today = local_day, 0
        if commanded:
            panel.moves_today += 1
        panel.history.append(Move(now, round(angle, 1), reason, detail))
        del panel.history[:-HISTORY_LEN]
        text = REASON_TEXT.get(reason, reason).format(
            strategy=detail or STRATEGY_TEXT.get(panel.strategy, ""), detail=detail
        )
        verb = "moved to" if commanded else "is at"
        message = f"{verb} {angle:.0f}\u00b0: {text}"
        sensor_id = er.async_get(self.hass).async_get_entity_id(
            "sensor", DOMAIN, f"{panel.id}_target_angle"
        )
        self.hass.bus.async_fire(
            EVENT_LOGBOOK_ENTRY,
            {
                "name": panel.title,
                "message": message,
                "domain": DOMAIN,
                ATTR_ENTITY_ID: sensor_id,
            },
        )
        self.hass.bus.async_fire(
            EVENT_MOVE,
            {
                "panel": panel.title,
                "angle": angle,
                "reason": reason,
                "detail": detail,
                "entity_id": sensor_id,
            },
        )
        LOGGER.info("%s %s", panel.title, message)

    def _check_stuck(self, panel: Panel, now: datetime) -> None:
        if (
            panel.driver is not None  # relay panels report their own faults
            or panel.current is None  # no reading (offline): can't judge
            or panel.move_started is None
            or panel.commanded is None
            or panel.current_source == "estimate"
        ):
            return
        span = panel.cfg.max_angle - panel.cfg.min_angle
        duration = travel_seconds(
            panel.move_from if panel.move_from is not None else panel.commanded,
            panel.commanded,
            span,
            panel.cfg.travel_time,
        )
        reached = (
            panel.current is not None
            and abs(panel.current - panel.commanded) <= MANUAL_TOLERANCE
        )
        issue_id = f"actuator_stuck_{panel.id}"
        if reached:
            panel.move_started = None
            if panel.stuck:
                panel.stuck = False
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        if (
            not panel.stuck
            and now - panel.move_started
            > timedelta(seconds=duration * 1.5) + SETTLE_GRACE
        ):
            panel.stuck = True
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="actuator_stuck",
                translation_placeholders={
                    "panel": panel.title,
                    "entity": panel.cfg.actuator_entity,
                    "target": f"{panel.commanded:.0f}",
                    "current": "?" if panel.current is None else f"{panel.current:.0f}",
                },
            )
            LOGGER.warning(
                "%s did not reach %.0f deg (at %s)",
                panel.title,
                panel.commanded,
                panel.current,
            )

    # ---- numbers for the sensors and the card -------------------------------

    def _accumulate(self, panel: Panel, now: datetime, day: date) -> None:
        """Add the time since the last round to today's gain estimate.

        The panel held `panel.current` (read before this round moves it)
        during that time; the sun is taken at the middle of the interval.
        The reference is the annual optimum rounded to the panel's step and
        limits: what the same rack would do on the Fixed strategy.
        """
        if panel.energy_day != day:
            panel.energy_day, panel.energy_actual, panel.energy_fixed = day, 0.0, 0.0
            panel.energy_since, panel.excluded_seconds = None, 0.0
        reference = self.fixed_reference(panel)
        panel.instant_gain = None
        if self.sun is not None and panel.current is not None and reference is not None:
            ref_now = plane_irradiance(reference, panel.cfg.azimuth, self.sun)
            if panel.following_strategy and ref_now >= 50.0:
                now_actual = plane_irradiance(
                    panel.current, panel.cfg.azimuth, self.sun
                )
                panel.instant_gain = round((now_actual / ref_now - 1.0) * 100.0, 1)
        if self._last_tick is None or panel.current is None or reference is None:
            return
        seconds = min((now - self._last_tick).total_seconds(), 600.0)
        if seconds <= 0:
            return
        mid = sun_position(
            now - timedelta(seconds=seconds / 2.0), self.latitude, self.longitude
        )
        if mid.elevation <= 0.0:
            return
        if not panel.following_strategy:
            panel.excluded_seconds += seconds
            return
        hours = seconds / 3600.0
        az = panel.cfg.azimuth
        panel.energy_actual += plane_irradiance(panel.current, az, mid) * hours
        panel.energy_fixed += plane_irradiance(reference, az, mid) * hours
        if panel.energy_since is None:
            panel.energy_since = now - timedelta(seconds=seconds)

    @staticmethod
    def fixed_reference(panel: Panel) -> float | None:
        """The annual optimum as this panel would hold it (step and limits)."""
        if panel.fixed_angle is None:
            return None
        cfg = panel.cfg
        raw = panel.fixed_angle
        if cfg.step > 0:
            raw = round(raw / cfg.step) * cfg.step
        return panel.geometry.clamp(raw)

    def _update_pv(self, panel: Panel) -> None:
        if (
            not panel.cfg.pv_power_entity
            or not panel.cfg.pv_peak_power
            or self.sun is None
        ):
            panel.pv_model = None
            return
        angle = panel.current if panel.current is not None else 0.0
        panel.pv_model = round(
            panel.cfg.pv_peak_power
            * plane_irradiance(angle, panel.cfg.azimuth, self.sun)
            / 1000.0,
            1,
        )

    def _update_curve(self, panel: Panel, day: date) -> None:
        """Planned angle every 30 minutes today (for the card)."""
        key = (day, panel.strategy, panel.daily, panel.fixed_angle)
        if panel.curve_key == key:
            return
        tz = dt_util.get_default_time_zone()
        start = datetime.combine(day, datetime.min.time(), tz)
        curve = []
        cfg, geo = panel.cfg, panel.geometry
        for i in range(49):
            when = start + timedelta(minutes=30 * i)
            if panel.strategy == STRATEGY_TRACKING:
                sun = sun_position(when, self.latitude, self.longitude)
                raw = (
                    geo.clamp(cfg.night_angle)
                    if is_night(sun)
                    else tracking_target(geo, sun)
                )
            elif panel.strategy == STRATEGY_SEASONAL:
                raw = geo.clamp(
                    seasonal_angle(
                        day,
                        self.latitude,
                        cfg.winter_angle,
                        cfg.summer_angle,
                        cfg.season_weight,
                    )
                )
            elif panel.strategy == STRATEGY_DAILY and panel.daily:
                raw = panel.daily[1]
            else:
                raw = panel.fixed_angle if panel.fixed_angle is not None else 0.0
            angle = geo.clamp(round(raw / cfg.step) * cfg.step) if cfg.step > 0 else raw
            curve.append(
                (f"{when.hour:02d}:{when.minute:02d}" if i < 48 else "24:00", angle)
            )
        panel.today_curve = curve
        panel.curve_key = key

    def _update_sun_path(self, day: date) -> None:
        if self.sun_path_day == day:
            return
        tz = dt_util.get_default_time_zone()
        start = datetime.combine(day, datetime.min.time(), tz)
        path = []
        for i in range(49):
            when = start + timedelta(minutes=30 * i)
            sun = sun_position(when, self.latitude, self.longitude)
            path.append(
                (
                    f"{when.hour:02d}:{when.minute:02d}" if i < 48 else "24:00",
                    round(sun.elevation, 1),
                    round(sun.azimuth, 1),
                )
            )
        self.sun_path, self.sun_path_day = path, day

    # ---- actions -------------------------------------------------------------

    async def async_set_tilt(self, panel: Panel, angle: float) -> None:
        """Manual angle."""
        panel.mode = MODE_MANUAL
        panel.manual_angle = panel.geometry.clamp(angle)
        await self.async_evaluate([panel])

    async def async_set_mode(self, panel: Panel, mode: str) -> None:
        """Change the mode (auto, manual or a strategy)."""
        if mode == MODE_MANUAL and panel.manual_angle is None:
            panel.manual_angle = (
                panel.current if panel.current is not None else panel.commanded
            )
        panel.mode = mode
        panel.manual_until = None
        await self.async_evaluate([panel])

    async def async_set_auto(self, panel: Panel, enabled: bool) -> None:
        """Automatic control on or off."""
        panel.auto_enabled = enabled
        await self.async_evaluate([panel])

    async def async_stow(
        self, panels: list[Panel], storm: bool, duration: timedelta | None = None
    ) -> None:
        """Stow panels now; with storm=True also latch storm mode for the site.

        With a duration the stow clears itself afterwards (else: until resumed).
        """
        until = dt_util.utcnow() + duration if duration else None
        for panel in panels:
            panel.stowed = True
            panel.stowed_until = until
        if storm:
            self.safety.latch_storm(dt_util.utcnow())
        await self.async_evaluate()

    async def async_resume(self, panels: list[Panel]) -> None:
        """Back to automatic: clears stow, manual mode, pause and the storm latch."""
        for panel in panels:
            panel.stowed, panel.stowed_until = False, None
            panel.manual_until = None
            if panel.mode == MODE_MANUAL:
                panel.mode = MODE_AUTO
            panel.auto_enabled = True
        self.safety.clear_storm()
        await self.async_evaluate(panels)

    async def async_calibrate(self, panel: Panel, angle: float) -> None:
        """Tell the integration the panel's real angle (open-loop resync)."""
        now = dt_util.utcnow()
        panel.commanded = panel.estimate = panel.current = round(angle, 1)
        panel.move_started = None
        if panel.driver is not None:
            panel.driver.set_position(panel.mapping.to_position(angle))
        self._record(
            panel, now, angle, REASON_CALIBRATE, "angle set by hand", commanded=False
        )
        self._save()
        self._notify()

    def diagnostics(self) -> dict[str, Any]:
        """State snapshot for diagnostics."""
        return {
            "safety": {
                "state": self.safety.last.state,
                "detail": self.safety.last.detail,
                "storm": self.safety.storm,
                "wind_stowed": self.safety.wind_stowed,
                "last_wind": self.safety.last_wind,
            },
            "readings": {
                "wind": self.readings.wind,
                "wind_age_s": self.readings.wind_age.total_seconds()
                if self.readings.wind_age
                else None,
                "condition": self.readings.condition,
                "temperature": self.readings.temperature,
                "cloud": self.readings.cloud,
                "rain": self.readings.rain,
                "snow": self.readings.snow,
            },
            "sources": self.sources,
            "quiet": {
                "active": self.quiet,
                "until": self.quiet_until.isoformat() if self.quiet_until else None,
            },
            "sun": None
            if self.sun is None
            else {
                "azimuth": round(self.sun.azimuth, 2),
                "elevation": round(self.sun.elevation, 2),
            },
            "panels": {
                p.title: {
                    "config": {f.name: getattr(p.cfg, f.name) for f in fields(p.cfg)},
                    "state": p.store_data(),
                    "target": p.target,
                    "current": p.current,
                    "current_source": p.current_source,
                    "fixed_angle": p.fixed_angle,
                    "daily": None if p.daily is None else p.daily[1],
                    "stuck": p.stuck,
                }
                for p in self.panels.values()
            },
        }
