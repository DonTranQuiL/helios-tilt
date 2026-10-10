"""Setup, card registration, unload and diagnostics."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.helios_tilt.const import CARD_URL, DOMAIN, VERSION
from custom_components.helios_tilt.diagnostics import async_get_config_entry_diagnostics


async def test_card_registered_with_hash(hass: HomeAssistant, setup_site) -> None:
    """The card is served and added to the frontend with a cache-busting hash."""
    hass.config.components.add("frontend")
    with patch("custom_components.helios_tilt.add_extra_js_url") as add:
        await setup_site()
    ours = [c.args[1] for c in add.call_args_list]
    assert len(ours) == 1
    assert ours[0].startswith(f"{CARD_URL}?v={VERSION}-")
    assert len(ours[0].rsplit("-", 1)[1]) == 8


async def test_unload_stops_everything(
    hass: HomeAssistant, setup_site, weather, cover
) -> None:
    """After unload nothing reacts to the weather any more."""
    entry = await setup_site()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    weather(wind_speed=90)
    await hass.async_block_till_done()
    assert cover.positions == [25]


async def test_diagnostics_redacts_location(hass: HomeAssistant, setup_site) -> None:
    """Latitude and longitude never leave the house."""
    entry = await setup_site()
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["version"] == VERSION
    assert diag["entry"]["data"]["latitude"] == "**REDACTED**"
    assert diag["state"]["safety"]["state"] == "ok"
    assert "Panel 1" in diag["state"]["panels"]
    assert diag["entry"]["subentries"][0]["type"] == "panel"
    assert DOMAIN
