"""Diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import HeliosConfigEntry
from .const import CONF_LATITUDE, CONF_LONGITUDE, VERSION

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE, "latitude", "longitude"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HeliosConfigEntry
) -> dict[str, Any]:
    """Config, panels and live state (location redacted)."""
    site = entry.runtime_data
    return {
        "version": VERSION,
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
            "subentries": [
                {"type": s.subentry_type, "title": s.title, "data": dict(s.data)}
                for s in entry.subentries.values()
            ],
        },
        "state": site.diagnostics(),
    }
