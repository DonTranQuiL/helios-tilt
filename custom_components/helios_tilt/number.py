"""Manual angle."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import DEGREE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeliosConfigEntry
from .controller import HeliosSite, Panel
from .entity import HeliosEntity

MANUAL = NumberEntityDescription(
    key="manual_angle",
    translation_key="manual_angle",
    native_unit_of_measurement=DEGREE,
    mode=NumberMode.SLIDER,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeliosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Per panel."""
    site = entry.runtime_data
    for panel in site.panels.values():
        async_add_entities(
            [HeliosManualAngle(site, panel, MANUAL)], config_subentry_id=panel.id
        )


class HeliosManualAngle(HeliosEntity, NumberEntity):
    """Setting it switches the panel to manual mode."""

    def __init__(
        self, site: HeliosSite, panel: Panel, description: NumberEntityDescription
    ) -> None:
        """Limits from the panel."""
        super().__init__(site, panel, description)
        self._attr_native_min_value = panel.cfg.min_angle
        self._attr_native_max_value = panel.cfg.max_angle
        self._attr_native_step = 1.0

    @property
    def native_value(self) -> float | None:
        """The manual angle (or the current angle before one is set)."""
        if self.panel.manual_angle is not None:
            return self.panel.manual_angle
        return self.panel.current

    async def async_set_native_value(self, value: float) -> None:
        """Go manual at this angle."""
        await self.site.async_set_tilt(self.panel, value)
