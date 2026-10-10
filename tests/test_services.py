"""Actions."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.helios_tilt.const import DOMAIN

from .conftest import PANEL_DATA, panel_of

TARGET = "sensor.panel_1_target_angle"


async def test_set_tilt_and_resume(hass: HomeAssistant, setup_site, cover) -> None:
    """set_tilt goes manual (clamped); resume_auto returns to the strategy."""
    await setup_site()
    await hass.services.async_call(
        DOMAIN, "set_tilt", {"entity_id": TARGET, "angle": 80}, blocking=True
    )
    assert cover.positions == [25, 100]
    assert hass.states.get("select.panel_1_mode").state == "manual"
    await hass.services.async_call(
        DOMAIN, "resume_auto", {"entity_id": TARGET}, blocking=True
    )
    assert cover.positions == [25, 100, 25]
    assert hass.states.get("select.panel_1_mode").state == "auto"


async def test_stow_by_device_and_storm(hass: HomeAssistant, setup_site, cover) -> None:
    """Stow a device; storm latches site-wide until resumed."""
    entry = await setup_site()
    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    await hass.services.async_call(
        DOMAIN, "stow", {"device_id": device.id}, blocking=True
    )
    assert cover.positions == [25, 0]
    assert hass.states.get("sensor.panel_1_last_move").state == "stow"
    assert hass.states.get("binary_sensor.panel_1_wind_stow").state == "on"
    await hass.services.async_call(DOMAIN, "stow", {"storm": True}, blocking=True)
    assert hass.states.get("binary_sensor.panel_1_storm_mode").state == "on"
    await hass.services.async_call(DOMAIN, "resume_auto", {}, blocking=True)
    assert hass.states.get("binary_sensor.panel_1_storm_mode").state == "off"
    assert cover.positions[-1] == 25


async def test_set_mode_all_panels(hass: HomeAssistant, setup_site, cover) -> None:
    """Without a target the action applies to every panel."""
    hass.states.async_set("cover.two", "closed", {"current_position": 0})
    entry = await setup_site(
        panels=[{**PANEL_DATA}, {**PANEL_DATA, "actuator_entity": "cover.two"}]
    )
    await hass.services.async_call(
        DOMAIN, "set_mode", {"mode": "seasonal"}, blocking=True
    )
    assert {p.mode for p in entry.runtime_data.panels.values()} == {"seasonal"}


async def test_calibrate(hass: HomeAssistant, setup_site) -> None:
    """Calibrate sets the known angle without moving; needs a target."""
    entry = await setup_site()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "calibrate", {"angle": 20}, blocking=True
        )
    await hass.services.async_call(
        DOMAIN, "calibrate", {"entity_id": TARGET, "angle": 22}, blocking=True
    )
    panel = panel_of(entry)
    assert panel.commanded == 22
    assert hass.states.get("sensor.panel_1_last_move").state == "calibrate"
    assert hass.states.get("sensor.panel_1_moves_today").state == "1"


async def test_bad_targets(hass: HomeAssistant, setup_site) -> None:
    """Entities of other integrations are refused."""
    await setup_site()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "stow", {"entity_id": "weather.home"}, blocking=True
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "stow", {"device_id": "nope"}, blocking=True
        )


async def test_not_loaded(hass: HomeAssistant, setup_site) -> None:
    """Actions explain when nothing is loaded."""
    entry = await setup_site()
    await hass.config_entries.async_unload(entry.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "resume_auto", {}, blocking=True)
