---
name: 🐛 Bug report
about: Report a problem or unexpected behavior in Helios Tilt
title: "[BUG] <Brief description of the issue>"
labels: bug
assignees: ''
---

## 🛑 Checklist
- [ ] I am using the latest version of Helios Tilt.
- [ ] I have checked the existing open and closed issues.
- [ ] I have enabled debug logging and included the logs below.

## 📝 Description
What happened, and what did you expect to happen?

## ⚙️ Setup
- **Helios Tilt version:** (e.g. v0.1.0-beta.1)
- **Home Assistant version:**
- **Actuator:** (cover / number / script, and what drives it: ESPHome, MQTT, Shelly, ...)
- **Feedback:** (cover position / separate sensor / none)
- **Axis and strategy:** (tilt or roll; fixed / seasonal / daily / tracking)
- **Wind source:** (weather entity / wind sensor / both)

## 🔁 Steps to reproduce
1.
2.
3.

## 📋 Logs
```yaml
logger:
  logs:
    custom_components.helios_tilt: debug
```

Or download the diagnostics: Settings → Devices & services → Helios Tilt → ⋮ → Download diagnostics (latitude and longitude are redacted).

```
paste logs here
```
