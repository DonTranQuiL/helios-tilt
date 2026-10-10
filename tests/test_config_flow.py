"""Config flow, panel subentries, options and reconfigure."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from custom_components.helios_tilt.const import DOMAIN, SUBENTRY_PANEL

from .conftest import LAT, LON

MAPPING = {
    "mapping": "linear",
    "position_at_min": 0,
    "position_at_max": 100,
    "feedback_kind": "position",
    "travel_time": 60,
}
POSITIONS = {
    "stow_angle": 0,
    "night_angle": 15,
    "diffuse_angle": 10,
    "snow_angle": 60,
    "rain_angle": 30,
    "frost_angle": 30,
    "winter_angle": 60,
    "summer_angle": 20,
    "season_weight": 50,
}


RELAYS = {
    "open_time": 30,
    "close_time": 30,
    "angle_closed": 0,
    "angle_open": 60,
}
RELAY_ADVANCED = {
    "start_delay": 0,
    "home_overrun": 15,
    "reverse_delay": 1,
    "home_after_moves": 20,
    "home_at_night": True,
    "home_end": "closed",
    "mapping": "linear",
}
GEOMETRY = {
    "axis": "tilt",
    "azimuth": 180,
    "min_angle": 0,
    "max_angle": 60,
    "step": 5,
    "strategy": "daily",
}


def type_input(name: str = "Garden", actuator_type: str = "entity") -> dict:
    return {CONF_NAME: name, "actuator_type": actuator_type}


def entity_input(**overrides) -> dict:
    data = {
        "actuator_entity": "cover.panel",
        **GEOMETRY,
        "mapping_feedback": {**MAPPING},
    }
    for key, value in overrides.items():
        if key in MAPPING or key in ("calibration", "feedback_entity"):
            data["mapping_feedback"][key] = value
        else:
            data[key] = value
    return data


def relays_input(**overrides) -> dict:
    data = {
        "open_switch": "switch.attic_l1",
        "close_switch": "switch.attic_l2",
        **RELAYS,
        **GEOMETRY,
        "relay_advanced": {**RELAY_ADVANCED},
    }
    for key, value in overrides.items():
        if key in RELAY_ADVANCED or key == "calibration":
            data["relay_advanced"][key] = value
        elif value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return data


def positions_input(**overrides) -> dict:
    return {**POSITIONS, "pv": {"pv_peak_power": 0}, **overrides}


async def add_panel(configure, flow_id, *, name="Garden", positions=None, **overrides):
    """Steps 1-3 for an entity panel; returns the final result."""
    result = await configure(flow_id, type_input(name))
    assert result["step_id"] == "entity"
    result = await configure(flow_id, entity_input(**overrides))
    assert result["step_id"] == "positions", result.get("errors")
    return await configure(flow_id, positions_input(**(positions or {})))


async def test_full_flow(hass: HomeAssistant, amsterdam, weather, cover) -> None:
    """Site with HA location defaults, then the first panel as a subentry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    schema = {str(k): k for k in result["data_schema"].schema}
    assert schema["latitude"].default() == LAT
    assert schema["longitude"].default() == LON

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Roof", "latitude": LAT, "longitude": LON}
    )
    assert result["errors"] == {"base": "wind_source_required"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Roof",
            "latitude": LAT,
            "longitude": LON,
            "weather_entity": "weather.home",
        },
    )
    assert result["step_id"] == "panel"
    flow = result["flow_id"]
    configure = hass.config_entries.flow.async_configure

    # Step 1: name and type only; no actuator field.
    schema = {str(k) for k in result["data_schema"].schema}
    assert schema == {CONF_NAME, "actuator_type"}
    result = await configure(flow, type_input())
    assert result["step_id"] == "entity"
    schema = {str(k) for k in result["data_schema"].schema}
    assert "actuator_entity" in schema and "open_switch" not in schema
    assert "relay_advanced" not in schema

    data = entity_input()
    data.pop("actuator_entity")
    with pytest.raises(InvalidData):  # required on the entity step
        await configure(flow, data)
    result = await configure(flow, entity_input(min_angle=50, max_angle=40))
    assert result["errors"] == {"max_angle": "max_below_min"}
    result = await configure(flow, entity_input(min_angle=-10))
    assert result["errors"] == {"min_angle": "tilt_range"}
    result = await configure(flow, entity_input(mapping="table"))
    assert result["errors"] == {"base": "calibration_required"}
    result = await configure(
        flow, entity_input(mapping="table", calibration="0:0, 30:80, 60:50")
    )
    assert result["errors"] == {"base": "invalid_mapping"}

    result = await configure(flow, entity_input(max_angle=50))
    assert result["step_id"] == "positions"
    # Defaults are clamped to the limits; seasonal angles follow the latitude.
    schema = {str(k): k for k in result["data_schema"].schema}
    assert schema["snow_angle"].default() == 50
    assert schema["winter_angle"].default() == 50  # 52.4 + 15, clamped to 50
    assert schema["summer_angle"].default() == 17  # 52.4 - 35
    placeholders = result["description_placeholders"]
    assert (placeholders["min"], placeholders["max"]) == ("0", "50")
    assert (placeholders["winter"], placeholders["summer"]) == ("50", "17")

    with pytest.raises(InvalidData):  # the selectors stop at the limits
        await configure(flow, positions_input(snow_angle=60))
    # Equal seasonal angles: a hint once, accepted on the second submit.
    flat = positions_input(snow_angle=50, winter_angle=30, summer_angle=30)
    result = await configure(flow, flat)
    assert result["errors"] == {"base": "season_flat"}
    result = await configure(flow, flat)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Roof"
    entry = result["result"]
    assert entry.data == {
        "latitude": LAT,
        "longitude": LON,
        "weather_entity": "weather.home",
    }
    (sub,) = entry.subentries.values()
    assert sub.title == "Garden"
    assert sub.subentry_type == SUBENTRY_PANEL
    assert sub.data["actuator_entity"] == "cover.panel"
    assert sub.data["actuator_type"] == "entity"
    assert sub.data["travel_time"] == 60
    assert sub.data["winter_angle"] == sub.data["summer_angle"] == 30
    assert "feedback_entity" not in sub.data
    assert not any(k in sub.data for k in ("open_switch", "open_time", "home_end"))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.garden_target_angle") is not None


async def test_roll_axis_allows_negative(
    hass: HomeAssistant, amsterdam, weather, cover
) -> None:
    """Roll trackers can go below zero."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Field",
            "latitude": LAT,
            "longitude": LON,
            "weather_entity": "weather.home",
        },
    )
    result = await add_panel(
        hass.config_entries.flow.async_configure,
        result["flow_id"],
        axis="roll",
        azimuth=270,
        min_angle=-45,
        max_angle=45,
        strategy="tracking",
        positions={"stow_angle": -10, "snow_angle": 40, "winter_angle": 40},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_add_and_reconfigure_panel(
    hass: HomeAssistant, setup_site, cover
) -> None:
    """Panels are added and changed from the integration page."""
    entry = await setup_site()
    cover2 = "cover.panel_two"
    hass.states.async_set(cover2, "closed", {"current_position": 0})
    configure = hass.config_entries.subentries.async_configure

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_PANEL), context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    flow = result["flow_id"]
    result = await configure(flow, type_input("Shed"))
    result = await configure(flow, entity_input())
    assert result["errors"] == {"base": "actuator_in_use"}
    result = await configure(flow, entity_input(actuator_entity=cover2))
    result = await configure(flow, positions_input())
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert len(entry.subentries) == 2
    assert hass.states.get("sensor.shed_target_angle") is not None

    sub = next(s for s in entry.subentries.values() if s.title == "Shed")
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    assert result["step_id"] == "settings"  # no menu for an entity actuator
    flow = result["flow_id"]
    result = await configure(flow, type_input("Shed roof"))
    assert result["step_id"] == "entity"
    schema = {str(k): k for k in result["data_schema"].schema}
    assert schema["actuator_entity"].default() == cover2
    result = await configure(flow, entity_input(actuator_entity=cover2, max_angle=45))
    # Saved angles above the new limit are shown clamped.
    schema = {str(k): k for k in result["data_schema"].schema}
    assert schema["winter_angle"].default() == 45
    result = await configure(flow, positions_input(winter_angle=45, snow_angle=45))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    sub = entry.subentries[sub.subentry_id]
    assert sub.title == "Shed roof"
    assert sub.data["max_angle"] == 45
    panel = entry.runtime_data.panels[sub.subentry_id]
    assert panel.cfg.max_angle == 45


async def test_switch_entity_panel_to_relays(
    hass: HomeAssistant, setup_site, cover
) -> None:
    """Changing the type drops the other type's settings."""
    entry = await setup_site()
    for entity_id in ("switch.attic_l1", "switch.attic_l2"):
        hass.states.async_set(entity_id, "off")
    sub = next(iter(entry.subentries.values()))
    configure = hass.config_entries.subentries.async_configure
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    flow = result["flow_id"]
    result = await configure(flow, type_input("Attic", "relays"))
    assert result["step_id"] == "relays"
    schema = {str(k) for k in result["data_schema"].schema}
    assert "actuator_entity" not in schema and "mapping_feedback" not in schema
    result = await configure(
        flow,
        relays_input(angle_closed=10, angle_open=40, min_angle=10, max_angle=40),
    )
    assert result["step_id"] == "positions"
    result = await configure(flow, positions_input(**_clamped(10, 40)))
    assert result["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()
    data = entry.subentries[sub.subentry_id].data
    assert data["actuator_type"] == "relays"
    assert "actuator_entity" not in data and "position_at_min" not in data
    assert entry.subentries[sub.subentry_id].unique_id == "switch.attic_l1"
    panel = entry.runtime_data.panels[sub.subentry_id]
    assert panel.cfg.actuator_entity == ""
    assert panel.driver is not None


def _clamped(lo: float, hi: float) -> dict:
    return {
        k: max(lo, min(hi, v)) for k, v in POSITIONS.items() if k != "season_weight"
    }


async def test_options(hass: HomeAssistant, setup_site) -> None:
    """Thresholds are validated and applied with a reload."""
    entry = await setup_site()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    base = {
        "wind_stow_speed": 40,
        "wind_resume_speed": 45,
        "calm_minutes": 5,
        "storm_speed": 70,
        "storm_hold_hours": 2,
        "stale_minutes": 90,
        "snow_mode": False,
        "rain_mode": True,
        "frost_mode": True,
        "frost_temperature": -1,
        "cloud_threshold": 70,
        "min_move_interval": 2,
        "manual_pause": 30,
        "deadband": 1,
        "hysteresis": 0.5,
        "sources": {"rain_threshold": 5, "snow_threshold": 1},
        "triggers": {},
        "quiet": {"quiet_allow_safety": True},
        "direction": {
            "direction_rule": False,
            "direction_sides": "both",
            "direction_sector": 60,
        },
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], base)
    assert result["errors"] == {"wind_resume_speed": "resume_above_stow"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**base, "wind_resume_speed": 30, "storm_speed": 30}
    )
    assert result["errors"] == {"storm_speed": "storm_below_stow"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**base, "wind_resume_speed": 30}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    site = entry.runtime_data
    assert site.safety.settings.wind_stow == 40
    assert site.safety.settings.rain is True


async def test_options_extras(hass: HomeAssistant, setup_site) -> None:
    """The optional sections are flattened, validated and applied."""
    entry = await setup_site()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema_keys = {str(k) for k in result["data_schema"].schema}
    assert {"sources", "triggers", "quiet", "direction"} <= schema_keys
    base = {
        "wind_stow_speed": 40,
        "wind_resume_speed": 30,
        "calm_minutes": 5,
        "storm_speed": 70,
        "storm_hold_hours": 2,
        "stale_minutes": 90,
        "snow_mode": True,
        "rain_mode": True,
        "frost_mode": True,
        "frost_temperature": 0,
        "cloud_threshold": 70,
        "min_move_interval": 2,
        "manual_pause": 30,
        "deadband": 1,
        "hysteresis": 0.5,
        "sources": {
            "rain_sensor": "sensor.rain_rate",
            "rain_threshold": 4,
            "snow_threshold": 1,
            "temperature_sensor": "sensor.outside",
        },
        "triggers": {"stow_triggers": ["input_boolean.party"], "trigger_angle": 20},
        "quiet": {"quiet_start": "22:00:00", "quiet_allow_safety": False},
        "direction": {
            "direction_rule": True,
            "direction_sides": "front",
            "direction_sector": 45,
        },
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], base)
    assert result["errors"] == {"base": "quiet_incomplete"}
    base["quiet"]["quiet_end"] = "07:00:00"
    result = await hass.config_entries.options.async_configure(result["flow_id"], base)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "sources" not in entry.options
    assert entry.options["rain_sensor"] == "sensor.rain_rate"
    assert entry.options["stow_triggers"] == ["input_boolean.party"]
    assert "snow_sensor" not in entry.options
    await hass.async_block_till_done()
    site = entry.runtime_data
    assert site.rain_threshold == 4
    assert site.temp_sensor == "sensor.outside"
    assert site.triggers == ["input_boolean.party"]
    assert site.trigger_angle == 20
    assert str(site.quiet_start) == "22:00:00"
    assert site.quiet_safety is False
    assert site.direction_rule is True
    assert site.direction_sides == "front"
    assert site.direction_sector == 45


async def test_reconfigure_site(hass: HomeAssistant, setup_site) -> None:
    """Location and weather sources can be changed."""
    entry = await setup_site()
    hass.states.async_set("sensor.wind", "5", {"unit_of_measurement": "km/h"})
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"latitude": 50.0, "longitude": 5.0}
    )
    assert result["errors"] == {"base": "wind_source_required"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"latitude": 50.0, "longitude": 5.0, "wind_sensor": "sensor.wind"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.data == {
        "latitude": 50.0,
        "longitude": 5.0,
        "wind_sensor": "sensor.wind",
    }
    assert entry.runtime_data.latitude == 50.0
    assert entry.runtime_data.weather_entity is None
