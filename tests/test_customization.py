"""Beta.6 customization: sources, dedicated sensors, triggers, quiet hours, direction."""

from __future__ import annotations

from datetime import time

import pytest
from homeassistant.core import HomeAssistant

from custom_components.helios_tilt.const import DOMAIN
from custom_components.helios_tilt.controller import _bearing, in_window

from .conftest import panel_of
from .test_controller import TARGET, advance, attr

WIND = "binary_sensor.panel_1_wind_stow"
LAST = "sensor.panel_1_last_move"


# ---- source transparency -------------------------------------------------------


async def test_wind_source_attributes(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    """The wind sensors say where the numbers come from and which one drives."""
    hass.states.async_set("sensor.wind", "20", {"unit_of_measurement": "km/h"})
    entry = await setup_site(site={"wind_sensor": "sensor.wind"})
    assert attr(hass, WIND, "weather_entity") == "weather.home"
    assert attr(hass, WIND, "wind_sensor") == "sensor.wind"
    assert attr(hass, WIND, "weather_wind") == 10
    assert attr(hass, WIND, "weather_gust") == 15
    assert attr(hass, WIND, "sensor_wind") == 20
    assert attr(hass, WIND, "wind_source") == "wind_sensor"
    # a weather entity without gusts (like a security system's weather)
    weather(wind_gust_speed=None, wind_speed=30)
    await hass.async_block_till_done()
    assert attr(hass, WIND, "weather_gust") is None
    assert attr(hass, WIND, "wind_source") == "weather_wind"
    assert attr(hass, "binary_sensor.panel_1_storm_mode", "wind_source") == (
        "weather_wind"
    )
    weather(wind_gust_speed=40, wind_speed=30)
    await hass.async_block_till_done()
    assert attr(hass, WIND, "wind_source") == "weather_gust"
    diag = entry.runtime_data.diagnostics()
    assert diag["sources"]["weather_gust"] == 40
    assert diag["sources"]["wind_source"] == "weather_gust"


# ---- dedicated sensors -----------------------------------------------------------


async def test_rain_binary_sensor_overrides_condition(
    hass: HomeAssistant, setup_site, weather, cover, freezer
) -> None:
    """A rain binary sensor wins over the weather condition, both ways."""
    hass.states.async_set("binary_sensor.rain", "on")
    await setup_site(options={"rain_mode": True, "rain_sensor": "binary_sensor.rain"})
    assert attr(hass, TARGET, "reason") == "rain"
    assert attr(hass, TARGET, "safety_detail") == "rain sensor"
    hass.states.async_set("binary_sensor.rain", "off")
    weather("pouring")
    await hass.async_block_till_done()
    assert attr(hass, TARGET, "reason") == "strategy"  # sensor says dry
    hass.states.async_set("binary_sensor.rain", "unavailable")
    await hass.async_block_till_done()
    assert attr(hass, TARGET, "reason") == "rain"  # falls back to the condition
    assert attr(hass, TARGET, "safety_detail") == "pouring"


@pytest.mark.parametrize(
    ("value", "unit", "rain"),
    [
        ("6", "mm/h", True),
        ("4", "mm/h", False),
        ("0.25", "in/h", True),  # 6.35 mm/h
        ("0.1", "in/h", False),  # 2.54 mm/h
        ("130", "mm/d", True),  # 5.4 mm/h
        ("6", None, True),  # no unit: mm/h
    ],
)
async def test_rain_rate_units(
    hass: HomeAssistant, setup_site, cover, value, unit, rain
) -> None:
    """Rate sensors are converted to mm/h before the threshold."""
    attrs = {"unit_of_measurement": unit} if unit else {}
    hass.states.async_set("sensor.rain_rate", value, attrs)
    await setup_site(options={"rain_mode": True, "rain_sensor": "sensor.rain_rate"})
    assert (attr(hass, TARGET, "reason") == "rain") is rain
    assert attr(hass, WIND, "rain_sensor_value").endswith("mm/h")


async def test_unknown_unit_is_ignored(
    hass: HomeAssistant, setup_site, cover, caplog
) -> None:
    """An unknown unit: warn and fall back to the weather condition."""
    hass.states.async_set("sensor.rain_rate", "99", {"unit_of_measurement": "L/s"})
    await setup_site(options={"rain_mode": True, "rain_sensor": "sensor.rain_rate"})
    assert attr(hass, TARGET, "reason") == "strategy"
    assert "Unknown unit L/s" in caplog.text


@pytest.mark.parametrize(
    ("value", "unit", "snow"),
    [("15", "mm", True), ("5", "mm", False), ("0.5", "in", True), ("2", "cm", True)],
)
async def test_snow_depth_units(
    hass: HomeAssistant, setup_site, cover, value, unit, snow
) -> None:
    """Snow depth in mm/in/cm against the threshold in cm."""
    hass.states.async_set("sensor.snow", value, {"unit_of_measurement": unit})
    await setup_site(options={"snow_sensor": "sensor.snow"})
    assert (attr(hass, TARGET, "reason") == "snow") is snow


async def test_snow_binary_sensor(hass: HomeAssistant, setup_site, cover) -> None:
    hass.states.async_set("binary_sensor.snow", "on")
    await setup_site(options={"snow_sensor": "binary_sensor.snow"})
    assert attr(hass, TARGET, "reason") == "snow"


async def test_temperature_sensor_fahrenheit(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    """The outdoor sensor (in F) overrides the weather temperature for frost."""
    hass.states.async_set("sensor.outside", "26", {"unit_of_measurement": "°F"})
    entry = await setup_site(
        options={"frost_mode": True, "temperature_sensor": "sensor.outside"}
    )
    assert attr(hass, TARGET, "reason") == "frost"  # -3.3 C, weather says 18 C
    assert entry.runtime_data.sources["temperature_source"] == "sensor.outside"
    assert entry.runtime_data.sources["temperature"] == pytest.approx(-3.3)
    hass.states.async_set("sensor.outside", "unavailable")
    await hass.async_block_till_done()
    assert attr(hass, TARGET, "reason") == "strategy"  # weather: 18 C
    assert entry.runtime_data.sources["temperature_source"] == "weather.home"


# ---- custom stow triggers ------------------------------------------------------


async def test_stow_trigger(hass: HomeAssistant, setup_site, cover, freezer) -> None:
    """A trigger stows at its own angle, beats manual mode and clears at once."""
    hass.states.async_set("input_boolean.party", "off", {"friendly_name": "Party"})
    await setup_site(
        options={"stow_triggers": ["input_boolean.party"], "trigger_angle": 6}
    )
    assert cover.positions == [25]
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 30}, blocking=True)
    assert cover.positions == [25, 50]
    hass.states.async_set("input_boolean.party", "on", {"friendly_name": "Party"})
    await hass.async_block_till_done()
    assert cover.positions == [25, 50, 10]
    assert hass.states.get(LAST).state == "trigger"
    assert attr(hass, TARGET, "detail") == "Party"
    assert attr(hass, TARGET, "triggers") == ["Party"]
    assert hass.states.get(WIND).state == "on"
    hass.states.async_set("input_boolean.party", "off", {"friendly_name": "Party"})
    await hass.async_block_till_done()
    assert attr(hass, TARGET, "reason") == "manual"  # no calm period
    await advance(hass, freezer, 6)  # the normal minimum move interval
    assert cover.positions == [25, 50, 10, 50]  # back to manual 30 deg


async def test_trigger_default_angle(hass: HomeAssistant, setup_site, cover) -> None:
    """Without a trigger angle each panel uses its stow angle."""
    hass.states.async_set("switch.hail", "on")
    await setup_site(options={"stow_triggers": ["switch.hail"]})
    assert cover.positions == [0]
    assert attr(hass, TARGET, "reason") == "trigger"


async def test_stow_duration(hass: HomeAssistant, setup_site, cover, freezer) -> None:
    """helios_tilt.stow with a duration resumes by itself."""
    entry = await setup_site()
    await hass.services.async_call(
        DOMAIN, "stow", {"duration": {"minutes": 30}}, blocking=True
    )
    assert cover.positions == [25, 0]
    assert attr(hass, TARGET, "stowed_until") is not None
    assert panel_of(entry).store_data()["stowed_until"] is not None
    await advance(hass, freezer, 29)
    assert cover.positions == [25, 0]
    await advance(hass, freezer, 2)
    assert cover.positions == [25, 0, 25]
    assert panel_of(entry).stowed is False
    assert attr(hass, TARGET, "stowed_until") is None


async def test_stow_without_duration_stays(
    hass: HomeAssistant, setup_site, cover, freezer
) -> None:
    await setup_site()
    await hass.services.async_call(DOMAIN, "stow", {}, blocking=True)
    await advance(hass, freezer, 600)
    assert cover.positions == [25, 0]


# ---- quiet hours -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "start", "end", "inside"),
    [
        ("12:00", "11:00", "13:00", True),
        ("13:00", "11:00", "13:00", False),
        ("23:30", "22:00", "07:00", True),  # crosses midnight
        ("03:00", "22:00", "07:00", True),
        ("07:00", "22:00", "07:00", False),
        ("12:00", "22:00", "07:00", False),
        ("12:00", "12:00", "12:00", False),  # empty window
    ],
)
def test_in_window(now: str, start: str, end: str, inside: bool) -> None:
    t = time.fromisoformat
    assert in_window(t(now), t(start), t(end)) is inside


QUIET = {"quiet_start": "23:00:00", "quiet_end": "12:30:00"}  # noon is inside


async def test_quiet_hours_hold_strategy(
    hass: HomeAssistant, setup_site, cover, freezer
) -> None:
    """No strategy moves in quiet hours (window across midnight); after: move."""
    await setup_site(options=QUIET)
    assert cover.positions == []
    assert attr(hass, TARGET, "reason") == "quiet"
    assert attr(hass, TARGET, "quiet") is True
    assert attr(hass, TARGET, "detail") == "until 12:30"
    assert attr(hass, TARGET, "quiet_until").startswith("2026-06-21T12:30:00")
    await advance(hass, freezer, 31)
    assert cover.positions == [25]
    assert attr(hass, TARGET, "quiet") is False


async def test_quiet_until_next_day(
    hass: HomeAssistant, setup_site, cover, freezer
) -> None:
    """At 23:30 a 22:00-07:00 window ends tomorrow."""
    freezer.move_to("2026-06-21 21:30:00+00:00")  # 23:30 CEST
    await setup_site(options={"quiet_start": "22:00:00", "quiet_end": "07:00:00"})
    assert attr(hass, TARGET, "quiet_until").startswith("2026-06-22T07:00:00")


async def test_quiet_window_outside(hass: HomeAssistant, setup_site, cover) -> None:
    await setup_site(options={"quiet_start": "12:30:00", "quiet_end": "11:00:00"})
    assert cover.positions == [25]
    assert attr(hass, TARGET, "quiet") is False


async def test_quiet_hours_allow_safety_and_user(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    """Safety (default) and user commands still move in quiet hours."""
    await setup_site(options=QUIET)
    await hass.services.async_call(DOMAIN, "set_tilt", {"angle": 30}, blocking=True)
    assert cover.positions == [50]
    weather(wind_speed=40, wind_gust_speed=60)
    await hass.async_block_till_done()
    assert cover.positions == [50, 0]
    assert hass.states.get(LAST).state == "wind"


async def test_quiet_hours_hold_safety_but_not_storm(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    """With safety moves off, wind waits; storm mode still stows."""
    await setup_site(options={**QUIET, "quiet_allow_safety": False})
    weather(wind_speed=40, wind_gust_speed=60)
    await hass.async_block_till_done()
    assert cover.positions == []
    assert attr(hass, TARGET, "reason") == "quiet"
    weather(wind_speed=60, wind_gust_speed=90)
    await hass.async_block_till_done()
    assert cover.positions == [0]
    assert hass.states.get(LAST).state == "storm"


# ---- wind direction rule ---------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "degrees"),
    [
        (270, 270.0),
        ("90", 90.0),
        (-90, 270.0),
        ("SW", 225.0),
        ("nne", 22.5),
        ("x", None),
    ],
)
def test_bearing_parse(value, degrees) -> None:
    assert _bearing(value) == degrees


DIRECTION = {"direction_rule": True}  # both sides, +-60 deg; panel faces south


@pytest.mark.parametrize(
    ("options", "bearing", "stows"),
    [
        ({}, 90, True),  # rule off: any direction stows
        (DIRECTION, 90, False),  # east wind passes a south-facing panel
        (DIRECTION, 200, True),  # front
        (DIRECTION, 10, True),  # rear
        (DIRECTION, None, True),  # no bearing: omnidirectional
        ({**DIRECTION, "direction_sides": "front"}, 10, False),
        ({**DIRECTION, "direction_sides": "rear"}, 10, True),
        ({**DIRECTION, "direction_sides": "rear"}, 180, False),
        ({**DIRECTION, "direction_sector": 20}, 215, False),
    ],
)
async def test_direction_rule(
    hass: HomeAssistant, setup_site, weather, cover, options, bearing, stows
) -> None:
    await setup_site(options=options)
    weather(wind_speed=40, wind_gust_speed=60, wind_bearing=bearing)
    await hass.async_block_till_done()
    assert (cover.positions[-1] == 0) is stows
    assert (hass.states.get(WIND).state == "on") is stows
    assert attr(hass, TARGET, "wind_exempt") is not stows


async def test_direction_storm_always_stows(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    await setup_site(options=DIRECTION)
    weather(wind_speed=60, wind_gust_speed=90, wind_bearing=90)
    await hass.async_block_till_done()
    assert cover.positions == [25, 0]
    assert hass.states.get(LAST).state == "storm"


async def test_direction_sensor_overrides_weather(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    """A direction sensor (cardinal text) wins over the weather bearing."""
    hass.states.async_set("sensor.wind_dir", "E")
    await setup_site(options={**DIRECTION, "direction_sensor": "sensor.wind_dir"})
    weather(wind_speed=40, wind_gust_speed=60, wind_bearing=180)
    await hass.async_block_till_done()
    assert cover.positions == [25]
    assert attr(hass, WIND, "wind_bearing") == 90
    assert attr(hass, WIND, "wind_bearing_source") == "sensor.wind_dir"
    hass.states.async_set("sensor.wind_dir", "unavailable")
    await hass.async_block_till_done()
    assert cover.positions == [25, 0]  # weather bearing 180: front


async def test_direction_change_stows_later(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    """Exempt now, but the wind turns towards the panel: stow at once."""
    await setup_site(options=DIRECTION)
    weather(wind_speed=40, wind_gust_speed=60, wind_bearing=90)
    await hass.async_block_till_done()
    assert cover.positions == [25]
    weather(wind_speed=40, wind_gust_speed=60, wind_bearing=170)
    await hass.async_block_till_done()
    assert cover.positions == [25, 0]


async def test_snow_still_applies_when_wind_exempt(
    hass: HomeAssistant, setup_site, weather, cover, freezer
) -> None:
    """The exempt panel falls through to the next safety rule."""
    await setup_site(options=DIRECTION)
    weather("snowy", wind_speed=40, wind_gust_speed=60, wind_bearing=90)
    await hass.async_block_till_done()
    await advance(hass, freezer, 6)
    assert cover.positions[-1] == 100
    assert attr(hass, TARGET, "reason") == "snow"
