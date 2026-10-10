"""Actions: set_tilt, stow, resume_auto, set_mode, calibrate, home, calibrate_travel."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, MODES

if TYPE_CHECKING:
    from .controller import HeliosSite, Panel

SERVICE_SET_TILT = "set_tilt"
SERVICE_STOW = "stow"
SERVICE_RESUME = "resume_auto"
SERVICE_SET_MODE = "set_mode"
SERVICE_CALIBRATE = "calibrate"
SERVICE_HOME = "home"
SERVICE_CALIBRATE_TRAVEL = "calibrate_travel"

ATTR_ANGLE = "angle"
ATTR_STORM = "storm"
ATTR_MODE = "mode"
ATTR_ACTION = "action"
ATTR_HOMING_SECONDS = "homing_seconds"
TRAVEL_ACTIONS = ["start", "stop", "cancel"]

TARGET = {
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
}
ANGLE_SCHEMA = vol.Schema(
    {**TARGET, vol.Required(ATTR_ANGLE): vol.All(vol.Coerce(float), vol.Range(-90, 90))}
)
STOW_SCHEMA = vol.Schema(
    {**TARGET, vol.Optional(ATTR_STORM, default=False): cv.boolean}
)
RESUME_SCHEMA = vol.Schema(TARGET)
MODE_SCHEMA = vol.Schema({**TARGET, vol.Required(ATTR_MODE): vol.In(MODES)})
HOME_SCHEMA = vol.Schema(TARGET)
TRAVEL_SCHEMA = vol.Schema(
    {
        **TARGET,
        vol.Required(ATTR_ACTION): vol.In(TRAVEL_ACTIONS),
        vol.Optional(ATTR_HOMING_SECONDS): vol.All(
            vol.Coerce(float), vol.Range(1, 300)
        ),
    }
)


# Action name -> schema (fields besides the target are documented in services.yaml).
SCHEMAS: dict[str, vol.Schema] = {
    SERVICE_SET_TILT: ANGLE_SCHEMA,
    SERVICE_STOW: STOW_SCHEMA,
    SERVICE_RESUME: RESUME_SCHEMA,
    SERVICE_SET_MODE: MODE_SCHEMA,
    SERVICE_CALIBRATE: ANGLE_SCHEMA,
    SERVICE_HOME: HOME_SCHEMA,
    SERVICE_CALIBRATE_TRAVEL: TRAVEL_SCHEMA,
}


def _sites(hass: HomeAssistant) -> list[HeliosSite]:
    return [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]


def resolve_panels(
    hass: HomeAssistant, call: ServiceCall, require_target: bool = False
) -> dict[HeliosSite, list[Panel]]:
    """Panels named by the call's entities/devices (all panels without a target)."""
    sites = _sites(hass)
    if not sites:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_loaded"
        )
    entity_ids: list[str] = call.data.get(ATTR_ENTITY_ID) or []
    device_ids: list[str] = call.data.get(ATTR_DEVICE_ID) or []
    if not entity_ids and not device_ids:
        if require_target:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="target_required"
            )
        return {site: list(site.panels.values()) for site in sites}

    wanted: set[str] = set()
    ent_reg = er.async_get(hass)
    for entity_id in entity_ids:
        entry = ent_reg.async_get(entity_id)
        if entry is None or entry.platform != DOMAIN or not entry.config_subentry_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_a_panel",
                translation_placeholders={"target": entity_id},
            )
        wanted.add(entry.config_subentry_id)
    dev_reg = dr.async_get(hass)
    for device_id in device_ids:
        device = dev_reg.async_get(device_id)
        ids = (
            [ident[1] for ident in device.identifiers if ident[0] == DOMAIN]
            if device
            else []
        )
        if not ids:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_a_panel",
                translation_placeholders={"target": device_id},
            )
        wanted.update(ids)

    result: dict[HeliosSite, list[Panel]] = {}
    for site in sites:
        panels = [p for pid, p in site.panels.items() if pid in wanted]
        if panels:
            result[site] = panels
    if not result:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_a_panel",
            translation_placeholders={"target": ", ".join(entity_ids + device_ids)},
        )
    return result


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions."""

    async def set_tilt(call: ServiceCall) -> None:
        for site, panels in resolve_panels(hass, call).items():
            for panel in panels:
                await site.async_set_tilt(panel, call.data[ATTR_ANGLE])

    async def stow(call: ServiceCall) -> None:
        for site, panels in resolve_panels(hass, call).items():
            await site.async_stow(panels, call.data[ATTR_STORM])

    async def resume(call: ServiceCall) -> None:
        for site, panels in resolve_panels(hass, call).items():
            await site.async_resume(panels)

    async def set_mode(call: ServiceCall) -> None:
        for site, panels in resolve_panels(hass, call).items():
            for panel in panels:
                await site.async_set_mode(panel, call.data[ATTR_MODE])

    async def calibrate(call: ServiceCall) -> None:
        for site, panels in resolve_panels(hass, call, require_target=True).items():
            for panel in panels:
                await site.async_calibrate(panel, call.data[ATTR_ANGLE])

    hass.services.async_register(
        DOMAIN, SERVICE_SET_TILT, set_tilt, schema=ANGLE_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_STOW, stow, schema=STOW_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RESUME, resume, schema=RESUME_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_MODE, set_mode, schema=MODE_SCHEMA)

    def _relay_panels(call: ServiceCall) -> list[tuple[HeliosSite, Panel]]:
        found = [
            (site, panel)
            for site, panels in resolve_panels(hass, call, require_target=True).items()
            for panel in panels
            if panel.driver is not None
        ]
        if not found:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="not_relays"
            )
        return found

    async def home(call: ServiceCall) -> None:
        for site, panel in _relay_panels(call):
            site.async_home(panel)

    async def calibrate_travel(call: ServiceCall) -> None:
        for site, panel in _relay_panels(call):
            site.async_travel_calibration(
                panel, call.data[ATTR_ACTION], call.data.get(ATTR_HOMING_SECONDS)
            )

    hass.services.async_register(
        DOMAIN, SERVICE_CALIBRATE, calibrate, schema=ANGLE_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_HOME, home, schema=HOME_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_CALIBRATE_TRAVEL, calibrate_travel, schema=TRAVEL_SCHEMA
    )
