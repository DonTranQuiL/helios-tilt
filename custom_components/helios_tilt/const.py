"""Constants for Helios Tilt."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "helios_tilt"
NAME: Final = "Helios Tilt"
VERSION = "0.1.0b1"
LOGGER = logging.getLogger(__package__)

PLATFORMS: Final = ["binary_sensor", "number", "select", "sensor", "switch"]
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

SITE_DEFAULTS: Final = {
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
