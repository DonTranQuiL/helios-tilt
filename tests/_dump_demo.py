"""Not a test: renders demo states for docs/images/card.png (run explicitly)."""

from __future__ import annotations

import json
from datetime import timedelta

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.helios_tilt.const import DOMAIN

from .conftest import PANEL_DATA, FakeCover
from .test_card import card_data


async def test_dump(hass, setup_site, weather, cover, freezer):
    freezer.move_to("2026-09-12 05:30:00+00:00")
    FakeCover(hass, "cover.garden_rack")
    weather(wind_speed=12, wind_gust_speed=18)
    entry = await setup_site(
        panels=[
            {
                **PANEL_DATA,
                "title": "Garage roof",
                "strategy": "tracking",
                "min_angle": 5,
                "max_angle": 65,
            },
            {
                **PANEL_DATA,
                "title": "Garden rack",
                "actuator_entity": "cover.garden_rack",
                "strategy": "daily",
            },
        ]
    )

    async def step(minutes, **w):
        freezer.tick(timedelta(minutes=minutes))
        if w:
            weather(**w)
        else:
            weather(wind_speed=12, wind_gust_speed=18)
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

    for _ in range(14):
        await step(30)
    await step(2, wind_speed=38, wind_gust_speed=58)
    for _ in range(3):
        await step(4, wind_speed=20, wind_gust_speed=26)
    for _ in range(8):
        await step(2, wind_speed=16, wind_gust_speed=24)
    for _ in range(4):
        await step(20, wind_speed=18, wind_gust_speed=27)
    data = await card_data(hass, entry)
    data["now"] = dt_util.utcnow().isoformat()
    with open("/tmp/helios_demo.json", "w", encoding="utf-8") as fh:  # noqa: ASYNC230
        json.dump(data, fh)
    assert DOMAIN
