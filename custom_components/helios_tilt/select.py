"""Mode select."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeliosConfigEntry
from .const import MODES
from .entity import HeliosEntity

MODE = SelectEntityDescription(key="mode", translation_key="mode", options=MODES)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeliosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Per panel."""
    site = entry.runtime_data
    for panel in site.panels.values():
        async_add_entities(
            [HeliosModeSelect(site, panel, MODE)], config_subentry_id=panel.id
        )


class HeliosModeSelect(HeliosEntity, SelectEntity):
    """auto / manual / fixed / seasonal / daily / tracking."""

    @property
    def current_option(self) -> str:
        """Current mode."""
        return self.panel.mode

    async def async_select_option(self, option: str) -> None:
        """Change mode."""
        await self.site.async_set_mode(self.panel, option)
