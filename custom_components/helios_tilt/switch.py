"""Automatic control switch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeliosConfigEntry
from .entity import HeliosEntity

AUTO = SwitchEntityDescription(key="auto", translation_key="auto")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeliosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Per panel."""
    site = entry.runtime_data
    for panel in site.panels.values():
        async_add_entities(
            [HeliosAutoSwitch(site, panel, AUTO)], config_subentry_id=panel.id
        )


class HeliosAutoSwitch(HeliosEntity, SwitchEntity):
    """Off: no automatic moves (safety still stows)."""

    @property
    def is_on(self) -> bool:
        """Automatic control on."""
        return self.panel.auto_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable."""
        await self.site.async_set_auto(self.panel, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable."""
        await self.site.async_set_auto(self.panel, False)
