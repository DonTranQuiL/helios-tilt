"""Generate translations/en.json and nl.json (run from the repo root)."""

import json
from pathlib import Path

OUT = Path("custom_components/helios_tilt/translations")

SITE = {
    "en": {
        "name": "Name",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "weather_entity": "Weather entity",
        "wind_sensor": "Wind speed sensor",
    },
    "nl": {
        "name": "Naam",
        "latitude": "Breedtegraad",
        "longitude": "Lengtegraad",
        "weather_entity": "Weer-entiteit",
        "wind_sensor": "Windsnelheidssensor",
    },
}
SITE_DESC = {
    "en": {
        "latitude": "Defaults to your Home Assistant location.",
        "longitude": "Defaults to your Home Assistant location.",
        "weather_entity": "Wind speed, gusts, condition (snow/rain), temperature and cloud cover.",
        "wind_sensor": "Optional local anemometer. The highest of all wind readings is used.",
    },
    "nl": {
        "latitude": "Standaard de locatie van Home Assistant.",
        "longitude": "Standaard de locatie van Home Assistant.",
        "weather_entity": "Windsnelheid, windstoten, conditie (sneeuw/regen), temperatuur en bewolking.",
        "wind_sensor": "Optionele eigen windmeter. De hoogste van alle windwaarden telt.",
    },
}
PANEL = {
    "en": {
        "name": "Panel name",
        "actuator_entity": "Actuator",
        "axis": "Axis",
        "azimuth": "Azimuth",
        "min_angle": "Minimum angle",
        "max_angle": "Maximum angle",
        "step": "Step",
        "strategy": "Strategy",
    },
    "nl": {
        "name": "Paneelnaam",
        "actuator_entity": "Actuator",
        "axis": "As",
        "azimuth": "Azimut",
        "min_angle": "Minimale hoek",
        "max_angle": "Maximale hoek",
        "step": "Stap",
        "strategy": "Strategie",
    },
}
PANEL_DESC = {
    "en": {
        "actuator_entity": "A cover (set_cover_position), a number / input_number, or a script (gets angle, position and panel as variables).",
        "axis": "Tilt: the panel leans toward the azimuth (0 = flat). Roll: a single-axis tracker; negative angles tilt the other way.",
        "azimuth": "Tilt: the direction the panel faces (180 = south). Roll: the direction of positive tilt (axis + 90).",
        "min_angle": "Soft limit, never commanded below this.",
        "max_angle": "Soft limit, never commanded above this.",
        "step": "Targets are rounded to this step (0 = no rounding).",
        "strategy": "How the angle is chosen in automatic mode.",
    },
    "nl": {
        "actuator_entity": "Een cover (set_cover_position), een number / input_number of een script (krijgt angle, position en panel als variabelen).",
        "axis": "Kantelen: het paneel helt naar de azimut (0 = plat). Rollen: een eenassige tracker; negatieve hoeken kantelen de andere kant op.",
        "azimuth": "Kantelen: de richting waarin het paneel kijkt (180 = zuid). Rollen: de richting van positieve kanteling (as + 90).",
        "min_angle": "Zachte grens, er wordt nooit lager gestuurd.",
        "max_angle": "Zachte grens, er wordt nooit hoger gestuurd.",
        "step": "Doelhoeken worden op deze stap afgerond (0 = niet afronden).",
        "strategy": "Hoe de hoek in automatische modus wordt gekozen.",
    },
}
SECTIONS = {
    "en": {
        "mapping_feedback": (
            "Actuator mapping and feedback",
            {
                "mapping": "Mapping",
                "position_at_min": "Position at minimum angle",
                "position_at_max": "Position at maximum angle",
                "calibration": "Calibration table",
                "feedback_entity": "Feedback sensor",
                "feedback_kind": "Feedback reports",
                "travel_time": "Full stroke travel time",
            },
            {
                "position_at_min": "Swap the two positions to invert the actuator.",
                "calibration": "angle:position pairs, e.g. 0:0, 15:22, 30:47, 45:75, 60:100",
                "feedback_entity": "Optional. Without it the cover position is used, or an estimate from the travel time.",
                "travel_time": "Seconds from minimum to maximum. Used for estimates and the stuck check.",
            },
        ),
        "positions": (
            "Positions and seasonal curve",
            {
                "stow_angle": "Stow angle (wind/storm)",
                "night_angle": "Night park angle",
                "diffuse_angle": "Cloudy (diffuse) angle",
                "snow_angle": "Snow shedding angle",
                "rain_angle": "Heavy rain angle",
                "frost_angle": "Frost angle",
                "winter_angle": "Winter angle",
                "summer_angle": "Summer angle",
                "season_weight": "Season weight",
            },
            {
                "stow_angle": "Lowest wind load for your mount, usually flat.",
                "season_weight": "Seasonal strategy: 50 is a plain cosine, higher stays at the winter angle longer.",
            },
        ),
        "pv": (
            "PV comparison (optional)",
            {"pv_power_entity": "PV power sensor", "pv_peak_power": "PV peak power"},
            {
                "pv_peak_power": "Peak power of the panels on this mount, for the actual-vs-model sensor."
            },
        ),
    },
    "nl": {
        "mapping_feedback": (
            "Actuator-omrekening en terugkoppeling",
            {
                "mapping": "Omrekening",
                "position_at_min": "Positie bij minimale hoek",
                "position_at_max": "Positie bij maximale hoek",
                "calibration": "Kalibratietabel",
                "feedback_entity": "Terugkoppelsensor",
                "feedback_kind": "Terugkoppeling meldt",
                "travel_time": "Looptijd volledige slag",
            },
            {
                "position_at_min": "Wissel de twee posities om de actuator om te keren.",
                "calibration": "hoek:positie paren, bijv. 0:0, 15:22, 30:47, 45:75, 60:100",
                "feedback_entity": "Optioneel. Zonder sensor wordt de coverpositie gebruikt, of een schatting op basis van de looptijd.",
                "travel_time": "Seconden van minimum naar maximum. Voor schattingen en de vastloopcontrole.",
            },
        ),
        "positions": (
            "Posities en seizoenscurve",
            {
                "stow_angle": "Veilige stand (wind/storm)",
                "night_angle": "Nachtstand",
                "diffuse_angle": "Bewolkt (diffuus)",
                "snow_angle": "Sneeuw-afglijhoek",
                "rain_angle": "Hoek bij zware regen",
                "frost_angle": "Hoek bij vorst",
                "winter_angle": "Winterhoek",
                "summer_angle": "Zomerhoek",
                "season_weight": "Seizoensweging",
            },
            {
                "stow_angle": "Laagste windbelasting voor je constructie, meestal plat.",
                "season_weight": "Seizoensstrategie: 50 is een gewone cosinus, hoger blijft langer op de winterhoek.",
            },
        ),
        "pv": (
            "PV-vergelijking (optioneel)",
            {
                "pv_power_entity": "PV-vermogenssensor",
                "pv_peak_power": "PV-piekvermogen",
            },
            {
                "pv_peak_power": "Piekvermogen van de panelen op deze constructie, voor de sensor werkelijk-vs-model."
            },
        ),
    },
}
THRESH = {
    "en": {
        "wind_stow_speed": "Stow at wind speed",
        "wind_resume_speed": "Resume below wind speed",
        "calm_minutes": "Calm time before resuming",
        "storm_speed": "Storm mode at wind speed",
        "storm_hold_hours": "Storm mode hold time",
        "stale_minutes": "Wind data is stale after",
        "snow_mode": "Snow shedding position",
        "rain_mode": "Heavy rain position",
        "frost_mode": "Frost position",
        "frost_temperature": "Frost below temperature",
        "cloud_threshold": "Diffuse mode above cloud cover",
        "min_move_interval": "Minimum time between moves",
        "manual_pause": "Pause after a manual move",
        "deadband": "Deadband",
        "hysteresis": "Hysteresis",
    },
    "nl": {
        "wind_stow_speed": "Veilige stand bij windsnelheid",
        "wind_resume_speed": "Hervatten onder windsnelheid",
        "calm_minutes": "Rustige tijd voor hervatten",
        "storm_speed": "Stormmodus bij windsnelheid",
        "storm_hold_hours": "Duur stormmodus",
        "stale_minutes": "Winddata verouderd na",
        "snow_mode": "Sneeuw-afglijstand",
        "rain_mode": "Stand bij zware regen",
        "frost_mode": "Stand bij vorst",
        "frost_temperature": "Vorst onder temperatuur",
        "cloud_threshold": "Diffuse modus boven bewolking",
        "min_move_interval": "Minimale tijd tussen bewegingen",
        "manual_pause": "Pauze na handmatige beweging",
        "deadband": "Dode zone",
        "hysteresis": "Hysterese",
    },
}
THRESH_DESC = {
    "en": {
        "storm_hold_hours": "Storm mode stays on this long after the last strong wind. 0 = until you resume by hand.",
        "stale_minutes": "Without fresh wind data panels freeze (or stay stowed if it was windy).",
        "cloud_threshold": "Tracking strategy only: above this cloud cover the panel goes to the diffuse angle.",
        "min_move_interval": "Safety moves ignore this.",
        "deadband": "Smaller angle changes are skipped.",
        "hysteresis": "Extra margin before a rounded target changes step.",
    },
    "nl": {
        "storm_hold_hours": "Stormmodus blijft zo lang aan na de laatste harde wind. 0 = tot je handmatig hervat.",
        "stale_minutes": "Zonder verse winddata bevriezen de panelen (of blijven ze veilig als het hard waaide).",
        "cloud_threshold": "Alleen bij volgen: boven deze bewolking gaat het paneel naar de diffuse hoek.",
        "min_move_interval": "Veiligheidsbewegingen negeren dit.",
        "deadband": "Kleinere hoekveranderingen worden overgeslagen.",
        "hysteresis": "Extra marge voordat een afgeronde doelhoek een stap verspringt.",
    },
}
ERRORS = {
    "en": {
        "wind_source_required": "Choose a weather entity or a wind speed sensor: wind protection needs one.",
        "max_below_min": "The maximum angle must be above the minimum angle.",
        "tilt_range": "A tilt axis works between 0 and 90 degrees. Use the roll axis for negative angles.",
        "calibration_required": "Enter a calibration table or choose linear mapping.",
        "invalid_mapping": "The mapping can't be used. Table: at least two angle:position pairs, positions rising (or falling) with the angle. Linear: the two positions must differ.",
        "actuator_in_use": "This actuator already drives another panel.",
        "resume_above_stow": "The resume speed must be below the stow speed.",
        "storm_below_stow": "The storm speed must be at least the stow speed.",
    },
    "nl": {
        "wind_source_required": "Kies een weer-entiteit of een windsnelheidssensor: windbeveiliging heeft er een nodig.",
        "max_below_min": "De maximale hoek moet boven de minimale hoek liggen.",
        "tilt_range": "Een kantelas werkt tussen 0 en 90 graden. Gebruik de rol-as voor negatieve hoeken.",
        "calibration_required": "Vul een kalibratietabel in of kies lineaire omrekening.",
        "invalid_mapping": "De omrekening is onbruikbaar. Tabel: minstens twee hoek:positie paren, posities stijgend (of dalend) met de hoek. Lineair: de twee posities moeten verschillen.",
        "actuator_in_use": "Deze actuator stuurt al een ander paneel aan.",
        "resume_above_stow": "De hervatsnelheid moet onder de veilige-standsnelheid liggen.",
        "storm_below_stow": "De stormsnelheid moet minstens de veilige-standsnelheid zijn.",
    },
}
REASONS = {
    "en": {
        "strategy": "Strategy",
        "night": "Night park",
        "diffuse": "Cloudy",
        "manual": "Manual",
        "wind": "Wind stow",
        "storm": "Storm mode",
        "stow": "Stowed",
        "snow": "Snow",
        "rain": "Heavy rain",
        "frost": "Frost",
        "calibrate": "Calibration",
    },
    "nl": {
        "strategy": "Strategie",
        "night": "Nachtstand",
        "diffuse": "Bewolkt",
        "manual": "Handmatig",
        "wind": "Wind: veilige stand",
        "storm": "Stormmodus",
        "stow": "Veilige stand",
        "snow": "Sneeuw",
        "rain": "Zware regen",
        "frost": "Vorst",
        "calibrate": "Kalibratie",
    },
}
STRATEGY = {
    "en": {
        "fixed": "Fixed (annual optimum)",
        "seasonal": "Seasonal curve",
        "daily": "Daily optimum",
        "tracking": "Sun tracking",
    },
    "nl": {
        "fixed": "Vast (jaaroptimum)",
        "seasonal": "Seizoenscurve",
        "daily": "Dagoptimum",
        "tracking": "Zon volgen",
    },
}
MODE = {
    "en": {"auto": "Automatic", "manual": "Manual", **STRATEGY["en"]},
    "nl": {"auto": "Automatisch", "manual": "Handmatig", **STRATEGY["nl"]},
}
T = {
    "en": {
        "site_title": "Helios Tilt site",
        "site_desc": "Where the panels are and where the wind comes from. Panels are added in the next step.",
        "panel_title": "First panel",
        "panel_desc": "One mount driven by one actuator. Add more panels later from the integration page.",
        "reconf_title": "Location and weather",
        "add_panel": "Add panel",
        "panel_type": "Panel",
        "panel_user_title": "Add a panel",
        "panel_reconf_title": "Change panel",
        "opt_title": "Safety and timing",
        "opt_desc": "Wind speeds are in km/h whatever unit your sensors report. Priority is always safety, then manual, then automatic.",
        "already": "This site is already set up.",
        "reconf_ok": "Saved.",
        "entities": {
            "sensor": {
                "target_angle": "Target angle",
                "current_angle": "Current angle",
                "last_move": "Last move",
                "moves_today": "Moves today",
                "gain": "Estimated gain",
                "pv_performance": "PV actual vs model",
            },
            "select": "Mode",
            "number": "Manual angle",
            "switch": "Automatic control",
            "binary_sensor": {"storm": "Storm mode", "wind_stow": "Wind stow"},
        },
        "selectors": {
            "axis": {
                "tilt": "Tilt (faces the azimuth)",
                "roll": "Roll (single-axis tracker)",
            },
            "mapping": {"linear": "Linear", "table": "Calibration table"},
            "feedback_kind": {
                "position": "Actuator position",
                "angle": "Panel angle (degrees)",
            },
        },
        "services": {
            "set_tilt": (
                "Set tilt",
                "Move panels to an angle and switch them to manual mode.",
                {
                    "angle": (
                        "Angle",
                        "Panel angle in degrees (clamped to the soft limits).",
                    )
                },
            ),
            "stow": (
                "Stow",
                "Move panels to their stow angle and keep them there until resumed.",
                {"storm": ("Storm mode", "Also latch storm mode for the whole site.")},
            ),
            "resume_auto": (
                "Resume automatic",
                "Clear stow, manual mode, the manual pause and storm mode.",
                {},
            ),
            "set_mode": (
                "Set mode",
                "Automatic, manual, or force a strategy.",
                {"mode": ("Mode", "The new mode.")},
            ),
            "calibrate": (
                "Calibrate",
                "Tell Helios the panel's real angle (for actuators without feedback).",
                {"angle": ("Angle", "The measured panel angle.")},
            ),
        },
        "exceptions": {
            "not_loaded": "Helios Tilt is not loaded.",
            "target_required": "Choose the panel to calibrate.",
            "not_a_panel": "{target} is not a Helios Tilt panel.",
        },
        "issue_title": "{panel}: actuator did not reach its angle",
        "issue_desc": "{entity} was told to go to {target}\u00b0 but reports {current}\u00b0. Check the actuator, its power and its end stops. The warning clears by itself once the panel reaches its target.",
    },
    "nl": {
        "site_title": "Helios Tilt-locatie",
        "site_desc": "Waar de panelen staan en waar de windinformatie vandaan komt. Panelen voeg je in de volgende stap toe.",
        "panel_title": "Eerste paneel",
        "panel_desc": "Een constructie met een actuator. Meer panelen voeg je later toe via de integratiepagina.",
        "reconf_title": "Locatie en weer",
        "add_panel": "Paneel toevoegen",
        "panel_type": "Paneel",
        "panel_user_title": "Paneel toevoegen",
        "panel_reconf_title": "Paneel wijzigen",
        "opt_title": "Veiligheid en timing",
        "opt_desc": "Windsnelheden zijn in km/u, welke eenheid je sensoren ook gebruiken. Volgorde is altijd: veiligheid, dan handmatig, dan automatisch.",
        "already": "Deze locatie is al ingesteld.",
        "reconf_ok": "Opgeslagen.",
        "entities": {
            "sensor": {
                "target_angle": "Doelhoek",
                "current_angle": "Huidige hoek",
                "last_move": "Laatste beweging",
                "moves_today": "Bewegingen vandaag",
                "gain": "Geschatte winst",
                "pv_performance": "PV werkelijk vs model",
            },
            "select": "Modus",
            "number": "Handmatige hoek",
            "switch": "Automatische besturing",
            "binary_sensor": {
                "storm": "Stormmodus",
                "wind_stow": "Wind: veilige stand",
            },
        },
        "selectors": {
            "axis": {
                "tilt": "Kantelen (kijkt naar de azimut)",
                "roll": "Rollen (eenassige tracker)",
            },
            "mapping": {"linear": "Lineair", "table": "Kalibratietabel"},
            "feedback_kind": {
                "position": "Actuatorpositie",
                "angle": "Paneelhoek (graden)",
            },
        },
        "services": {
            "set_tilt": (
                "Hoek instellen",
                "Zet panelen op een hoek en schakel ze naar handmatig.",
                {
                    "angle": (
                        "Hoek",
                        "Paneelhoek in graden (begrensd door de zachte grenzen).",
                    )
                },
            ),
            "stow": (
                "Veilige stand",
                "Zet panelen in de veilige stand tot je hervat.",
                {
                    "storm": (
                        "Stormmodus",
                        "Zet ook stormmodus aan voor de hele locatie.",
                    )
                },
            ),
            "resume_auto": (
                "Automatisch hervatten",
                "Wist veilige stand, handmatige modus, de pauze en stormmodus.",
                {},
            ),
            "set_mode": (
                "Modus instellen",
                "Automatisch, handmatig of een vaste strategie.",
                {"mode": ("Modus", "De nieuwe modus.")},
            ),
            "calibrate": (
                "Kalibreren",
                "Geef Helios de echte paneelhoek door (voor actuatoren zonder terugkoppeling).",
                {"angle": ("Hoek", "De gemeten paneelhoek.")},
            ),
        },
        "exceptions": {
            "not_loaded": "Helios Tilt is niet geladen.",
            "target_required": "Kies het paneel om te kalibreren.",
            "not_a_panel": "{target} is geen Helios Tilt-paneel.",
        },
        "issue_title": "{panel}: actuator bereikte de hoek niet",
        "issue_desc": "{entity} moest naar {target}\u00b0 maar meldt {current}\u00b0. Controleer de actuator, de voeding en de eindstops. De melding verdwijnt vanzelf zodra het paneel zijn doel bereikt.",
    },
}


def panel_step(lang: str, title: str, desc: str | None) -> dict:
    step = {
        "title": title,
        "data": PANEL[lang],
        "data_description": PANEL_DESC[lang],
        "sections": {
            key: {"name": name, "data": data, "data_description": dd}
            for key, (name, data, dd) in SECTIONS[lang].items()
        },
    }
    if desc:
        step["description"] = desc
    return step


def build(lang: str) -> dict:
    t = T[lang]
    site_data = SITE[lang]
    reconf_data = {k: v for k, v in site_data.items() if k != "name"}
    ent = t["entities"]
    return {
        "config": {
            "step": {
                "user": {
                    "title": t["site_title"],
                    "description": t["site_desc"],
                    "data": site_data,
                    "data_description": SITE_DESC[lang],
                },
                "panel": panel_step(lang, t["panel_title"], t["panel_desc"]),
                "reconfigure": {
                    "title": t["reconf_title"],
                    "data": reconf_data,
                    "data_description": SITE_DESC[lang],
                },
            },
            "error": ERRORS[lang],
            "abort": {
                "already_configured": t["already"],
                "reconfigure_successful": t["reconf_ok"],
            },
        },
        "config_subentries": {
            "panel": {
                "initiate_flow": {"user": t["add_panel"]},
                "entry_type": t["panel_type"],
                "step": {
                    "user": panel_step(lang, t["panel_user_title"], None),
                    "reconfigure": panel_step(lang, t["panel_reconf_title"], None),
                },
                "error": ERRORS[lang],
                "abort": {"reconfigure_successful": t["reconf_ok"]},
            }
        },
        "options": {
            "step": {
                "init": {
                    "title": t["opt_title"],
                    "description": t["opt_desc"],
                    "data": THRESH[lang],
                    "data_description": THRESH_DESC[lang],
                }
            },
            "error": ERRORS[lang],
        },
        "entity": {
            "sensor": {
                **{
                    k: {"name": v} for k, v in ent["sensor"].items() if k != "last_move"
                },
                "last_move": {
                    "name": ent["sensor"]["last_move"],
                    "state": REASONS[lang],
                },
            },
            "select": {"mode": {"name": ent["select"], "state": MODE[lang]}},
            "number": {"manual_angle": {"name": ent["number"]}},
            "switch": {"auto": {"name": ent["switch"]}},
            "binary_sensor": {k: {"name": v} for k, v in ent["binary_sensor"].items()},
        },
        "selector": {
            "axis": {"options": t["selectors"]["axis"]},
            "strategy": {"options": STRATEGY[lang]},
            "mapping": {"options": t["selectors"]["mapping"]},
            "feedback_kind": {"options": t["selectors"]["feedback_kind"]},
            "mode": {"options": MODE[lang]},
        },
        "services": {
            key: {
                "name": name,
                "description": desc,
                **(
                    {
                        "fields": {
                            f: {"name": n, "description": d}
                            for f, (n, d) in flds.items()
                        }
                    }
                    if flds
                    else {}
                ),
            }
            for key, (name, desc, flds) in t["services"].items()
        },
        "exceptions": {k: {"message": v} for k, v in t["exceptions"].items()},
        "issues": {
            "actuator_stuck": {
                "title": t["issue_title"],
                "description": t["issue_desc"],
            }
        },
    }


for lang in ("en", "nl"):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{lang}.json").write_text(
        json.dumps(build(lang), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
print("ok")
