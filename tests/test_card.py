"""Run the dashboard card in headless Chrome against real entity states.

Skipped when no Chrome/Chromium is installed (GitHub's Ubuntu runners have one).
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.helios_tilt.const import CARD_FILENAME, DOMAIN

ROOT = Path(__file__).parent.parent
CARD = ROOT / "custom_components" / DOMAIN / "frontend" / CARD_FILENAME
HARNESS = Path(__file__).parent / "card" / "harness.js"
CHROME = next(
    (
        shutil.which(name)
        for name in (
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
        )
        if shutil.which(name)
    ),
    None,
)


def test_card_calls_only_existing_services() -> None:
    """Every action the card calls exists, with fields that exist."""
    services = yaml.safe_load((CARD.parent.parent / "services.yaml").read_text("utf-8"))
    source = CARD.read_text("utf-8")
    calls = re.findall(r'this\._call\("(\w+)", \{([^}]*)\}', source)
    assert {name for name, _ in calls} == {
        "resume_auto",
        "stow",
        "set_mode",
        "set_tilt",
        "home",
    }
    for service, body in calls:
        assert service in services, service
        keys = set(re.findall(r"(\w+):", body)) - {"entity_id"}
        assert keys <= set(services[service].get("fields", {})), (service, keys)


async def card_data(hass: HomeAssistant, entry) -> dict:
    """States plus the registry bits the frontend gives a card."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    entities = {}
    states = {}
    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        entities[entity.entity_id] = {
            "entity_id": entity.entity_id,
            "device_id": entity.device_id,
            "platform": entity.platform,
            "translation_key": entity.translation_key,
        }
        states[entity.entity_id] = json.loads(
            json.dumps(hass.states.get(entity.entity_id).as_dict(), default=str)
        )
    devices = {
        d.id: {"name": d.name, "name_by_user": d.name_by_user}
        for d in dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    }
    return {"states": states, "entities": entities, "devices": devices}


def run_card(data: dict) -> dict:
    """Load the card and the harness in headless Chrome; return the results."""
    page_html = (
        "<!doctype html><html><head><meta charset='utf-8'></head><body>"
        f"<script type='application/json' id='states'>{json.dumps(data).replace('</', '<\\/')}</script>"
        "<pre id='out'></pre>"
        f"<script type='module'>{CARD.read_text('utf-8')}\n{HARNESS.read_text('utf-8')}</script>"
        "</body></html>"
    )
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "card.html"
        page.write_text(page_html, "utf-8")
        out = subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--window-size=1200,900",
                "--virtual-time-budget=5000",
                "--dump-dom",
                page.as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        ).stdout
    match = re.search(r'<pre id="out">(.*?)</pre>', out, re.S)
    assert match, out[-2000:]
    return json.loads(html.unescape(match.group(1)))


@pytest.mark.skipif(CHROME is None, reason="no Chrome/Chromium installed")
async def test_card_in_browser(hass: HomeAssistant, setup_site, freezer) -> None:
    """Render, click every control, and check escaping, layout and the editor."""
    entry = await setup_site(panels=[{"title": "Garage roof", **_panel()}])
    await hass.services.async_call(
        DOMAIN, "set_mode", {"mode": "tracking"}, blocking=True
    )
    data = await card_data(hass, entry)
    data["target"] = "sensor.garage_roof_target_angle"
    data["last"] = "sensor.garage_roof_last_move"
    data["current"] = "sensor.garage_roof_current_angle"
    assert data["target"] in data["states"]

    result = await hass.async_add_executor_job(run_card, data)
    c = result["checks"]
    assert result["errors"] == [], result["errors"]
    assert c["panels"] == 1
    assert c["names"] == ["Garage roof"]
    assert c["chip"] == "Tracking the sun"
    assert c["big"] == "25\u00b0"
    assert c["bad_text"] == []
    assert c["sun"] == 1
    assert c["sunpath"] == 1
    assert c["plan_points"] == 49
    assert c["wind_text"] == "15 km/h"
    assert c["marks"] == 2
    assert c["history"] == 2
    assert c["history_first"].startswith("Strategy")
    assert c["buttons"] == ["auto", "stow", "manual"]
    assert c["active"] == ["auto"]
    assert c["slider"] == {"min": "0", "max": "60"}
    assert c["renders_same"] == 0
    assert c["renders_unrelated"] == 0
    assert c["slider_output"] == "35\u00b0"
    assert c["kept_while_dragging"] is True
    services = [(x["service"], x["data"]) for x in result["calls"]]
    assert services[:4] == [
        ("resume_auto", {"entity_id": data["target"]}),
        ("stow", {"entity_id": data["target"]}),
        ("set_mode", {"entity_id": data["target"], "mode": "manual"}),
        ("set_tilt", {"entity_id": data["target"], "angle": 35}),
    ]
    assert all(x["domain"] == DOMAIN for x in result["calls"])
    assert "boom <b>bold</b>" in c["error"]
    assert c["error_markup"] == 0
    assert c["enabled_after_error"] is True
    assert c["ghost"] == 1
    assert c["stowed_chip"] == "Stowed"
    assert c["quiet_badge"] == "Quiet hours"
    assert c["quiet_title"].startswith("Quiet hours until ")
    assert c["quiet_chip"] == "Quiet hours"
    assert c["no_quiet_badge"] == 0
    assert c["trigger_chip"] == "Stow trigger"
    assert c["trigger_detail"] == "Party mode"
    assert c["trigger_stow_active"] is True
    assert c["exempt_chip"] == "Tracking the sun"
    assert c["moon"] == 1
    assert c["night_sun"] == 0
    assert c["xss_nodes"] == 0
    assert c["xss_text"] is True
    assert c["xss_fired"] == 0
    assert c["fallback_names"] == ["Garage roof"]
    assert c["fallback_history"] == 2
    assert c["not_found"] is True
    assert c["unavailable"] is True
    assert c["relay_est"] == "estimated"
    assert c["relay_badge"] == "Position uncertain"
    assert c["relay_moving"] == "closing"
    assert c["relay_buttons"] == ["auto", "stow", "manual", "home"]
    assert c["relay_home_attention"] is True
    assert ("home", {"entity_id": data["target"]}) in services
    assert c["plain_est"] == 0
    assert c["offline_badge"] == "Relay offline"
    assert c["offline_title"] == "Unavailable: switch.windowswitch_l1"
    assert c["offline_home_disabled"] is True
    assert c["online_badge"] == 0
    assert c["relay_nl"] == ["geschat", "Referentie"]
    assert c["nl_buttons"] == ["Auto", "Veilig", "Handmatig"]
    assert c["narrow_direction"] == "column"
    assert c["narrow_overflow"] is False
    assert c["wide_direction"] == "row"
    assert c["bare_blocks"] == 0
    assert c["bad_config"] == "rejected"
    assert c["bad_entities"] == "rejected"
    assert c["stub"] == {"entities": [data["target"]]}
    assert c["card_size"] == 6
    assert c["editor_fields"] == [
        "title",
        "entities",
        "show_wind",
        "show_controls",
        "show_curve",
        "show_history",
        "history_count",
    ]
    assert c["editor_label"] == "Wind gauge"
    assert c["editor_config"]["title"] == "Roof"
    assert "entities" not in c["editor_config"]
    assert c["registered"] == 1


def _panel() -> dict:
    from .conftest import PANEL_DATA

    return dict(PANEL_DATA)
