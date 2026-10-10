"""Constants for Helios Tilt."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "helios_tilt"
NAME: Final = "Helios Tilt"
VERSION = "0.1.0b6"
LOGGER = logging.getLogger(__package__)

PLATFORMS: Final = ["binary_sensor", "button", "number", "select", "sensor", "switch"]
SUBENTRY_PANEL: Final = "panel"

CARD_FILENAME: Final = "helios-tilt-card.js"
CARD_URL: Final = f"/{DOMAIN}/{CARD_FILENAME}"

EVENT_MOVE: Final = f"{DOMAIN}_move"
TICK_SECONDS: Final = 60
STORE_VERSION: Final = 1

# ---- site (config entry data / options) ------------------------------------
CONF_NAME: Final = "name"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_WEATHER: Final = "weather_entity"
CONF_WIND_SENSOR: Final = "wind_sensor"

CONF_WIND_STOW: Final = "wind_stow_speed"  # km/h
CONF_WIND_RESUME: Final = "wind_resume_speed"  # km/h
CONF_CALM_MINUTES: Final = "calm_minutes"
CONF_STORM_SPEED: Final = "storm_speed"  # km/h
CONF_STORM_HOLD: Final = "storm_hold_hours"  # 0 = clear by hand only
CONF_STALE_MINUTES: Final = "stale_minutes"
CONF_CLOUD_THRESHOLD: Final = "cloud_threshold"  # %
CONF_SNOW_MODE: Final = "snow_mode"
CONF_RAIN_MODE: Final = "rain_mode"
CONF_FROST_MODE: Final = "frost_mode"
CONF_FROST_TEMP: Final = "frost_temperature"  # degC
CONF_MIN_INTERVAL: Final = "min_move_interval"  # minutes
CONF_MANUAL_PAUSE: Final = "manual_pause"  # minutes
CONF_DEADBAND: Final = "deadband"  # degrees
CONF_HYSTERESIS: Final = "hysteresis"  # degrees

# Optional dedicated sources (options).
CONF_RAIN_SENSOR: Final = "rain_sensor"  # binary_sensor, or a rate in mm/h
CONF_RAIN_THRESHOLD: Final = "rain_threshold"  # mm/h
CONF_SNOW_SENSOR: Final = "snow_sensor"  # binary_sensor, or a snow depth
CONF_SNOW_THRESHOLD: Final = "snow_threshold"  # cm
CONF_TEMP_SENSOR: Final = "temperature_sensor"
# Custom stow triggers (options).
CONF_TRIGGERS: Final = "stow_triggers"
CONF_TRIGGER_ANGLE: Final = "trigger_angle"  # unset = each panel's stow angle
# Quiet hours (options).
CONF_QUIET_START: Final = "quiet_start"
CONF_QUIET_END: Final = "quiet_end"
CONF_QUIET_SAFETY: Final = "quiet_allow_safety"
# Wind direction rule (options).
CONF_DIRECTION_RULE: Final = "direction_rule"
CONF_DIRECTION_SENSOR: Final = "direction_sensor"
CONF_DIRECTION_SIDES: Final = "direction_sides"
CONF_DIRECTION_SECTOR: Final = "direction_sector"  # +- degrees
SIDES_FRONT: Final = "front"
SIDES_REAR: Final = "rear"
SIDES_BOTH: Final = "both"
SIDES: Final = [SIDES_BOTH, SIDES_FRONT, SIDES_REAR]

SITE_DEFAULTS: Final = {
    CONF_RAIN_THRESHOLD: 5.0,
    CONF_SNOW_THRESHOLD: 1.0,
    CONF_QUIET_SAFETY: True,
    CONF_DIRECTION_RULE: False,
    CONF_DIRECTION_SIDES: SIDES_BOTH,
    CONF_DIRECTION_SECTOR: 60.0,
    CONF_WIND_STOW: 50.0,
    CONF_WIND_RESUME: 35.0,
    CONF_CALM_MINUTES: 10,
    CONF_STORM_SPEED: 75.0,
    CONF_STORM_HOLD: 6,
    CONF_STALE_MINUTES: 120,
    CONF_CLOUD_THRESHOLD: 80,
    CONF_SNOW_MODE: True,
    CONF_RAIN_MODE: False,
    CONF_FROST_MODE: False,
    CONF_FROST_TEMP: -2.0,
    CONF_MIN_INTERVAL: 5,
    CONF_MANUAL_PAUSE: 60,
    CONF_DEADBAND: 2.0,
    CONF_HYSTERESIS: 1.0,
}

# ---- panel (config subentry data) -------------------------------------------
CONF_ACTUATOR: Final = "actuator_entity"
CONF_AXIS: Final = "axis"
CONF_AZIMUTH: Final = "azimuth"
CONF_MIN_ANGLE: Final = "min_angle"
CONF_MAX_ANGLE: Final = "max_angle"
CONF_STEP: Final = "step"
CONF_STRATEGY: Final = "strategy"
CONF_MAPPING: Final = "mapping"
CONF_POS_AT_MIN: Final = "position_at_min"
CONF_POS_AT_MAX: Final = "position_at_max"
CONF_CALIBRATION: Final = "calibration"
CONF_FEEDBACK: Final = "feedback_entity"
CONF_FEEDBACK_KIND: Final = "feedback_kind"
CONF_TRAVEL_TIME: Final = "travel_time"  # seconds, full stroke
CONF_STOW_ANGLE: Final = "stow_angle"
CONF_NIGHT_ANGLE: Final = "night_angle"
CONF_DIFFUSE_ANGLE: Final = "diffuse_angle"
CONF_SNOW_ANGLE: Final = "snow_angle"
CONF_RAIN_ANGLE: Final = "rain_angle"
CONF_FROST_ANGLE: Final = "frost_angle"
CONF_WINTER_ANGLE: Final = "winter_angle"
CONF_SUMMER_ANGLE: Final = "summer_angle"
CONF_SEASON_WEIGHT: Final = "season_weight"
CONF_PV_POWER: Final = "pv_power_entity"
CONF_PV_PEAK: Final = "pv_peak_power"  # W

# Two relays (timed): a dumb actuator on an open and a close relay.
CONF_ACTUATOR_TYPE: Final = "actuator_type"
ACTUATOR_ENTITY: Final = "entity"  # cover, number, input_number or script
ACTUATOR_RELAYS: Final = "relays"
ACTUATOR_TYPES: Final = [ACTUATOR_ENTITY, ACTUATOR_RELAYS]
CONF_OPEN_SWITCH: Final = "open_switch"
CONF_CLOSE_SWITCH: Final = "close_switch"
CONF_OPEN_COUNTDOWN: Final = "open_countdown"
CONF_CLOSE_COUNTDOWN: Final = "close_countdown"
CONF_OPEN_TIME: Final = "open_time"  # s, fully closed -> fully open
CONF_CLOSE_TIME: Final = "close_time"  # s, fully open -> fully closed
CONF_ANGLE_CLOSED: Final = "angle_closed"  # panel angle with the actuator fully closed
CONF_ANGLE_OPEN: Final = "angle_open"  # panel angle with the actuator fully open
CONF_START_DELAY: Final = "start_delay"  # s before the motor really moves
CONF_HOME_OVERRUN: Final = "home_overrun"  # % of the travel time past an end
CONF_REVERSE_DELAY: Final = "reverse_delay"  # s pause before changing direction
CONF_HOME_AFTER_MOVES: Final = "home_after_moves"
CONF_HOME_AT_NIGHT: Final = "home_at_night"
CONF_HOME_END: Final = "home_end"
HOME_CLOSED: Final = "closed"
HOME_OPEN: Final = "open"
HOME_NEAREST: Final = "nearest"
HOME_ENDS: Final = [HOME_CLOSED, HOME_OPEN, HOME_NEAREST]

AXIS_TILT: Final = "tilt"  # tilts toward the azimuth, angle 0..90
AXIS_ROLL: Final = "roll"  # single-axis tracker, angle -90..90
AXES: Final = [AXIS_TILT, AXIS_ROLL]

STRATEGY_FIXED: Final = "fixed"
STRATEGY_SEASONAL: Final = "seasonal"
STRATEGY_DAILY: Final = "daily"
STRATEGY_TRACKING: Final = "tracking"
STRATEGIES: Final = [
    STRATEGY_FIXED,
    STRATEGY_SEASONAL,
    STRATEGY_DAILY,
    STRATEGY_TRACKING,
]

MODE_AUTO: Final = "auto"
MODE_MANUAL: Final = "manual"
MODES: Final = [MODE_AUTO, MODE_MANUAL, *STRATEGIES]

MAPPING_LINEAR: Final = "linear"
MAPPING_TABLE: Final = "table"
FEEDBACK_POSITION: Final = "position"
FEEDBACK_ANGLE: Final = "angle"

PANEL_DEFAULTS: Final = {
    CONF_AXIS: AXIS_TILT,
    CONF_AZIMUTH: 180.0,
    CONF_MIN_ANGLE: 0.0,
    CONF_MAX_ANGLE: 60.0,
    CONF_STEP: 5.0,
    CONF_STRATEGY: STRATEGY_DAILY,
    CONF_MAPPING: MAPPING_LINEAR,
    CONF_POS_AT_MIN: 0.0,
    CONF_POS_AT_MAX: 100.0,
    CONF_CALIBRATION: "",
    CONF_FEEDBACK_KIND: FEEDBACK_POSITION,
    CONF_TRAVEL_TIME: 60.0,
    CONF_STOW_ANGLE: 0.0,
    CONF_NIGHT_ANGLE: 15.0,
    CONF_DIFFUSE_ANGLE: 10.0,
    CONF_SNOW_ANGLE: 60.0,
    CONF_RAIN_ANGLE: 30.0,
    CONF_FROST_ANGLE: 30.0,
    CONF_WINTER_ANGLE: 60.0,
    CONF_SUMMER_ANGLE: 20.0,
    CONF_SEASON_WEIGHT: 50.0,
    CONF_PV_PEAK: 0.0,
    CONF_ACTUATOR_TYPE: ACTUATOR_ENTITY,
    CONF_OPEN_TIME: 30.0,
    CONF_CLOSE_TIME: 30.0,
    CONF_ANGLE_CLOSED: 0.0,
    CONF_ANGLE_OPEN: 60.0,
    CONF_START_DELAY: 0.0,
    CONF_HOME_OVERRUN: 15.0,
    CONF_REVERSE_DELAY: 1.0,
    CONF_HOME_AFTER_MOVES: 20,
    CONF_HOME_AT_NIGHT: True,
    CONF_HOME_END: HOME_CLOSED,
}

# Move reasons (also translation keys for the last-move sensor).
REASON_STRATEGY: Final = "strategy"
REASON_NIGHT: Final = "night"
REASON_DIFFUSE: Final = "diffuse"
REASON_MANUAL: Final = "manual"
REASON_WIND: Final = "wind"
REASON_STORM: Final = "storm"
REASON_STOW: Final = "stow"
REASON_SNOW: Final = "snow"
REASON_RAIN: Final = "rain"
REASON_FROST: Final = "frost"
REASON_CALIBRATE: Final = "calibrate"
REASON_TRIGGER: Final = "trigger"
REASON_QUIET: Final = "quiet"
