# Changelog

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
