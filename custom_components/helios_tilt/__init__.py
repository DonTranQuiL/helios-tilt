"""Helios Tilt: automatic solar panel tilt control for Home Assistant."""

from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CARD_FILENAME, CARD_URL, DOMAIN, LOGGER, PLATFORMS, VERSION
from .controller import HeliosSite
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type HeliosConfigEntry = ConfigEntry[HeliosSite]


def _file_digest(path: Path) -> str:
    """Short hash of a file's content (cache busting)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions and the dashboard card once."""
    async_setup_services(hass)
    card = Path(__file__).parent / "frontend" / CARD_FILENAME
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card), True)]
    )
    if "frontend" in hass.config.components:
        digest = await hass.async_add_executor_job(_file_digest, card)
        add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}-{digest}")
    else:  # pragma: no cover - frontend is always loaded in a real install
        LOGGER.debug("Frontend not loaded, the Helios Tilt card is not registered")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HeliosConfigEntry) -> bool:
    """Set up a site and its panels."""
    site = HeliosSite(hass, entry)
    await site.async_start()
    entry.runtime_data = site
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    site.async_activate()
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: HeliosConfigEntry) -> None:
    """Options or panels changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HeliosConfigEntry) -> bool:
    """Unload a site."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded
