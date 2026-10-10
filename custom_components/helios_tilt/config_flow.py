"""Config flow: a site (location + weather) with one or more panels."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME, UnitOfSpeed
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .actuator import MappingError
from .const import (
    ACTUATOR_ENTITY,
    ACTUATOR_RELAYS,
    ACTUATOR_TYPES,
    AXES,
    AXIS_ROLL,
    CONF_ACTUATOR,
    CONF_ACTUATOR_TYPE,
    CONF_ANGLE_CLOSED,
    CONF_ANGLE_OPEN,
    CONF_AXIS,
    CONF_AZIMUTH,
    CONF_CALIBRATION,
    CONF_CALM_MINUTES,
    CONF_CLOSE_COUNTDOWN,
    CONF_CLOSE_SWITCH,
    CONF_CLOSE_TIME,
    CONF_CLOUD_THRESHOLD,
    CONF_DEADBAND,
    CONF_DIFFUSE_ANGLE,
    CONF_FEEDBACK,
    CONF_FEEDBACK_KIND,
    CONF_FROST_ANGLE,
    CONF_FROST_MODE,
    CONF_FROST_TEMP,
    CONF_HOME_AFTER_MOVES,
    CONF_HOME_AT_NIGHT,
    CONF_HOME_END,
    CONF_HOME_OVERRUN,
    CONF_HYSTERESIS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MANUAL_PAUSE,
    CONF_MAPPING,
    CONF_MAX_ANGLE,
    CONF_MIN_ANGLE,
    CONF_MIN_INTERVAL,
    CONF_NIGHT_ANGLE,
    CONF_OPEN_COUNTDOWN,
    CONF_OPEN_SWITCH,
    CONF_OPEN_TIME,
    CONF_POS_AT_MAX,
    CONF_POS_AT_MIN,
    CONF_PV_PEAK,
    CONF_PV_POWER,
    CONF_RAIN_ANGLE,
    CONF_RAIN_MODE,
    CONF_REVERSE_DELAY,
    CONF_SEASON_WEIGHT,
    CONF_SNOW_ANGLE,
    CONF_SNOW_MODE,
    CONF_STALE_MINUTES,
    CONF_START_DELAY,
    CONF_STEP,
    CONF_STORM_HOLD,
    CONF_STORM_SPEED,
    CONF_STOW_ANGLE,
    CONF_STRATEGY,
    CONF_SUMMER_ANGLE,
    CONF_TRAVEL_TIME,
    CONF_WEATHER,
    CONF_WIND_RESUME,
    CONF_WIND_SENSOR,
    CONF_WIND_STOW,
    CONF_WINTER_ANGLE,
    DOMAIN,
    FEEDBACK_ANGLE,
    FEEDBACK_POSITION,
    HOME_ENDS,
    MAPPING_LINEAR,
    MAPPING_TABLE,
    NAME,
    PANEL_DEFAULTS,
    SITE_DEFAULTS,
    STRATEGIES,
    SUBENTRY_PANEL,
)
from .controller import PanelConfig

ATTR_HOMING = "homing_seconds"


def _num(
    lo: float,
    hi: float,
    step: float | str = 1,
    unit: str | None = None,
    box: bool = True,
) -> selector.NumberSelector:
    config = selector.NumberSelectorConfig(
        min=lo,
        max=hi,
        step=step,  # type: ignore[typeddict-item]
        mode=selector.NumberSelectorMode.BOX
        if box
        else selector.NumberSelectorMode.SLIDER,
    )
    if unit:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def _angle(lo: float = -90, hi: float = 90) -> selector.NumberSelector:
    return _num(lo, hi, 1, "°")


def _choice(options: list[str], key: str) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            translation_key=key,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _opt(key: str, values: dict[str, Any]) -> vol.Optional:
    """Optional field with a suggested (clearable) value."""
    value = values.get(key)
    if value in (None, ""):
        return vol.Optional(key)
    return vol.Optional(key, description={"suggested_value": value})


# ---- site ----------------------------------------------------------------------


def _site_schema(values: dict[str, Any], with_name: bool) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if with_name:
        fields[vol.Required(CONF_NAME, default=values.get(CONF_NAME, NAME))] = str
    fields.update(
        {
            vol.Required(CONF_LATITUDE, default=values[CONF_LATITUDE]): _num(
                -90, 90, "any"
            ),
            vol.Required(CONF_LONGITUDE, default=values[CONF_LONGITUDE]): _num(
                -180, 180, "any"
            ),
            _opt(CONF_WEATHER, values): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            _opt(CONF_WIND_SENSOR, values): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="wind_speed"
                )
            ),
        }
    )
    return vol.Schema(fields)


def _validate_site(user_input: dict[str, Any]) -> dict[str, str]:
    if not user_input.get(CONF_WEATHER) and not user_input.get(CONF_WIND_SENSOR):
        return {"base": "wind_source_required"}
    return {}


def _thresholds_schema(values: dict[str, Any]) -> vol.Schema:
    v = {**SITE_DEFAULTS, **values}
    kmh = UnitOfSpeed.KILOMETERS_PER_HOUR
    return vol.Schema(
        {
            vol.Required(CONF_WIND_STOW, default=v[CONF_WIND_STOW]): _num(
                5, 250, 1, kmh
            ),
            vol.Required(CONF_WIND_RESUME, default=v[CONF_WIND_RESUME]): _num(
                0, 250, 1, kmh
            ),
            vol.Required(CONF_CALM_MINUTES, default=v[CONF_CALM_MINUTES]): _num(
                0, 240, 1, "min"
            ),
            vol.Required(CONF_STORM_SPEED, default=v[CONF_STORM_SPEED]): _num(
                5, 300, 1, kmh
            ),
            vol.Required(CONF_STORM_HOLD, default=v[CONF_STORM_HOLD]): _num(
                0, 72, 0.5, "h"
            ),
            vol.Required(CONF_STALE_MINUTES, default=v[CONF_STALE_MINUTES]): _num(
                5, 1440, 1, "min"
            ),
            vol.Required(CONF_SNOW_MODE, default=v[CONF_SNOW_MODE]): bool,
            vol.Required(CONF_RAIN_MODE, default=v[CONF_RAIN_MODE]): bool,
            vol.Required(CONF_FROST_MODE, default=v[CONF_FROST_MODE]): bool,
            vol.Required(CONF_FROST_TEMP, default=v[CONF_FROST_TEMP]): _num(
                -30, 10, 0.5, "°C"
            ),
            vol.Required(CONF_CLOUD_THRESHOLD, default=v[CONF_CLOUD_THRESHOLD]): _num(
                0, 100, 1, "%"
            ),
            vol.Required(CONF_MIN_INTERVAL, default=v[CONF_MIN_INTERVAL]): _num(
                0, 240, 1, "min"
            ),
            vol.Required(CONF_MANUAL_PAUSE, default=v[CONF_MANUAL_PAUSE]): _num(
                0, 1440, 1, "min"
            ),
            vol.Required(CONF_DEADBAND, default=v[CONF_DEADBAND]): _num(
                0, 20, 0.5, "°"
            ),
            vol.Required(CONF_HYSTERESIS, default=v[CONF_HYSTERESIS]): _num(
                0, 10, 0.5, "°"
            ),
        }
    )


def _validate_thresholds(user_input: dict[str, Any]) -> dict[str, str]:
    if user_input[CONF_WIND_RESUME] >= user_input[CONF_WIND_STOW]:
        return {CONF_WIND_RESUME: "resume_above_stow"}
    if user_input[CONF_STORM_SPEED] < user_input[CONF_WIND_STOW]:
        return {CONF_STORM_SPEED: "storm_below_stow"}
    return {}


# ---- panel ---------------------------------------------------------------------
#
# Three steps: (1) name and actuator type, (2) the fields for that type plus the
# geometry, (3) positions (defaults clamped to the limits) and the PV comparison.

STEP_ENTITY = "entity"
STEP_RELAYS = "relays"
STEP_POSITIONS = "positions"
SECTION_RELAY_ADVANCED = "relay_advanced"
SECTION_MAPPING = "mapping_feedback"
SECTION_PV = "pv"
SECTIONS = (SECTION_RELAY_ADVANCED, SECTION_MAPPING, SECTION_PV)

RELAY_KEYS = (
    CONF_OPEN_SWITCH,
    CONF_CLOSE_SWITCH,
    CONF_OPEN_COUNTDOWN,
    CONF_CLOSE_COUNTDOWN,
    CONF_OPEN_TIME,
    CONF_CLOSE_TIME,
    CONF_ANGLE_CLOSED,
    CONF_ANGLE_OPEN,
    CONF_START_DELAY,
    CONF_HOME_OVERRUN,
    CONF_REVERSE_DELAY,
    CONF_HOME_AFTER_MOVES,
    CONF_HOME_AT_NIGHT,
    CONF_HOME_END,
)
ENTITY_KEYS = (
    CONF_ACTUATOR,
    CONF_POS_AT_MIN,
    CONF_POS_AT_MAX,
    CONF_FEEDBACK,
    CONF_FEEDBACK_KIND,
    CONF_TRAVEL_TIME,
)
ANGLE_POSITION_KEYS = (
    CONF_STOW_ANGLE,
    CONF_NIGHT_ANGLE,
    CONF_DIFFUSE_ANGLE,
    CONF_SNOW_ANGLE,
    CONF_RAIN_ANGLE,
    CONF_FROST_ANGLE,
    CONF_WINTER_ANGLE,
    CONF_SUMMER_ANGLE,
)
OPTIONAL_KEYS = (
    CONF_FEEDBACK,
    CONF_PV_POWER,
    CONF_CALIBRATION,
    CONF_ACTUATOR,
    CONF_OPEN_SWITCH,
    CONF_CLOSE_SWITCH,
    CONF_OPEN_COUNTDOWN,
    CONF_CLOSE_COUNTDOWN,
)


def _type_schema(values: dict[str, Any]) -> vol.Schema:
    v = {**PANEL_DEFAULTS, **values}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=v.get(CONF_NAME, "Panel")): str,
            vol.Required(CONF_ACTUATOR_TYPE, default=v[CONF_ACTUATOR_TYPE]): _choice(
                ACTUATOR_TYPES, CONF_ACTUATOR_TYPE
            ),
        }
    )


def _geometry(v: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Required(CONF_AXIS, default=v[CONF_AXIS]): _choice(AXES, CONF_AXIS),
        vol.Required(CONF_AZIMUTH, default=v[CONF_AZIMUTH]): _num(0, 359, 1, "°"),
        vol.Required(CONF_MIN_ANGLE, default=v[CONF_MIN_ANGLE]): _angle(),
        vol.Required(CONF_MAX_ANGLE, default=v[CONF_MAX_ANGLE]): _angle(),
        vol.Required(CONF_STEP, default=v[CONF_STEP]): _num(0, 30, 0.5, "°"),
        vol.Required(CONF_STRATEGY, default=v[CONF_STRATEGY]): _choice(
            STRATEGIES, CONF_STRATEGY
        ),
    }


def _calibration_field(v: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Required(CONF_MAPPING, default=v[CONF_MAPPING]): _choice(
            [MAPPING_LINEAR, MAPPING_TABLE], CONF_MAPPING
        ),
        _opt(CONF_CALIBRATION, v): selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        ),
    }


def _entity_schema(values: dict[str, Any]) -> vol.Schema:
    """A cover, number or script: the entity and how positions map to angles."""
    v = {**PANEL_DEFAULTS, **values}
    fields: dict[Any, Any] = {
        (
            vol.Required(CONF_ACTUATOR, default=v[CONF_ACTUATOR])
            if v.get(CONF_ACTUATOR)
            else vol.Required(CONF_ACTUATOR)
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["cover", "number", "input_number", "script"]
            )
        ),
        **_geometry(v),
    }
    mapping: dict[Any, Any] = {
        **_calibration_field(v),
        vol.Required(CONF_POS_AT_MIN, default=v[CONF_POS_AT_MIN]): _num(
            -10000, 10000, 0.1
        ),
        vol.Required(CONF_POS_AT_MAX, default=v[CONF_POS_AT_MAX]): _num(
            -10000, 10000, 0.1
        ),
        _opt(CONF_FEEDBACK, v): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "number", "input_number"])
        ),
        vol.Required(CONF_FEEDBACK_KIND, default=v[CONF_FEEDBACK_KIND]): _choice(
            [FEEDBACK_POSITION, FEEDBACK_ANGLE], CONF_FEEDBACK_KIND
        ),
        vol.Required(CONF_TRAVEL_TIME, default=v[CONF_TRAVEL_TIME]): _num(
            1, 3600, 1, "s"
        ),
    }
    fields[vol.Required(SECTION_MAPPING)] = section(
        vol.Schema(mapping), {"collapsed": False}
    )
    return vol.Schema(fields)


def _relays_schema(values: dict[str, Any]) -> vol.Schema:
    """Two relays: the switches, countdowns, travel times and end angles."""
    v = {**PANEL_DEFAULTS, **values}
    switch = selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["switch", "input_boolean"])
    )
    countdown = selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["number", "input_number"])
    )

    def req(key: str) -> vol.Marker:
        if v.get(key):
            return vol.Required(key, default=v[key])
        return vol.Required(key)

    fields: dict[Any, Any] = {
        req(CONF_OPEN_SWITCH): switch,
        req(CONF_CLOSE_SWITCH): switch,
        _opt(CONF_OPEN_COUNTDOWN, v): countdown,
        _opt(CONF_CLOSE_COUNTDOWN, v): countdown,
        vol.Required(CONF_OPEN_TIME, default=v[CONF_OPEN_TIME]): _num(1, 600, 0.1, "s"),
        vol.Required(CONF_CLOSE_TIME, default=v[CONF_CLOSE_TIME]): _num(
            1, 600, 0.1, "s"
        ),
        vol.Required(CONF_ANGLE_CLOSED, default=v[CONF_ANGLE_CLOSED]): _angle(),
        vol.Required(CONF_ANGLE_OPEN, default=v[CONF_ANGLE_OPEN]): _angle(),
        **_geometry(v),
    }
    advanced: dict[Any, Any] = {
        vol.Required(CONF_START_DELAY, default=v[CONF_START_DELAY]): _num(
            0, 10, 0.1, "s"
        ),
        vol.Required(CONF_HOME_OVERRUN, default=v[CONF_HOME_OVERRUN]): _num(
            5, 50, 1, "%"
        ),
        vol.Required(CONF_REVERSE_DELAY, default=v[CONF_REVERSE_DELAY]): _num(
            0.3, 10, 0.1, "s"
        ),
        vol.Required(CONF_HOME_AFTER_MOVES, default=v[CONF_HOME_AFTER_MOVES]): _num(
            0, 500, 1
        ),
        vol.Required(CONF_HOME_AT_NIGHT, default=v[CONF_HOME_AT_NIGHT]): bool,
        vol.Required(CONF_HOME_END, default=v[CONF_HOME_END]): _choice(
            HOME_ENDS, CONF_HOME_END
        ),
        **_calibration_field(v),
    }
    fields[vol.Required(SECTION_RELAY_ADVANCED)] = section(
        vol.Schema(advanced), {"collapsed": True}
    )
    return vol.Schema(fields)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def season_suggestion(latitude: float, lo: float, hi: float) -> tuple[float, float]:
    """Winter and summer angles for a latitude: about lat+15 and lat-35."""
    lat = abs(latitude)
    winter = _clamp(round(lat + 15), max(lo, 0), min(hi, 90))
    summer = _clamp(round(lat - 35), max(lo, 0), min(hi, 90))
    return winter, summer


def _position_values(
    data: dict[str, Any], latitude: float, fresh: bool
) -> dict[str, Any]:
    """Step 3 defaults: saved (or default) angles, clamped to the soft limits."""
    v = {**PANEL_DEFAULTS, **data}
    lo, hi = v[CONF_MIN_ANGLE], v[CONF_MAX_ANGLE]
    if fresh and v[CONF_AXIS] != AXIS_ROLL:
        v[CONF_WINTER_ANGLE], v[CONF_SUMMER_ANGLE] = season_suggestion(latitude, lo, hi)
    for key in ANGLE_POSITION_KEYS:
        v[key] = _clamp(v[key], lo, hi)
    return v


def _positions_schema(v: dict[str, Any]) -> vol.Schema:
    lo, hi = v[CONF_MIN_ANGLE], v[CONF_MAX_ANGLE]
    fields: dict[Any, Any] = {
        vol.Required(key, default=v[key]): _angle(lo, hi) for key in ANGLE_POSITION_KEYS
    }
    fields[vol.Required(CONF_SEASON_WEIGHT, default=v[CONF_SEASON_WEIGHT])] = _num(
        0, 100, 1, "%", box=False
    )
    pv: dict[Any, Any] = {
        _opt(CONF_PV_POWER, v): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="power")
        ),
        vol.Required(CONF_PV_PEAK, default=v[CONF_PV_PEAK]): _num(0, 1000000, 10, "W"),
    }
    fields[vol.Required(SECTION_PV)] = section(vol.Schema(pv), {"collapsed": True})
    return vol.Schema(fields)


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    data = {k: v for k, v in user_input.items() if k not in SECTIONS}
    for name in SECTIONS:
        data.update(user_input.get(name, {}))
    # Cleared optional fields: drop them so defaults apply.
    for key in OPTIONAL_KEYS:
        if key in data and not data[key]:
            data.pop(key)
    return data


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    """Keep only the keys of the chosen actuator type."""
    data = dict(data)
    data.setdefault(CONF_ACTUATOR_TYPE, ACTUATOR_ENTITY)
    drop = ENTITY_KEYS if data[CONF_ACTUATOR_TYPE] == ACTUATOR_RELAYS else RELAY_KEYS
    for key in drop:
        data.pop(key, None)
    for key in OPTIONAL_KEYS:
        if key in data and not data[key]:
            data.pop(key)
    return data


def _unique_id(data: dict[str, Any]) -> str:
    """The actuator (or the open relay) identifies a panel."""
    if data[CONF_ACTUATOR_TYPE] == ACTUATOR_RELAYS:
        return data[CONF_OPEN_SWITCH]
    return data[CONF_ACTUATOR]


def _validate_relays(data: dict[str, Any]) -> dict[str, str]:
    open_switch, close_switch = data.get(CONF_OPEN_SWITCH), data.get(CONF_CLOSE_SWITCH)
    if not open_switch or not close_switch:
        return {"base": "relays_required"}
    if open_switch == close_switch:
        return {CONF_CLOSE_SWITCH: "same_relay"}
    countdowns = [data.get(CONF_OPEN_COUNTDOWN), data.get(CONF_CLOSE_COUNTDOWN)]
    if countdowns[0] and countdowns[0] == countdowns[1]:
        return {CONF_CLOSE_COUNTDOWN: "same_countdown"}
    closed, opened = data[CONF_ANGLE_CLOSED], data[CONF_ANGLE_OPEN]
    if closed == opened:
        return {CONF_ANGLE_OPEN: "same_end_angles"}
    lo, hi = sorted((closed, opened))
    if data[CONF_MIN_ANGLE] < lo - 0.5 or data[CONF_MAX_ANGLE] > hi + 0.5:
        return {"base": "limits_outside_stroke"}
    return {}


def _validate_actuator(data: dict[str, Any]) -> dict[str, str]:
    """Step 2: the actuator fields and the geometry."""
    if data[CONF_ACTUATOR_TYPE] == ACTUATOR_RELAYS:
        if errors := _validate_relays(data):
            return errors
    elif not data.get(CONF_ACTUATOR):
        return {CONF_ACTUATOR: "actuator_required"}
    lo, hi = data[CONF_MIN_ANGLE], data[CONF_MAX_ANGLE]
    if hi <= lo:
        return {CONF_MAX_ANGLE: "max_below_min"}
    if data[CONF_AXIS] != AXIS_ROLL and (lo < 0 or hi > 90):
        return {CONF_MIN_ANGLE: "tilt_range"}
    if data.get(CONF_MAPPING) == MAPPING_TABLE and not data.get(CONF_CALIBRATION):
        return {"base": "calibration_required"}
    try:
        PanelConfig.from_data(data).build_mapping()
    except MappingError:
        return {"base": "invalid_mapping"}
    return {}


def _validate_positions(data: dict[str, Any]) -> dict[str, str]:
    lo, hi = data[CONF_MIN_ANGLE], data[CONF_MAX_ANGLE]
    for key in ANGLE_POSITION_KEYS:
        if not lo - 1e-6 <= data[key] <= hi + 1e-6:
            return {key: "outside_limits"}
    return {}


class PanelSteps:
    """The panel steps, shared by the first-panel step and the subentry flows."""

    _panel: dict[str, Any]
    _reconfiguring: bool = False
    _season_ok: tuple[float, float] | None = None

    # Hooks
    def _latitude(self) -> float:
        raise NotImplementedError

    def _actuator_taken(self, unique_id: str) -> bool:
        return False

    async def _async_finish(self, title: str, data: dict[str, Any]) -> Any:
        raise NotImplementedError

    def _initial(self) -> dict[str, Any]:
        return {}

    # Step 1 is the flow's own (panel / user / settings); it calls this.
    async def _async_type_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> Any:
        if user_input is not None:
            previous = self._panel.get(CONF_ACTUATOR_TYPE)
            self._panel = {**self._panel, **user_input}
            if previous and previous != user_input[CONF_ACTUATOR_TYPE]:
                # Another type: start its fields from the defaults.
                for key in (*RELAY_KEYS, *ENTITY_KEYS, CONF_MAPPING, CONF_CALIBRATION):
                    self._panel.pop(key, None)
            if user_input[CONF_ACTUATOR_TYPE] == ACTUATOR_RELAYS:
                return await self.async_step_relays()
            return await self.async_step_entity()
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id=step_id, data_schema=_type_schema(self._panel)
        )

    async def _async_actuator_step(
        self, step_id: str, schema: Any, user_input: dict[str, Any] | None
    ) -> Any:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._panel, **_flatten(user_input)}
            for key in OPTIONAL_KEYS:  # cleared on this form
                if key not in _flatten(user_input) and key in _form_keys(schema):
                    data.pop(key, None)
            errors = _validate_actuator(data)
            if not errors and self._actuator_taken(_unique_id(data)):
                errors = {"base": "actuator_in_use"}
            self._panel = data
            if not errors:
                return await self.async_step_positions()
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id=step_id,
            data_schema=schema(self._panel),
            errors=errors,
            description_placeholders={"name": self._panel.get(CONF_NAME, "")},
        )

    async def async_step_entity(self, user_input: dict[str, Any] | None = None) -> Any:
        """Step 2 for a cover, number or script."""
        return await self._async_actuator_step(STEP_ENTITY, _entity_schema, user_input)

    async def async_step_relays(self, user_input: dict[str, Any] | None = None) -> Any:
        """Step 2 for two relays."""
        return await self._async_actuator_step(STEP_RELAYS, _relays_schema, user_input)

    async def async_step_positions(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Step 3: positions and the seasonal curve, inside the soft limits."""
        errors: dict[str, str] = {}
        lo, hi = self._panel[CONF_MIN_ANGLE], self._panel[CONF_MAX_ANGLE]
        winter, summer = season_suggestion(self._latitude(), lo, hi)
        if user_input is not None:
            flat = _flatten(user_input)
            data = {**self._panel, **flat}
            if CONF_PV_POWER not in flat:
                data.pop(CONF_PV_POWER, None)
            errors = _validate_positions(data)
            pair = (data[CONF_WINTER_ANGLE], data[CONF_SUMMER_ANGLE])
            if not errors and pair[0] == pair[1] and self._season_ok != pair:
                # A hint, once: submit again to keep a flat seasonal curve.
                self._season_ok = pair
                errors = {"base": "season_flat"}
            self._panel = data
            if not errors:
                clean = _clean(data)
                title = clean.pop(CONF_NAME)
                return await self._async_finish(title, clean)
            values = data
        else:
            values = _position_values(
                self._panel, self._latitude(), fresh=not self._reconfiguring
            )
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id=STEP_POSITIONS,
            data_schema=_positions_schema({**PANEL_DEFAULTS, **values}),
            errors=errors,
            description_placeholders={
                "min": f"{lo:g}",
                "max": f"{hi:g}",
                "latitude": f"{self._latitude():.1f}",
                "winter": f"{winter:g}",
                "summer": f"{summer:g}",
            },
        )


def _form_keys(schema: Any) -> set[str]:
    """Every field (also inside sections) of a step-2 schema."""
    keys: set[str] = set()
    for marker, value in schema({}).schema.items():
        if isinstance(value, section):
            keys |= {str(k) for k in value.schema.schema}
        else:
            keys.add(str(marker))
    return keys


class HeliosConfigFlow(PanelSteps, ConfigFlow, domain=DOMAIN):
    """Site, then the first panel."""

    VERSION = 1

    def __init__(self) -> None:
        """Start."""
        self._site: dict[str, Any] = {}
        self._panel = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HeliosOptionsFlow:
        """Thresholds."""
        return HeliosOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Panels are subentries."""
        return {SUBENTRY_PANEL: PanelSubentryFlow}

    def _site_defaults(self) -> dict[str, Any]:
        return {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
        }

    def _latitude(self) -> float:
        return float(self._site.get(CONF_LATITUDE, self.hass.config.latitude))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Location and weather."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_site(user_input)
            if not errors:
                self._site = user_input
                return await self.async_step_panel()
        values = {**self._site_defaults(), **(user_input or {})}
        return self.async_show_form(
            step_id="user", data_schema=_site_schema(values, True), errors=errors
        )

    async def async_step_panel(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The first panel: its name and actuator type."""
        return await self._async_type_step("panel", user_input)

    async def _async_finish(self, title: str, data: dict[str, Any]) -> ConfigFlowResult:
        site = dict(self._site)
        name = site.pop(CONF_NAME)
        return self.async_create_entry(
            title=name,
            data=site,
            subentries=[
                ConfigSubentryData(
                    data=data,
                    subentry_type=SUBENTRY_PANEL,
                    title=title,
                    unique_id=_unique_id(data),
                )
            ],
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change location or weather sources."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_site(user_input)
            if not errors:
                data = {k: v for k, v in user_input.items() if v not in (None, "")}
                return self.async_update_and_abort(entry, data=data)
        values = {**self._site_defaults(), **entry.data, **(user_input or {})}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_site_schema(values, False),
            errors=errors,
        )


class HeliosOptionsFlow(OptionsFlow):
    """Safety thresholds and timing."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """One form."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_thresholds(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)
        values = {**self.config_entry.options, **(user_input or {})}
        return self.async_show_form(
            step_id="init", data_schema=_thresholds_schema(values), errors=errors
        )


class PanelSubentryFlow(PanelSteps, ConfigSubentryFlow):
    """Add or change a panel."""

    def __init__(self) -> None:
        """Start."""
        self._panel = {}

    def _latitude(self) -> float:
        entry = self._get_entry()
        return float(entry.data.get(CONF_LATITUDE, self.hass.config.latitude))

    def _actuator_taken(self, unique_id: str) -> bool:
        exclude = (
            self._get_reconfigure_subentry().subentry_id
            if self._reconfiguring
            else None
        )
        return any(
            s.unique_id == unique_id and s.subentry_id != exclude
            for s in self._get_entry().subentries.values()
        )

    async def _async_finish(
        self, title: str, data: dict[str, Any]
    ) -> SubentryFlowResult:
        if not self._reconfiguring:
            return self.async_create_entry(
                title=title, data=data, unique_id=_unique_id(data)
            )
        return self.async_update_and_abort(
            self._get_entry(),
            self._get_reconfigure_subentry(),
            title=title,
            data=data,
            unique_id=_unique_id(data),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """New panel: name and actuator type."""
        return await self._async_type_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change a panel; relay panels can also time their travel."""
        subentry = self._get_reconfigure_subentry()
        if subentry.data.get(CONF_ACTUATOR_TYPE) == ACTUATOR_RELAYS:
            return self.async_show_menu(
                step_id="reconfigure", menu_options=["settings", "travel"]
            )
        return await self.async_step_settings(user_input)

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change a panel: name and actuator type first."""
        if not self._reconfiguring:
            subentry = self._get_reconfigure_subentry()
            self._reconfiguring = True
            self._panel = {CONF_NAME: subentry.title, **subentry.data}
            self._panel.setdefault(CONF_ACTUATOR_TYPE, ACTUATOR_ENTITY)
        return await self._async_type_step("settings", user_input)

    # ---- guided travel-time calibration (two relays) -------------------------------

    def _loaded_panel(self) -> tuple[Any, Any] | None:
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return None
        site = entry.runtime_data
        panel = site.panels.get(self._get_reconfigure_subentry().subentry_id)
        if panel is None or panel.driver is None:
            return None
        return site, panel

    async def async_step_travel(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Explain, then close fully (homing) and start opening."""
        found = self._loaded_panel()
        if found is None:
            return self.async_abort(reason="not_loaded")
        site, panel = found
        default = round(panel.driver.cfg.max_run)
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                site.async_travel_calibration(
                    panel, "start", user_input[ATTR_HOMING], autosave=False
                )
            except HomeAssistantError:
                errors = {"base": "relays_unavailable"}
            else:
                self._calibrating = True
                return await self.async_step_travel_open()
        return self.async_show_form(
            step_id="travel",
            data_schema=vol.Schema(
                {vol.Required(ATTR_HOMING, default=default): _num(5, 300, 1, "s")}
            ),
            errors=errors,
            description_placeholders={
                "panel": panel.title,
                "entities": ", ".join(panel.driver.unavailable) or "-",
            },
        )

    async def _async_mark(
        self, phase: str, user_input: dict[str, Any] | None
    ) -> dict[str, str] | None:
        """Submit = the end is reached. None when marked, else form errors."""
        found = self._loaded_panel()
        if found is None:
            return {"base": "calibration_failed"}
        _site, panel = found
        cal = panel.driver.calibration
        if user_input is None:
            return {}
        if cal is None:
            return {"base": "calibration_failed"}
        if cal["phase"] == "homing" or (
            cal["phase"] == phase and "timing_started" not in cal
        ):
            return {"base": "still_homing"}
        if cal["phase"] != phase:
            return {"base": "calibration_failed"}
        if not panel.driver.async_calibration_mark():
            return {"base": "still_homing"}  # the relay is not on yet
        return None

    async def async_step_travel_open(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Submit the moment the actuator reaches the open end."""
        errors = await self._async_mark("opening", user_input)
        if errors is None:
            return await self.async_step_travel_close()
        if errors.get("base") == "calibration_failed":
            return self.async_abort(reason="calibration_failed")
        return self.async_show_form(
            step_id="travel_open", data_schema=vol.Schema({}), errors=errors
        )

    async def async_step_travel_close(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Submit the moment the actuator reaches the closed end."""
        errors = await self._async_mark("closing", user_input)
        if errors is None:
            return await self.async_step_travel_result()
        if errors.get("base") == "calibration_failed":
            return self.async_abort(reason="calibration_failed")
        return self.async_show_form(
            step_id="travel_close", data_schema=vol.Schema({}), errors=errors
        )

    async def async_step_travel_result(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """The measured times (editable) and the angles at both ends."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        values = {**PANEL_DEFAULTS, **subentry.data}
        if user_input is not None:
            self._calibrating = False
            return self.async_update_and_abort(
                entry, subentry, data={**subentry.data, **user_input}
            )
        found = self._loaded_panel()
        cal = (found[1].driver.calibration if found else None) or {}
        return self.async_show_form(
            step_id="travel_result",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_OPEN_TIME,
                        default=cal.get("open_time") or values[CONF_OPEN_TIME],
                    ): _num(1, 600, 0.1, "s"),
                    vol.Required(
                        CONF_CLOSE_TIME,
                        default=cal.get("close_time") or values[CONF_CLOSE_TIME],
                    ): _num(1, 600, 0.1, "s"),
                    vol.Required(
                        CONF_ANGLE_CLOSED, default=values[CONF_ANGLE_CLOSED]
                    ): _angle(),
                    vol.Required(
                        CONF_ANGLE_OPEN, default=values[CONF_ANGLE_OPEN]
                    ): _angle(),
                }
            ),
        )

    @callback
    def async_remove(self) -> None:
        """The dialog was closed mid-calibration: stop the relays."""
        if not getattr(self, "_calibrating", False):
            return
        found = self._loaded_panel()
        if found is not None and found[1].driver.calibrating:
            found[0].async_travel_calibration(found[1], "cancel")
