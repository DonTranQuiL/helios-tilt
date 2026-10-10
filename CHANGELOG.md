# Changelog

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
