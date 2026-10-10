"""Shared fixtures: a site in Amsterdam with a cover-driven panel."""

from __future__ import annotations

import asyncio
import builtins
import glob
import os
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.helios_tilt.const import DOMAIN, SUBENTRY_PANEL

LAT, LON = 52.3676, 4.9041
# 21 June 2026, 12:00 Amsterdam (CEST): the sun is high in the south.
NOON = "2026-06-21 10:00:00+00:00"

SITE_DATA = {
    "latitude": LAT,
    "longitude": LON,
    "weather_entity": "weather.home",
}
PANEL_DATA = {
    "actuator_entity": "cover.panel",
    "axis": "tilt",
    "azimuth": 180.0,
    "min_angle": 0.0,
    "max_angle": 60.0,
    "step": 5.0,
    "strategy": "daily",
    "mapping": "linear",
    "position_at_min": 0.0,
    "position_at_max": 100.0,
    "travel_time": 60.0,
}
WEATHER_ATTRS = {
    "temperature": 18.0,
    "temperature_unit": "°C",
    "wind_speed": 10.0,
    "wind_gust_speed": 15.0,
    "wind_speed_unit": "km/h",
    "cloud_coverage": 20,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations automatically for all tests."""
    return


@pytest.fixture
async def amsterdam(hass: HomeAssistant) -> HomeAssistant:
    """Home Assistant located in Amsterdam."""
    await hass.config.async_update(
        latitude=LAT, longitude=LON, time_zone="Europe/Amsterdam"
    )
    return hass


class FakeCover:
    """A cover that reports the position it was told (optionally after a delay).

    All fake covers share one set_cover_position handler that routes each call
    to the cover it names.
    """

    def __init__(self, hass: HomeAssistant, entity_id: str = "cover.panel") -> None:
        self.hass = hass
        self.entity_id = entity_id
        self.calls: list[ServiceCall] = []
        self.follow = True
        self.set(0)
        covers: dict[str, FakeCover] = hass.data.setdefault("fake_covers", {})
        if not covers:
            async_mock_service(hass, "cover", "set_cover_position")
            hass.services.async_remove("cover", "set_cover_position")

            async def _handle(call: ServiceCall) -> None:
                ids = call.data["entity_id"]
                for entity_id in [ids] if isinstance(ids, str) else ids:
                    if cover := covers.get(entity_id):
                        cover.calls.append(call)
                        if cover.follow:
                            cover.set(call.data["position"])

            hass.services.async_register("cover", "set_cover_position", _handle)
        covers[entity_id] = self

    def set(self, position: float, state: str | None = None) -> None:
        self.hass.states.async_set(
            self.entity_id,
            state or ("closed" if position == 0 else "open"),
            {"current_position": position, "supported_features": 15},
        )

    @property
    def positions(self) -> list[float]:
        return [c.data["position"] for c in self.calls]


@pytest.fixture
def weather(hass: HomeAssistant, frozen) -> Callable[..., None]:
    """Set the weather entity."""

    def _set(state: str = "sunny", **attrs: Any) -> None:
        hass.states.async_set("weather.home", state, {**WEATHER_ATTRS, **attrs})

    _set()
    return _set


@pytest.fixture
def cover(hass: HomeAssistant, frozen) -> FakeCover:
    """The panel's cover."""
    return FakeCover(hass)


def make_entry(
    site: dict[str, Any] | None = None,
    panels: list[dict[str, Any]] | None = None,
    options: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """A site entry with panel subentries."""
    panels = panels if panels is not None else [{**PANEL_DATA}]
    return MockConfigEntry(
        domain=DOMAIN,
        title="Roof",
        data={**SITE_DATA, **(site or {})},
        options=options or {},
        entry_id="site1",
        subentries_data=[
            ConfigSubentryData(
                data=p,
                subentry_type=SUBENTRY_PANEL,
                title=p.get("title", f"Panel {i + 1}"),
                unique_id=p["actuator_entity"],
            )
            for i, p in enumerate(panels)
        ],
    )


@pytest.fixture
def frozen(freezer):
    """Midsummer noon in Amsterdam."""
    freezer.move_to(NOON)
    return freezer


@pytest.fixture
def setup_site(hass, amsterdam, weather, cover, frozen) -> Callable[..., Any]:
    """Coroutine function: set up a site and return the entry."""

    async def _setup(**kwargs: Any) -> MockConfigEntry:
        entry = make_entry(**kwargs)
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return _setup


def panel_of(entry: MockConfigEntry, index: int = 0):
    """The runtime Panel object."""
    return list(entry.runtime_data.panels.values())[index]


_INTEGRATION_DIR = str(Path(__file__).parent.parent / "custom_components" / DOMAIN)
_BLOCKING = [
    (builtins, "open"),
    (os, "listdir"),
    (os, "scandir"),
    (os, "walk"),
    (os.path, "exists"),
    (os.path, "isfile"),
    (glob, "glob"),
    (time, "sleep"),
    (Path, "open"),
    (Path, "read_text"),
    (Path, "read_bytes"),
    (Path, "write_text"),
    (Path, "write_bytes"),
    (Path, "exists"),
    (Path, "is_file"),
    (Path, "is_dir"),
]


@pytest.fixture(autouse=True)
def no_blocking_io_in_loop(monkeypatch: pytest.MonkeyPatch):
    """Fail when Helios Tilt does file or sleep I/O inside the event loop.

    Home Assistant only logs these in tests, so check it ourselves: any of
    these calls, made while an event loop runs in this thread with Helios
    Tilt code on the stack, is a "Detected blocking call" in a real install.
    """
    found: list[str] = []
    loop_thread = threading.get_ident()

    def guard(func, name):
        def guarded(*args, **kwargs):
            if threading.get_ident() == loop_thread:
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    return func(*args, **kwargs)
                frame = sys._getframe(1)
                while frame is not None:
                    filename = frame.f_code.co_filename
                    if filename.startswith(_INTEGRATION_DIR):
                        found.append(
                            f"{name}{args[:1]!r} from "
                            f"{filename[len(_INTEGRATION_DIR) + 1 :]}:{frame.f_lineno}"
                        )
                        break
                    frame = frame.f_back
            return func(*args, **kwargs)

        return guarded

    for obj, attr in _BLOCKING:
        monkeypatch.setattr(obj, attr, guard(getattr(obj, attr), attr))
    yield found
    assert not found, f"blocking calls in the event loop: {found}"
