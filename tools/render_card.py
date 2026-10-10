"""Render docs/images/card.png from demo states (see tests/_dump_demo.py)."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARD = ROOT / "custom_components" / "helios_tilt" / "frontend" / "helios-tilt-card.js"
data = json.loads(
    Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/helios_demo.json").read_text()
)
out = ROOT / "docs" / "images" / "card.png"

page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
  html, body {{ margin: 0; background: #111318; font-family: Roboto, "Segoe UI", Arial, sans-serif; }}
  body {{
    --primary-text-color: #e6e8eb; --secondary-text-color: #9aa3ad; --divider-color: rgba(255,255,255,.12);
    --card-background-color: #1c1f26; --primary-color: #03a9f4; --text-primary-color: #fff;
    --success-color: #43a047; --warning-color: #ff9800; --error-color: #e53935; --info-color: #2f80ed;
    padding: 24px;
  }}
  ha-card {{ display: block; background: var(--card-background-color); border-radius: 16px; box-shadow: 0 2px 10px rgba(0,0,0,.4); }}
  .demo {{ color: #9aa3ad; font-size: 13px; margin: 0 0 10px 4px; letter-spacing: .03em; }}
  .demo b {{ color: #ffb52e; }}
  #box {{ width: 1000px; }}
</style></head><body>
<div class="demo"><b>DEMO DATA</b> &middot; Helios Tilt card &middot; two simulated panels, 12 Sep 2026 16:20</div>
<div id="box"></div>
<script>
  const DEMO_NOW = {json.dumps(data["now"])};
  const RealDate = Date;
  class FakeDate extends RealDate {{
    constructor(...a) {{ super(...(a.length ? a : [DEMO_NOW])); }}
    static now() {{ return new RealDate(DEMO_NOW).getTime(); }}
  }}
  window.Date = FakeDate;
</script>
<script type="module">
{CARD.read_text()}
const DATA = {json.dumps(data).replace("</", "<\\/")};
const card = document.createElement("helios-tilt-card");
card.setConfig({{ title: "Solar tilt", history_count: 4 }});
document.getElementById("box").appendChild(card);
card.hass = {{ states: DATA.states, entities: DATA.entities, devices: DATA.devices, language: "en", callService: async () => {{}} }};
</script></body></html>"""

with tempfile.TemporaryDirectory() as tmp:
    html = Path(tmp) / "card.html"
    html.write_text(page, "utf-8")
    env = {**os.environ, "TZ": "Europe/Amsterdam"}
    subprocess.run(
        [
            "google-chrome",
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=2",
            "--window-size=1048,760",
            "--virtual-time-budget=3000",
            f"--screenshot={out}",
            html.as_uri(),
        ],
        check=True,
        env=env,
        capture_output=True,
    )
print(out)
