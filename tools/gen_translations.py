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

# ---- two relays (timed) -------------------------------------------------------
PANEL["en"]["actuator_type"] = "Actuator type"
PANEL["nl"]["actuator_type"] = "Type actuator"
PANEL_DESC["en"]["actuator_type"] = (
    "An existing entity (cover, number or script), or two relays (open + close) driving a dumb actuator by time."
)
PANEL_DESC["nl"]["actuator_type"] = (
    "Een bestaande entiteit (cover, number of script), of twee relais (open + dicht) die een domme actuator op tijd aansturen."
)
SECTIONS["en"] = {
    "relays": (
        "Two relays (timed)",
        {
            "open_switch": "Open relay (extends)",
            "close_switch": "Close relay (retracts)",
            "open_countdown": "Open relay countdown",
            "close_countdown": "Close relay countdown",
            "open_time": "Full open time",
            "close_time": "Full close time",
            "angle_closed": "Panel angle when fully closed",
            "angle_open": "Panel angle when fully open",
            "start_delay": "Start delay",
            "home_overrun": "Homing overrun",
            "reverse_delay": "Direction change pause",
            "home_after_moves": "Home after this many moves",
            "home_at_night": "Home at the night park",
            "home_end": "Home against",
        },
        {
            "open_switch": "Switch that makes the actuator extend (Zigbee2MQTT: switch.NAME_l1). The actuator must have its own limit switches.",
            "close_switch": "Switch that makes it retract (switch.NAME_l2). Never both on: Helios switches the other one off first.",
            "open_countdown": "Optional, e.g. number.NAME_countdown_l1. Set for every run as a hardware fail-safe: the relay switches itself off even if Home Assistant stops.",
            "close_countdown": "Optional, e.g. number.NAME_countdown_l2.",
            "open_time": "Seconds from fully closed to fully open. Measure it with Reconfigure > Time the travel.",
            "close_time": "Seconds from fully open to fully closed (often different).",
            "angle_closed": "Measure the panel (or window) angle at both ends; the stroke is mapped linearly in between, or use a calibration table of angle:stroke% pairs.",
            "start_delay": "Seconds the motor needs before it moves. Usually 0.",
            "home_overrun": "Runs to an end stop keep going this % of the travel time longer, so the estimate re-syncs.",
            "reverse_delay": "Pause after a run before going the other way.",
            "home_after_moves": "Drift builds up with every move; home again after this many moves (0 = only when needed).",
            "home_at_night": "Drive into the home end stop before the night park.",
        },
    ),
    **SECTIONS["en"],
}
SECTIONS["en"]["mapping_feedback"][2]["calibration"] = (
    "angle:position pairs, e.g. 0:0, 15:22, 30:47, 45:75, 60:100. Two relays: angle:stroke% (0 = fully closed)."
)
SECTIONS["nl"] = {
    "relays": (
        "Twee relais (op tijd)",
        {
            "open_switch": "Open-relais (uitschuiven)",
            "close_switch": "Dicht-relais (intrekken)",
            "open_countdown": "Afteltijd open-relais",
            "close_countdown": "Afteltijd dicht-relais",
            "open_time": "Looptijd volledig open",
            "close_time": "Looptijd volledig dicht",
            "angle_closed": "Paneelhoek volledig dicht",
            "angle_open": "Paneelhoek volledig open",
            "start_delay": "Startvertraging",
            "home_overrun": "Doorloop bij homen",
            "reverse_delay": "Pauze bij richtingwissel",
            "home_after_moves": "Homen na zoveel bewegingen",
            "home_at_night": "Homen bij de nachtstand",
            "home_end": "Homen tegen",
        },
        {
            "open_switch": "Schakelaar waarmee de actuator uitschuift (Zigbee2MQTT: switch.NAAM_l1). De actuator moet eigen eindschakelaars hebben.",
            "close_switch": "Schakelaar waarmee hij intrekt (switch.NAAM_l2). Nooit allebei aan: Helios zet eerst de andere uit.",
            "open_countdown": "Optioneel, bijv. number.NAAM_countdown_l1. Wordt bij elke beweging gezet als hardwarebeveiliging: het relais schakelt zelf uit, ook als Home Assistant stopt.",
            "close_countdown": "Optioneel, bijv. number.NAAM_countdown_l2.",
            "open_time": "Seconden van volledig dicht naar volledig open. Meet het via Opnieuw configureren > Looptijd meten.",
            "close_time": "Seconden van volledig open naar volledig dicht (vaak anders).",
            "angle_closed": "Meet de hoek van het paneel (of raam) aan beide uiteinden; de slag wordt daartussen lineair omgerekend, of gebruik een kalibratietabel met hoek:slag%-paren.",
            "start_delay": "Seconden die de motor nodig heeft voor hij beweegt. Meestal 0.",
            "home_overrun": "Bewegingen naar een eindstop lopen zoveel % van de looptijd langer door, zodat de schatting weer klopt.",
            "reverse_delay": "Pauze na een beweging voordat de andere kant op wordt gestuurd.",
            "home_after_moves": "Bij elke beweging groeit de afwijking; na zoveel bewegingen opnieuw homen (0 = alleen als het nodig is).",
            "home_at_night": "Voor de nachtstand eerst tegen de home-eindstop rijden.",
        },
    ),
    **SECTIONS["nl"],
}
SECTIONS["nl"]["mapping_feedback"][2]["calibration"] = (
    "hoek:positie paren, bijv. 0:0, 15:22, 30:47, 45:75, 60:100. Twee relais: hoek:slag% (0 = volledig dicht)."
)
ERRORS["en"].update(
    {
        "actuator_required": "Choose the actuator entity, or pick the two relays type.",
        "relays_required": "Choose both the open and the close relay.",
        "same_relay": "The open and close relay must be different switches.",
        "same_countdown": "The two countdowns must be different entities.",
        "same_end_angles": "The angles at fully closed and fully open must differ.",
        "limits_outside_stroke": "The minimum and maximum angle must lie between the angles at fully closed and fully open.",
        "still_homing": "Still closing. Wait until it has closed fully and starts to open, then submit when it reaches the open end.",
        "calibration_failed": "The calibration stopped (a relay did not respond, or it took too long). Both relays are off.",
    }
)
ERRORS["nl"].update(
    {
        "actuator_required": "Kies de actuator-entiteit, of kies het type twee relais.",
        "relays_required": "Kies zowel het open- als het dicht-relais.",
        "same_relay": "Het open- en dicht-relais moeten verschillende schakelaars zijn.",
        "same_countdown": "De twee afteltijden moeten verschillende entiteiten zijn.",
        "same_end_angles": "De hoeken bij volledig dicht en volledig open moeten verschillen.",
        "limits_outside_stroke": "De minimale en maximale hoek moeten tussen de hoeken bij volledig dicht en volledig open liggen.",
        "still_homing": "Nog aan het sluiten. Wacht tot hij helemaal dicht is en begint te openen, en bevestig als hij het open eind bereikt.",
        "calibration_failed": "De kalibratie is gestopt (een relais reageerde niet, of het duurde te lang). Beide relais zijn uit.",
    }
)
TRAVEL = {
    "en": {
        "menu_title": "Change panel",
        "menu": {"settings": "Settings", "travel": "Time the travel (calibrate)"},
        "travel": (
            "Time the travel: {panel}",
            "Keep the actuator in sight and stay clear of it. On submit it first closes fully (homing) for the time below, then starts opening. On the next screen, submit the moment it reaches the fully open end.",
            {"homing_seconds": "Homing time"},
            {
                "homing_seconds": "Long enough to close fully from anywhere, plus a margin."
            },
        ),
        "travel_open": (
            "Opening...",
            "It closes first, then opens. Submit the moment it stops at the fully open end.",
        ),
        "travel_close": (
            "Closing...",
            "Now it closes. Submit the moment it stops at the fully closed end.",
        ),
        "travel_result": (
            "Measured travel",
            "Check the measured times and enter the panel angle at both ends.",
            {
                "open_time": "Full open time",
                "close_time": "Full close time",
                "angle_closed": "Panel angle when fully closed",
                "angle_open": "Panel angle when fully open",
            },
        ),
        "not_loaded": "Load the integration first.",
        "calibration_failed": "The calibration stopped (a relay did not respond, or it took too long). Both relays are off.",
    },
    "nl": {
        "menu_title": "Paneel wijzigen",
        "menu": {"settings": "Instellingen", "travel": "Looptijd meten (kalibreren)"},
        "travel": (
            "Looptijd meten: {panel}",
            "Houd de actuator in het zicht en blijf er uit de buurt. Na bevestigen sluit hij eerst volledig (homen) gedurende de tijd hieronder, daarna begint hij te openen. Bevestig op het volgende scherm zodra hij het volledig open eind bereikt.",
            {"homing_seconds": "Home-tijd"},
            {
                "homing_seconds": "Lang genoeg om vanaf elke stand helemaal te sluiten, plus marge."
            },
        ),
        "travel_open": (
            "Openen...",
            "Eerst sluit hij, dan opent hij. Bevestig zodra hij stopt op het volledig open eind.",
        ),
        "travel_close": (
            "Sluiten...",
            "Nu sluit hij. Bevestig zodra hij stopt op het volledig dichte eind.",
        ),
        "travel_result": (
            "Gemeten looptijd",
            "Controleer de gemeten tijden en vul de paneelhoek aan beide uiteinden in.",
            {
                "open_time": "Looptijd volledig open",
                "close_time": "Looptijd volledig dicht",
                "angle_closed": "Paneelhoek volledig dicht",
                "angle_open": "Paneelhoek volledig open",
            },
        ),
        "not_loaded": "Laad eerst de integratie.",
        "calibration_failed": "De kalibratie is gestopt (een relais reageerde niet, of het duurde te lang). Beide relais zijn uit.",
    },
}
RELAY_T = {
    "en": {
        "binary_sensor": {"position_uncertain": "Position uncertain"},
        "button": {
            "home": "Home now",
            "travel_start": "Travel calibration: start",
            "travel_mark": "Travel calibration: end reached",
            "travel_cancel": "Travel calibration: cancel",
        },
        "selectors": {
            "actuator_type": {
                "entity": "Entity (cover, number or script)",
                "relays": "Two relays (timed)",
            },
            "home_end": {
                "closed": "Fully closed",
                "open": "Fully open",
                "nearest": "Nearest end",
            },
            "travel_action": {
                "start": "Start (close fully, then open)",
                "stop": "End reached",
                "cancel": "Cancel",
            },
        },
        "services": {
            "home": (
                "Home now",
                "Panels on two relays: drive into the home end stop to re-sync the estimate, then back to the target.",
                {},
            ),
            "calibrate_travel": (
                "Time the travel",
                "Panels on two relays: start closes fully, then opens; call stop when it reaches the open end, and again at the closed end. The times are saved.",
                {
                    "action": ("Action", "start, stop (end reached) or cancel."),
                    "homing_seconds": (
                        "Homing time",
                        "How long to close first. Default: the maximum run time.",
                    ),
                },
            ),
        },
        "not_relays": "Choose a panel driven by two relays.",
        "fault_title": "{panel}: relay problem",
        "fault_desc": "{fault}. Both relays were switched off and the position is marked uncertain; the next move homes first. Check the relay device, its Zigbee link and the wiring. This clears after the next successful move.",
    },
    "nl": {
        "binary_sensor": {"position_uncertain": "Positie onzeker"},
        "button": {
            "home": "Nu homen",
            "travel_start": "Looptijd meten: start",
            "travel_mark": "Looptijd meten: eind bereikt",
            "travel_cancel": "Looptijd meten: annuleren",
        },
        "selectors": {
            "actuator_type": {
                "entity": "Entiteit (cover, number of script)",
                "relays": "Twee relais (op tijd)",
            },
            "home_end": {
                "closed": "Volledig dicht",
                "open": "Volledig open",
                "nearest": "Dichtstbijzijnde eind",
            },
            "travel_action": {
                "start": "Start (helemaal dicht, dan open)",
                "stop": "Eind bereikt",
                "cancel": "Annuleren",
            },
        },
        "services": {
            "home": (
                "Nu homen",
                "Panelen op twee relais: rij tegen de home-eindstop om de schatting gelijk te zetten, dan terug naar het doel.",
                {},
            ),
            "calibrate_travel": (
                "Looptijd meten",
                "Panelen op twee relais: start sluit volledig en opent dan; roep stop aan bij het open eind, en nog eens bij het dichte eind. De tijden worden opgeslagen.",
                {
                    "action": ("Actie", "start, stop (eind bereikt) of cancel."),
                    "homing_seconds": (
                        "Home-tijd",
                        "Hoe lang eerst te sluiten. Standaard: de maximale looptijd.",
                    ),
                },
            ),
        },
        "not_relays": "Kies een paneel dat met twee relais wordt aangestuurd.",
        "fault_title": "{panel}: probleem met een relais",
        "fault_desc": "{fault}. Beide relais zijn uitgeschakeld en de positie is als onzeker gemarkeerd; de volgende beweging homet eerst. Controleer het relaisapparaat, de Zigbee-verbinding en de bedrading. De melding verdwijnt na de volgende geslaagde beweging.",
    },
}
for _lang in ("en", "nl"):
    T[_lang]["entities"]["binary_sensor"].update(RELAY_T[_lang]["binary_sensor"])
    T[_lang]["services"].update(RELAY_T[_lang]["services"])
    T[_lang]["exceptions"]["not_relays"] = RELAY_T[_lang]["not_relays"]


GEOMETRY = ("axis", "azimuth", "min_angle", "max_angle", "step", "strategy")
RELAY_MAIN = (
    "open_switch",
    "close_switch",
    "open_countdown",
    "close_countdown",
    "open_time",
    "close_time",
    "angle_closed",
    "angle_open",
)
RELAY_ADVANCED = (
    "start_delay",
    "home_overrun",
    "reverse_delay",
    "home_after_moves",
    "home_at_night",
    "home_end",
    "mapping",
    "calibration",
)
POSITIONS = (
    "stow_angle",
    "night_angle",
    "diffuse_angle",
    "snow_angle",
    "rain_angle",
    "frost_angle",
    "winter_angle",
    "summer_angle",
    "season_weight",
)
STEPS = {
    "en": {
        "first_title": "First panel",
        "first_desc": "One mount driven by one actuator. Name it and choose how it is driven; the next step asks only for that type's settings. Add more panels later from the integration page.",
        "add_title": "Add a panel",
        "add_desc": "Name the panel and choose how it is driven. The next step asks only for that type's settings.",
        "change_title": "Change panel",
        "change_desc": "Changing the actuator type starts that type's settings from the defaults.",
        "entity_title": "{name}: actuator entity",
        "entity_desc": "The entity Helios commands, the panel geometry, and how actuator positions map to panel angles.",
        "mapping_section": "Mapping and feedback",
        "relays_title": "{name}: two relays (timed)",
        "relays_desc": "The open and close relay, their countdowns as a hardware fail-safe, the full travel times and the panel angle at both ends. The minimum and maximum angle must lie between the two end angles.",
        "advanced_section": "Homing, timing and stroke table",
        "positions_title": "{name}: positions",
        "positions_desc": "Every angle here is kept between the soft limits, {min}\u00b0 and {max}\u00b0: the panel never goes beyond a limit. Suggested seasonal angles for latitude {latitude}\u00b0: winter {winter}\u00b0, summer {summer}\u00b0 (about latitude + 15 and latitude - 35, within the limits).",
        "clamp": "Kept between the soft limits, {min}\u00b0 to {max}\u00b0.",
        "winter": "Seasonal strategy, at the winter solstice. Steeper than summer: about latitude + 15.",
        "summer": "Seasonal strategy, at the summer solstice: about latitude - 35. Equal to winter means a flat curve.",
        "calibration_relays": "With a calibration table: angle:stroke% pairs (0 = fully closed), e.g. 10:0, 20:40, 30:75, 40:100.",
        "mapping_relays": "Linear maps the stroke between the two end angles. A table is for non-linear mounts.",
    },
    "nl": {
        "first_title": "Eerste paneel",
        "first_desc": "Een constructie met een actuator. Geef het een naam en kies hoe het wordt aangestuurd; de volgende stap vraagt alleen de instellingen voor dat type. Meer panelen voeg je later toe via de integratiepagina.",
        "add_title": "Paneel toevoegen",
        "add_desc": "Geef het paneel een naam en kies hoe het wordt aangestuurd. De volgende stap vraagt alleen de instellingen voor dat type.",
        "change_title": "Paneel wijzigen",
        "change_desc": "Wissel je van type actuator, dan beginnen de instellingen van dat type bij de standaardwaarden.",
        "entity_title": "{name}: actuator-entiteit",
        "entity_desc": "De entiteit die Helios aanstuurt, de paneelgeometrie en hoe actuatorposities naar paneelhoeken worden omgerekend.",
        "mapping_section": "Omrekening en terugkoppeling",
        "relays_title": "{name}: twee relais (op tijd)",
        "relays_desc": "Het open- en dicht-relais, hun afteltijden als hardwarebeveiliging, de volledige looptijden en de paneelhoek aan beide uiteinden. De minimale en maximale hoek moeten tussen de twee eindhoeken liggen.",
        "advanced_section": "Homen, timing en slagtabel",
        "positions_title": "{name}: posities",
        "positions_desc": "Elke hoek hier blijft tussen de zachte grenzen, {min}\u00b0 en {max}\u00b0: het paneel gaat nooit voorbij een grens. Voorgestelde seizoenshoeken voor breedtegraad {latitude}\u00b0: winter {winter}\u00b0, zomer {summer}\u00b0 (ongeveer breedtegraad + 15 en breedtegraad - 35, binnen de grenzen).",
        "clamp": "Blijft binnen de zachte grenzen, {min}\u00b0 tot {max}\u00b0.",
        "winter": "Seizoensstrategie, bij de winterzonnewende. Steiler dan zomer: ongeveer breedtegraad + 15.",
        "summer": "Seizoensstrategie, bij de zomerzonnewende: ongeveer breedtegraad - 35. Gelijk aan winter betekent een vlakke curve.",
        "calibration_relays": "Met een kalibratietabel: hoek:slag%-paren (0 = volledig dicht), bijv. 10:0, 20:40, 30:75, 40:100.",
        "mapping_relays": "Lineair rekent de slag om tussen de twee eindhoeken. Een tabel is voor niet-lineaire constructies.",
    },
}
ERRORS["en"].update(
    {
        "outside_limits": "Outside the soft limits ({min}\u00b0 to {max}\u00b0). The panel never goes beyond a limit, so it would stop at the nearest one. Enter an angle within the limits.",
        "season_flat": "The winter and summer angles are equal, so the seasonal curve is flat. Suggested for latitude {latitude}\u00b0: winter {winter}\u00b0, summer {summer}\u00b0. Submit again to keep them equal.",
    }
)
ERRORS["nl"].update(
    {
        "outside_limits": "Buiten de zachte grenzen ({min}\u00b0 tot {max}\u00b0). Het paneel gaat nooit voorbij een grens en zou bij de dichtstbijzijnde stoppen. Vul een hoek binnen de grenzen in.",
        "season_flat": "De winter- en zomerhoek zijn gelijk, dus de seizoenscurve is vlak. Voorstel voor breedtegraad {latitude}\u00b0: winter {winter}\u00b0, zomer {summer}\u00b0. Bevestig opnieuw om ze gelijk te houden.",
    }
)


def _labels(lang: str) -> tuple[dict, dict]:
    data = dict(PANEL[lang])
    desc = dict(PANEL_DESC[lang])
    for _name, d, dd in SECTIONS[lang].values():
        data.update(d)
        desc.update(dd)
    return data, desc


def _pick(src: dict, keys) -> dict:
    return {k: src[k] for k in keys if k in src}


def type_step(lang: str, title: str, desc: str) -> dict:
    data, dd = _labels(lang)
    keys = ("name", "actuator_type")
    return {
        "title": title,
        "description": desc,
        "data": _pick(data, keys),
        "data_description": _pick(dd, keys),
    }


def panel_steps(lang: str) -> dict:
    """Steps 2 and 3, the same in every flow."""
    st = STEPS[lang]
    data, dd = _labels(lang)
    relay_dd = {
        **dd,
        "mapping": st["mapping_relays"],
        "calibration": st["calibration_relays"],
    }
    pos_dd = {
        **{k: (dd.get(k, "") + " " + st["clamp"]).strip() for k in POSITIONS[:6]},
        "winter_angle": st["winter"],
        "summer_angle": st["summer"],
        "season_weight": dd["season_weight"],
    }
    pv = SECTIONS[lang]["pv"]
    entity_main = ("actuator_entity", *GEOMETRY)
    mapping = SECTIONS[lang]["mapping_feedback"]
    return {
        "entity": {
            "title": st["entity_title"],
            "description": st["entity_desc"],
            "data": _pick(data, entity_main),
            "data_description": _pick(dd, entity_main),
            "sections": {
                "mapping_feedback": {
                    "name": st["mapping_section"],
                    "data": mapping[1],
                    "data_description": mapping[2],
                }
            },
        },
        "relays": {
            "title": st["relays_title"],
            "description": st["relays_desc"],
            "data": _pick(data, (*RELAY_MAIN, *GEOMETRY)),
            "data_description": _pick(relay_dd, (*RELAY_MAIN, *GEOMETRY)),
            "sections": {
                "relay_advanced": {
                    "name": st["advanced_section"],
                    "data": _pick(data, RELAY_ADVANCED),
                    "data_description": _pick(relay_dd, RELAY_ADVANCED),
                }
            },
        },
        "positions": {
            "title": st["positions_title"],
            "description": st["positions_desc"],
            "data": _pick(data, POSITIONS),
            "data_description": pos_dd,
            "sections": {
                "pv": {"name": pv[0], "data": pv[1], "data_description": pv[2]}
            },
        },
    }


def build(lang: str) -> dict:
    t = T[lang]
    site_data = SITE[lang]
    reconf_data = {k: v for k, v in site_data.items() if k != "name"}
    ent = t["entities"]
    tr = TRAVEL[lang]
    rt = RELAY_T[lang]
    return {
        "config": {
            "step": {
                "user": {
                    "title": t["site_title"],
                    "description": t["site_desc"],
                    "data": site_data,
                    "data_description": SITE_DESC[lang],
                },
                "panel": type_step(
                    lang, STEPS[lang]["first_title"], STEPS[lang]["first_desc"]
                ),
                **panel_steps(lang),
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
                    "user": type_step(
                        lang, STEPS[lang]["add_title"], STEPS[lang]["add_desc"]
                    ),
                    **panel_steps(lang),
                    "reconfigure": {
                        "title": tr["menu_title"],
                        "menu_options": tr["menu"],
                    },
                    "settings": type_step(
                        lang, STEPS[lang]["change_title"], STEPS[lang]["change_desc"]
                    ),
                    "travel": {
                        "title": tr["travel"][0],
                        "description": tr["travel"][1],
                        "data": tr["travel"][2],
                        "data_description": tr["travel"][3],
                    },
                    "travel_open": {
                        "title": tr["travel_open"][0],
                        "description": tr["travel_open"][1],
                    },
                    "travel_close": {
                        "title": tr["travel_close"][0],
                        "description": tr["travel_close"][1],
                    },
                    "travel_result": {
                        "title": tr["travel_result"][0],
                        "description": tr["travel_result"][1],
                        "data": tr["travel_result"][2],
                    },
                },
                "error": ERRORS[lang],
                "abort": {
                    "reconfigure_successful": t["reconf_ok"],
                    "not_loaded": tr["not_loaded"],
                    "calibration_failed": tr["calibration_failed"],
                },
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
            "button": {k: {"name": v} for k, v in rt["button"].items()},
        },
        "selector": {
            "axis": {"options": t["selectors"]["axis"]},
            "strategy": {"options": STRATEGY[lang]},
            "mapping": {"options": t["selectors"]["mapping"]},
            "feedback_kind": {"options": t["selectors"]["feedback_kind"]},
            "mode": {"options": MODE[lang]},
            **{k: {"options": v} for k, v in rt["selectors"].items()},
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
            },
            "relay_fault": {
                "title": rt["fault_title"],
                "description": rt["fault_desc"],
            },
        },
    }


for lang in ("en", "nl"):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{lang}.json").write_text(
        json.dumps(build(lang), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
print("ok")
