"""Binary sensors: storm mode, wind stow and (two relays) position uncertain."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
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


UNCERTAIN = HeliosBinaryDescription(
    key="position_uncertain",
    translation_key="position_uncertain",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda site, panel: bool(panel.driver and panel.driver.uncertain),
)


AVAILABLE = HeliosBinaryDescription(
    key="actuator_available",
    translation_key="actuator_available",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda site, panel: bool(panel.driver and panel.driver.available),
)


def _relay_attrs(site: HeliosSite, panel: Panel) -> dict[str, Any]:
    driver = panel.driver
    assert driver is not None
    position = driver.current_position()
    return {
        "stroke": None if position is None else round(position, 1),
        "moves_since_home": driver.moves_since_home,
        "travel_since_home": round(driver.travel_since_home),
        "home_after_moves": driver.cfg.home_after_moves,
        "last_homed": driver.last_homed.isoformat() if driver.last_homed else None,
        "fault": driver.fault,
        "actuator_available": driver.available,
        "unavailable_entities": list(driver.unavailable),
        "retry_after": driver.retry_after.isoformat() if driver.retry_after else None,
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeliosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Per panel."""
    site = entry.runtime_data
    for panel in site.panels.values():
        entities = [HeliosBinarySensor(site, panel, d) for d in BINARY_SENSORS]
        if panel.driver is not None:
            entities.append(HeliosBinarySensor(site, panel, UNCERTAIN))
            entities.append(HeliosBinarySensor(site, panel, AVAILABLE))
        async_add_entities(entities, config_subentry_id=panel.id)


class HeliosBinarySensor(HeliosEntity, BinarySensorEntity):
    """Storm or wind stow."""

    entity_description: HeliosBinaryDescription

    @property
    def is_on(self) -> bool:
        """Active."""
        return self.entity_description.value_fn(self.site, self.panel)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Wind numbers for the card (relay numbers for position uncertain)."""
        if self.entity_description.key in (UNCERTAIN.key, AVAILABLE.key):
            return _relay_attrs(self.site, self.panel)
        return _wind_attrs(self.site, self.panel)
