"""Buttons for panels on two relays: home now and the travel calibration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeliosConfigEntry
from .controller import HeliosSite, Panel
from .entity import HeliosEntity


@dataclass(frozen=True, kw_only=True)
class HeliosButtonDescription(ButtonEntityDescription):
    """Button with a press function."""

    press_fn: Callable[[HeliosSite, Panel], object]


BUTTONS: tuple[HeliosButtonDescription, ...] = (
    HeliosButtonDescription(
        key="home",
        translation_key="home",
        press_fn=lambda site, panel: site.async_home(panel),
    ),
    HeliosButtonDescription(
        key="travel_start",
        translation_key="travel_start",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda site, panel: site.async_travel_calibration(panel, "start"),
    ),
    HeliosButtonDescription(
        key="travel_mark",
        translation_key="travel_mark",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda site, panel: site.async_travel_calibration(panel, "stop"),
    ),
    HeliosButtonDescription(
        key="travel_cancel",
        translation_key="travel_cancel",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda site, panel: site.async_travel_calibration(panel, "cancel"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeliosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Only panels driven by two relays get these."""
    site = entry.runtime_data
    for panel in site.panels.values():
        if panel.driver is None:
            continue
        async_add_entities(
            [HeliosButton(site, panel, d) for d in BUTTONS],
            config_subentry_id=panel.id,
        )


class HeliosButton(HeliosEntity, ButtonEntity):
    """Home now or a calibration step."""

    entity_description: HeliosButtonDescription

    async def async_press(self) -> None:
        """Do it."""
        self.entity_description.press_fn(self.site, self.panel)
