"""Base entity: one device per panel."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN, NAME, VERSION
from .controller import HeliosSite, Panel


class HeliosEntity(Entity):
    """Entity of one panel; refreshed whenever the site evaluates."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, site: HeliosSite, panel: Panel, description: EntityDescription
    ) -> None:
        """Bind to a panel."""
        self.site = site
        self.panel = panel
        self.entity_description = description
        self._attr_unique_id = f"{panel.id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, panel.id)},
            name=panel.title,
            manufacturer="DonTranQuiL",
            model=f"{NAME} panel",
            sw_version=VERSION,
        )

    async def async_added_to_hass(self) -> None:
        """Follow the site."""
        self.async_on_remove(self.site.async_add_listener(self.async_write_ha_state))
