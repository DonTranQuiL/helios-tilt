"""Static checks: versions, translations, services and the card stay in sync."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from custom_components.helios_tilt.const import CARD_FILENAME, DOMAIN, VERSION
from custom_components.helios_tilt.services import SCHEMAS, TARGET

ROOT = Path(__file__).parent.parent
COMPONENT = ROOT / "custom_components" / DOMAIN


def _json(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def test_manifest_version_matches_const() -> None:
    """The release workflow bumps both; they must never drift."""
    manifest = _json(COMPONENT / "manifest.json")
    assert manifest["version"] == VERSION
    assert manifest["domain"] == DOMAIN
    assert manifest["name"] == "Helios Tilt"
    assert manifest["requirements"] == []
    assert manifest["documentation"].endswith("/helios-tilt")
    assert "DonTranQuiL/helios-tilt" in manifest["issue_tracker"]


def test_manifest_version_is_valid() -> None:
    """Home Assistant parses the version with AwesomeVersion (PEP 440 / SemVer)."""
    from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

    version = AwesomeVersion(_json(COMPONENT / "manifest.json")["version"])
    assert version.strategy in (
        AwesomeVersionStrategy.PEP440,
        AwesomeVersionStrategy.SEMVER,
        AwesomeVersionStrategy.SIMPLEVER,
    )


def test_card_version_matches() -> None:
    """The card reports the same version as the integration."""
    card = (COMPONENT / "frontend" / CARD_FILENAME).read_text("utf-8")
    match = re.search(r'const VERSION = "([^"]+)"', card)
    assert match and match.group(1) == VERSION


def test_card_is_ascii() -> None:
    """Non-ASCII in the bundle breaks some proxies; use escapes."""
    card = (COMPONENT / "frontend" / CARD_FILENAME).read_bytes()
    assert card.isascii()


def test_hacs_json() -> None:
    """hacs.json has no deprecated keys."""
    hacs = _json(ROOT / "hacs.json")
    assert hacs["name"] == "Helios Tilt"
    assert "domains" not in hacs
    assert "homeassistant" in hacs


def _keys(obj: dict, prefix: str = "") -> set[str]:
    keys = set()
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys |= _keys(value, path)
        else:
            keys.add(path)
    return keys


def test_translations_in_sync() -> None:
    """Every language has exactly the English keys."""
    english = _keys(_json(COMPONENT / "translations" / "en.json"))
    for path in (COMPONENT / "translations").glob("*.json"):
        assert _keys(_json(path)) == english, path.name


def test_services_documented() -> None:
    """services.yaml, the schemas, translations and icons list the same actions."""
    services = yaml.safe_load((COMPONENT / "services.yaml").read_text("utf-8"))
    strings = _json(COMPONENT / "translations" / "en.json")["services"]
    icons = _json(COMPONENT / "icons.json")["services"]
    assert set(services) == set(SCHEMAS) == set(strings) == set(icons)
    target = {str(key) for key in TARGET}
    for name, service in services.items():
        fields = set(service.get("fields", {}))
        assert fields == set(strings[name].get("fields", {})), name
        schema_fields = {str(key) for key in SCHEMAS[name].schema} - target
        assert fields == schema_fields, name


def test_entity_translations_and_icons() -> None:
    """Every entity key has a name and an icon."""
    strings = _json(COMPONENT / "translations" / "en.json")["entity"]
    icons = _json(COMPONENT / "icons.json")["entity"]
    for platform, entities in strings.items():
        assert set(entities) == set(icons[platform]), platform
