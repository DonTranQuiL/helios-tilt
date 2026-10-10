# Changelog

## 0.1.0 (2026-10-10)

First stable release, tested on a real Tuya ZG-2002-RF two-relay setup.

**Highlights**

- **Works with dumb actuators:** the *Two relays (timed)* actuator type drives actuators that have no feedback. It estimates the position from run time (separate open and close times), homes against the limit switches, interlocks the relays, uses the relay countdown as a fail-safe, detects the RF remote, and handles offline relays. A guided **Time the travel** calibration is included and **required** after setup.
- Real sun position and four strategies: daily optimum, tracking with a cloudy-day mode and night park, a seasonal curve, and a fixed annual optimum.
- Safety first: wind and gust stow with a calm period, a latching storm mode, snow/rain/frost positions, custom stow triggers and an optional wind direction rule.
- Customization: your own rain, snow and temperature sensors; quiet hours; a timed stow; and source attributes that show what drives each decision.
- A dashboard card in English and Dutch, with badges for relay offline, uncertain position and quiet hours.

**Changes since beta.6**

- Quiet hours no longer hold the **night park** (tracking strategy): parking at sunset still happens, and the panel then rests until the quiet hours end. Daytime strategy moves stay held.
- README rewritten:
  - a "Works with dumb actuators" section with a wiring diagram;
  - a required calibration guide and a complete ZG-2002-RF example;
  - how the strategies choose the angle, including why panels sit at their maximum in autumn and winter;
  - the safety priority, the customization options, and an FAQ.
- Docs site updated to match.

## 0.1.0-beta.6 (2026-10-10)

- **Source transparency:** the *Wind stow* and *Storm mode* sensors (and diagnostics) show the sources (`weather_entity`, `wind_sensor`), each value (`weather_wind`, `weather_gust`, `sensor_wind`) and which one drives the wind now (`wind_source`), plus the wind bearing and the temperature source. The README and the setup help recommend a weather entity with gusts (e.g. Buienradar).
- **Dedicated sensors** (Configure, optional): rain (binary sensor, or a rate in mm/h, mm/d, in/h, in/d with a threshold), snow (binary sensor, or a depth in mm/cm/m/in/ft with a threshold) and an outdoor temperature sensor (°F converted) for frost. They override the weather condition while available and fall back to it otherwise.
- **Custom stow triggers** (Configure, optional): a list of entities; while any is on, panels stow at the trigger angle (or their stow angle), with safety priority. The reason and the card name the trigger.
- `helios_tilt.stow` takes an optional `duration` and resumes by itself afterwards.
- **Quiet hours** (Configure, optional): a time window, which may cross midnight, without automatic moves. Safety moves are allowed by default (configurable); storm mode always moves, as do your own commands. The target shows reason `quiet` and *until HH:MM*; the card shows a Quiet hours badge.
- **Wind direction rule** (Configure, optional, off by default): only stow for wind within ± X° of the panel's front and/or rear, from the weather `wind_bearing` or a direction sensor (degrees or N/NE/…). Storm speed always stows; no bearing means stowing from any direction.
- Options are grouped into collapsed sections. en/nl translations.

## 0.1.0-beta.5 (2026-10-10)

- Two relays: before any run or calibration, both relays (and the countdowns, if set) must be available. While one is unavailable (Zigbee device offline), nothing is switched and nothing is retried. Helios logs `Relay switch.X is unavailable (Zigbee device offline?)` once and raises a *relay offline* repair. It all clears by itself when the device is back, and the panel then drives to its target.
- New *Actuator available* binary sensor (connectivity). The current-angle sensor gets `actuator_available` / `unavailable_entities` attributes, and the card shows a **Relay offline** badge and disables Home.
- **Home now**, calibration start (button or action) and the guided calibration show a clear, translated error while a relay is offline, instead of silently doing nothing.
- A relay that goes offline mid-run stops the run, marks the position uncertain and homes after it is back, without counting as a fault.
- Faults back off (1, 2, 4 … 30 minutes) instead of being retried every round.
- A relay that is already off counts as confirmed off straight away (now covered by a test).
- No more "did not reach … (at None)" warning when there is no position reading; relay panels report their own faults.

## 0.1.0-beta.4 (2026-10-10)

- Panel setup in steps. Step 1 asks for the name and actuator type, step 2 for only that type's fields (entity + mapping, or the relays, countdowns, travel times and end angles) plus the geometry, and step 3 for the positions and PV. The generic *Actuator* field no longer appears for two-relay panels. Reconfigure uses the same steps, and switching the type drops the old type's settings.
- Positions are kept within the soft limits: defaults are clamped, the fields stop at the limits, and the help text shows the range.
- The seasonal winter/summer angles are suggested from the latitude (about lat + 15° / lat − 35°, clamped). Equal winter and summer angles show a one-time hint that the curve is flat.
- Two-relay panels never command or watch a generic actuator entity, even if one was saved earlier.
- Clearer errors: same relay, same countdown and same end angles point at the field.

## 0.1.0-beta.3 (2026-10-10)

- New actuator type **Two relays (timed)** for dumb actuators without position feedback, such as a Tuya ZG-2002-RF dual relay via Zigbee2MQTT. The position is estimated from run time, with separate open and close speeds and an optional start delay.
- Interlock: the opposite relay is switched off and confirmed, then a 0.3 s wait, plus a pause on a direction change. A run aborts when a relay doesn't confirm, and both are switched off if both are ever on. Each run has a maximum length.
- Hardware fail-safe: the relay's countdown is armed for every run (after the relay confirms on, because Tuya countdowns toggle) and cleared afterwards.
- Homing: runs to an end stop overrun by 15 %. It also homes on the first move, after a restart mid-run or a fault, after N moves, and before the night park. The estimate is saved. A **Home now** button and a `helios_tilt.home` action.
- Travel calibration: a guided Reconfigure step (it closes, opens, and you submit at each end), buttons, or `helios_tilt.calibrate_travel`. Wind and storm cancel a calibration and stow.
- Switching the relays by hand (remote, z2m) is detected and tracked, capped, and pauses automatic control. On shutdown or unload, both relays are switched off.
- New entities: a *Position uncertain* binary sensor and *Home now* / travel-calibration buttons. The current-angle sensor shows the estimated stroke and direction.
- Card: an "estimated" label, an uncertain badge, the run direction and a Home button for relay panels.
- README: two-relay setup, wiring and safety notes, calibration walkthrough and a ZG-2002-RF example.

## 0.1.0-beta.2 (2026-10-10)

- Estimated gain: only time spent following the strategy counts now. Wind, storm and manual stows, weather positions, manual mode, diffuse parking and data freezes no longer drag it below zero; they are reported as `excluded_minutes`.
- Estimated gain: the fixed reference is the annual optimum rounded to the panel's step and limits, the sun is taken mid-interval, and new attributes show the moment's value (`instant_gain`), the basis and when counting started.
- Tracking aims for the most clear-sky irradiance (beam plus sky diffuse) instead of pointing straight at the sun, so it never models below the fixed angle.
- Card: the gain reads "today vs fixed", with the current value next to it.

## 0.1.0-beta.1 (2026-10-10)

First public beta.

- Site and panel setup through the UI: config subentries per panel, with options and reconfigure.
- NOAA sun position (with refraction) and a clear-sky model, computed locally without extra packages.
- Strategies: fixed annual optimum, seasonal curve, daily optimum, sun tracking (cloudy-day diffuse mode, night park).
- Safety: wind and gust stow with a calm-period resume, storm latch, snow/rain/frost positions, a freeze on stale data, and no moves until data is valid.
- Actuators: cover, number/input_number or script; linear or calibration-table mapping; feedback sensor, cover position or open-loop estimate.
- Hardware protection: never commands a moving actuator; minimum move interval, deadband and hysteresis; manual-move detection with a pause; a repair notice for stuck actuators.
- Entities per panel, actions (`set_tilt`, `stow`, `resume_auto`, `set_mode`, `calibrate`), logbook entries and a `helios_tilt_move` event.
- Bundled dashboard card with a visual editor, in English and Dutch.
- Diagnostics with the location redacted.
