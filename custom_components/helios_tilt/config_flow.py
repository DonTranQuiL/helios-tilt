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

SECTION_RELAYS = "relays"
SECTION_MAPPING = "mapping_feedback"
SECTION_POSITIONS = "positions"
SECTION_PV = "pv"
SECTIONS = (SECTION_RELAYS, SECTION_MAPPING, SECTION_POSITIONS, SECTION_PV)

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

MAPPING_KEYS = (
    CONF_MAPPING,
    CONF_POS_AT_MIN,
    CONF_POS_AT_MAX,
    CONF_CALIBRATION,
    CONF_FEEDBACK,
    CONF_FEEDBACK_KIND,
    CONF_TRAVEL_TIME,
)
POSITION_KEYS = (
    CONF_STOW_ANGLE,
    CONF_NIGHT_ANGLE,
    CONF_DIFFUSE_ANGLE,
    CONF_SNOW_ANGLE,
    CONF_RAIN_ANGLE,
    CONF_FROST_ANGLE,
    CONF_WINTER_ANGLE,
    CONF_SUMMER_ANGLE,
    CONF_SEASON_WEIGHT,
)
PV_KEYS = (CONF_PV_POWER, CONF_PV_PEAK)
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


def _panel_schema(values: dict[str, Any], with_name: bool) -> vol.Schema:
    v = {**PANEL_DEFAULTS, **values}
    fields: dict[Any, Any] = {}
    if with_name:
        fields[vol.Required(CONF_NAME, default=v.get(CONF_NAME, "Panel"))] = str
    fields.update(
        {
            vol.Required(CONF_ACTUATOR_TYPE, default=v[CONF_ACTUATOR_TYPE]): _choice(
                ACTUATOR_TYPES, CONF_ACTUATOR_TYPE
            ),
            _opt(CONF_ACTUATOR, v): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["cover", "number", "input_number", "script"]
                )
            ),
            vol.Required(CONF_AXIS, default=v[CONF_AXIS]): _choice(AXES, CONF_AXIS),
            vol.Required(CONF_AZIMUTH, default=v[CONF_AZIMUTH]): _num(0, 359, 1, "°"),
            vol.Required(CONF_MIN_ANGLE, default=v[CONF_MIN_ANGLE]): _angle(),
            vol.Required(CONF_MAX_ANGLE, default=v[CONF_MAX_ANGLE]): _angle(),
            vol.Required(CONF_STEP, default=v[CONF_STEP]): _num(0, 30, 0.5, "°"),
            vol.Required(CONF_STRATEGY, default=v[CONF_STRATEGY]): _choice(
                STRATEGIES, CONF_STRATEGY
            ),
        }
    )
    switch = selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["switch", "input_boolean"])
    )
    countdown = selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["number", "input_number"])
    )
    relays: dict[Any, Any] = {
        _opt(CONF_OPEN_SWITCH, v): switch,
        _opt(CONF_CLOSE_SWITCH, v): switch,
        _opt(CONF_OPEN_COUNTDOWN, v): countdown,
        _opt(CONF_CLOSE_COUNTDOWN, v): countdown,
        vol.Required(CONF_OPEN_TIME, default=v[CONF_OPEN_TIME]): _num(1, 600, 0.1, "s"),
        vol.Required(CONF_CLOSE_TIME, default=v[CONF_CLOSE_TIME]): _num(
            1, 600, 0.1, "s"
        ),
        vol.Required(CONF_ANGLE_CLOSED, default=v[CONF_ANGLE_CLOSED]): _angle(),
        vol.Required(CONF_ANGLE_OPEN, default=v[CONF_ANGLE_OPEN]): _angle(),
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
    }
    mapping: dict[Any, Any] = {
        vol.Required(CONF_MAPPING, default=v[CONF_MAPPING]): _choice(
            [MAPPING_LINEAR, MAPPING_TABLE], CONF_MAPPING
        ),
        vol.Required(CONF_POS_AT_MIN, default=v[CONF_POS_AT_MIN]): _num(
            -10000, 10000, 0.1
        ),
        vol.Required(CONF_POS_AT_MAX, default=v[CONF_POS_AT_MAX]): _num(
            -10000, 10000, 0.1
        ),
        _opt(CONF_CALIBRATION, v): selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
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
    positions: dict[Any, Any] = {
        vol.Required(key, default=v[key]): (
            _num(0, 100, 1, "%", box=False) if key == CONF_SEASON_WEIGHT else _angle()
        )
        for key in POSITION_KEYS
    }
    pv: dict[Any, Any] = {
        _opt(CONF_PV_POWER, v): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="power")
        ),
        vol.Required(CONF_PV_PEAK, default=v[CONF_PV_PEAK]): _num(0, 1000000, 10, "W"),
    }
    fields[vol.Required(SECTION_RELAYS)] = section(
        vol.Schema(relays),
        {"collapsed": v[CONF_ACTUATOR_TYPE] != ACTUATOR_RELAYS},
    )
    fields[vol.Required(SECTION_MAPPING)] = section(
        vol.Schema(mapping), {"collapsed": True}
    )
    fields[vol.Required(SECTION_POSITIONS)] = section(
        vol.Schema(positions), {"collapsed": True}
    )
    fields[vol.Required(SECTION_PV)] = section(vol.Schema(pv), {"collapsed": True})
    return vol.Schema(fields)


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    data = {k: v for k, v in user_input.items() if k not in SECTIONS}
    for name in SECTIONS:
        data.update(user_input.get(name, {}))
    # Cleared optional fields: drop them so defaults apply.
    for key in (
        CONF_FEEDBACK,
        CONF_PV_POWER,
        CONF_CALIBRATION,
        CONF_ACTUATOR,
        CONF_OPEN_SWITCH,
        CONF_CLOSE_SWITCH,
        CONF_OPEN_COUNTDOWN,
        CONF_CLOSE_COUNTDOWN,
    ):
        if not data.get(key):
            data.pop(key, None)
    data.setdefault(CONF_ACTUATOR_TYPE, ACTUATOR_ENTITY)
    if data[CONF_ACTUATOR_TYPE] == ACTUATOR_RELAYS:
        data.pop(CONF_ACTUATOR, None)
    else:
        for key in RELAY_KEYS:
            data.pop(key, None)
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
        return {"base": "same_relay"}
    countdowns = [data.get(CONF_OPEN_COUNTDOWN), data.get(CONF_CLOSE_COUNTDOWN)]
    if countdowns[0] and countdowns[0] == countdowns[1]:
        return {"base": "same_countdown"}
    closed, opened = data[CONF_ANGLE_CLOSED], data[CONF_ANGLE_OPEN]
    if closed == opened:
        return {"base": "same_end_angles"}
    lo, hi = sorted((closed, opened))
    if data[CONF_MIN_ANGLE] < lo - 0.5 or data[CONF_MAX_ANGLE] > hi + 0.5:
        return {"base": "limits_outside_stroke"}
    return {}


def _validate_panel(data: dict[str, Any]) -> dict[str, str]:
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
    if data[CONF_MAPPING] == MAPPING_TABLE and not data.get(CONF_CALIBRATION):
        return {"base": "calibration_required"}
    try:
        PanelConfig.from_data(data).build_mapping()
    except MappingError:
        return {"base": "invalid_mapping"}
    return {}


class HeliosConfigFlow(ConfigFlow, domain=DOMAIN):
    """Site, then the first panel."""

    VERSION = 1

    def __init__(self) -> None:
        """Start."""
        self._site: dict[str, Any] = {}

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
        """The first panel."""
        errors: dict[str, str] = {}
        values: dict[str, Any] = {}
        if user_input is not None:
            data = _flatten(user_input)
            values = data
            errors = _validate_panel(data)
            if not errors:
                title = data.pop(CONF_NAME)
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
        return self.async_show_form(
            step_id="panel", data_schema=_panel_schema(values, True), errors=errors
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


class PanelSubentryFlow(ConfigSubentryFlow):
    """Add or change a panel."""

    def _taken(self, actuator: str, exclude: str | None = None) -> bool:
        return any(
            s.unique_id == actuator and s.subentry_id != exclude
            for s in self._get_entry().subentries.values()
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """New panel."""
        errors: dict[str, str] = {}
        values: dict[str, Any] = {}
        if user_input is not None:
            data = _flatten(user_input)
            values = data
            errors = _validate_panel(data)
            if not errors and self._taken(_unique_id(data)):
                errors = {"base": "actuator_in_use"}
            if not errors:
                title = data.pop(CONF_NAME)
                return self.async_create_entry(
                    title=title, data=data, unique_id=_unique_id(data)
                )
        return self.async_show_form(
            step_id="user", data_schema=_panel_schema(values, True), errors=errors
        )

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
        """Change a panel's settings."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        values: dict[str, Any] = {CONF_NAME: subentry.title, **subentry.data}
        if user_input is not None:
            data = _flatten(user_input)
            values = data
            errors = _validate_panel(data)
            if not errors and self._taken(_unique_id(data), subentry.subentry_id):
                errors = {"base": "actuator_in_use"}
            if not errors:
                title = data.pop(CONF_NAME)
                return self.async_update_and_abort(
                    entry,
                    subentry,
                    title=title,
                    data=data,
                    unique_id=_unique_id(data),
                )
        return self.async_show_form(
            step_id="settings",
            data_schema=_panel_schema(values, True),
            errors=errors,
        )

    # ---- guided travel-time calibration (two relays) -------------------------------

    def _panel(self) -> tuple[Any, Any] | None:
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
        found = self._panel()
        if found is None:
            return self.async_abort(reason="not_loaded")
        site, panel = found
        default = round(panel.driver.cfg.max_run)
        if user_input is not None:
            self._calibrating = True
            site.async_travel_calibration(
                panel, "start", user_input[ATTR_HOMING], autosave=False
            )
            return await self.async_step_travel_open()
        return self.async_show_form(
            step_id="travel",
            data_schema=vol.Schema(
                {vol.Required(ATTR_HOMING, default=default): _num(5, 300, 1, "s")}
            ),
            description_placeholders={"panel": panel.title},
        )

    async def _async_mark(
        self, phase: str, user_input: dict[str, Any] | None
    ) -> dict[str, str] | None:
        """Submit = the end is reached. None when marked, else form errors."""
        found = self._panel()
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
        found = self._panel()
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
        found = self._panel()
        if found is not None and found[1].driver.calibrating:
            found[0].async_travel_calibration(found[1], "cancel")
