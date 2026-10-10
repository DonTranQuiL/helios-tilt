"""The event-loop blocking guard in conftest.py really catches blocking calls."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.helios_tilt import _file_digest
from custom_components.helios_tilt.const import CARD_FILENAME, DOMAIN


async def test_guard_catches_file_io_in_loop(
    hass: HomeAssistant, no_blocking_io_in_loop
) -> None:
    """Calling the executor-only digest helper in the loop is reported."""
    card = (
        Path(__file__).parent.parent
        / "custom_components"
        / DOMAIN
        / "frontend"
        / CARD_FILENAME
    )
    _file_digest(card)
    assert no_blocking_io_in_loop
    assert "__init__.py" in no_blocking_io_in_loop[0]
    no_blocking_io_in_loop.clear()


async def test_setup_flow_and_unload_do_not_block(
    hass: HomeAssistant, setup_site, no_blocking_io_in_loop
) -> None:
    """Setup with the frontend (card hash), actions and unload stay off the disk."""
    hass.config.components.add("frontend")
    with patch("custom_components.helios_tilt.add_extra_js_url"):
        entry = await setup_site()
    await hass.services.async_call(DOMAIN, "stow", {}, blocking=True)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert no_blocking_io_in_loop == []
