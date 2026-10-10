"""Binary sensors: storm mode and wind stow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeliosConfigEntry
from .controller import HeliosSite, Panel
from .entity import HeliosEntity


@dataclass(frozen=True, kw_only=True)
class HeliosBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor with a value function."""

    value_fn: Callable[[HeliosSite, Panel], bool]


def _wind_attrs(site: HeliosSite, panel: Panel) -> dict[str, Any]:
    s = site.safety.settings
    return {
        "wind_speed": None
        if site.readings.wind is None
        else round(site.readings.wind, 1),
        "stow_speed": s.wind_stow,
        "resume_speed": s.wind_resume,
        "storm_speed": s.storm_speed,
        "unit": "km/h",
        "safety": site.safety.last.state,
        "detail": site.safety.last.detail,
        "calm_minutes": s.calm_minutes,
    }


BINARY_SENSORS: tuple[HeliosBinaryDescription, ...] = (
    HeliosBinaryDescription(
        key="storm",
        translation_key="storm",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=lambda site, panel: site.safety.storm,
    ),
    HeliosBinaryDescription(
        key="wind_stow",
        translation_key="wind_stow",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=lambda site, panel: site.safety.last.stow or panel.stowed,
    ),
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
            [HeliosBinarySensor(site, panel, d) for d in BINARY_SENSORS],
            config_subentry_id=panel.id,
        )


class HeliosBinarySensor(HeliosEntity, BinarySensorEntity):
    """Storm or wind stow."""

    entity_description: HeliosBinaryDescription

    @property
    def is_on(self) -> bool:
        """Active."""
        return self.entity_description.value_fn(self.site, self.panel)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Wind numbers for the card."""
        return _wind_attrs(self.site, self.panel)
