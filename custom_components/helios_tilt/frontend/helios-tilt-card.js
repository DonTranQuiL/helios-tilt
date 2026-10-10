// Helios Tilt card: side view of each panel with the sun, wind gauge,
// controls, today's angle plan and the last moves. Plain custom element, no
// build step. Keep this file ASCII-only (use \u escapes).
const VERSION = "0.1.0b5";
const DOMAIN = "helios_tilt";
const DEG = "\u00b0";
const DASH = "\u2013";
const DOT = "\u00b7";

const I18N = {
  en: {
    auto: "Auto", stow: "Stow", manual: "Manual", angle: "Angle", target: "Target", now: "Now",
    wind: "Wind", stow_at: "stow", storm_at: "storm", sun: "Sun", sun_down: "Sun below the horizon",
    plan: "Today's plan", moves: "Last moves", no_moves: "No moves yet", gain: "today vs fixed", gain_now: "now",
    moves_today: "moves today", not_found: "No Helios Tilt panels found. Add the integration or pick a target angle sensor.",
    unavailable: "Unavailable", failed: "Action failed",
    estimated: "estimated", uncertain: "Position uncertain", home: "Home", home_title: "Drive into the end stop to re-learn the position",
    moving_open: "opening", moving_close: "closing", calibrating: "Timing the travel", offline: "Relay offline", offline_title: "Unavailable: ",
    status: {
      storm: "Storm mode", wind: "Wind stow", stowed: "Stowed", manual: "Manual", paused: "Paused after manual move",
      off: "Auto off", startup: "Waiting for data", stale: "Holding: no wind data", night: "Night park",
      diffuse: "Cloudy: flat", snow: "Snow shedding", rain: "Heavy rain", frost: "Frost",
      fixed: "Annual optimum", seasonal: "Seasonal curve", daily: "Daily optimum", tracking: "Tracking the sun",
    },
    reasons: {
      strategy: "Strategy", night: "Night park", diffuse: "Cloudy", manual: "Manual", wind: "Wind stow",
      storm: "Storm mode", stow: "Stowed", snow: "Snow", rain: "Heavy rain", frost: "Frost", calibrate: "Calibration",
    },
    editor: {
      title: "Title", entities: "Panels (target angle sensors, empty = all)", show_wind: "Wind gauge",
      show_curve: "Today's plan", show_history: "Last moves", history_count: "Moves to show", show_controls: "Controls",
    },
  },
  nl: {
    auto: "Auto", stow: "Veilig", manual: "Handmatig", angle: "Hoek", target: "Doel", now: "Nu",
    wind: "Wind", stow_at: "veilig", storm_at: "storm", sun: "Zon", sun_down: "Zon onder de horizon",
    plan: "Plan voor vandaag", moves: "Laatste bewegingen", no_moves: "Nog geen bewegingen", gain: "vandaag t.o.v. vast", gain_now: "nu",
    moves_today: "bewegingen vandaag", not_found: "Geen Helios Tilt-panelen gevonden. Voeg de integratie toe of kies een doelhoeksensor.",
    unavailable: "Niet beschikbaar", failed: "Actie mislukt",
    estimated: "geschat", uncertain: "Positie onzeker", home: "Referentie", home_title: "Tot de eindstop rijden om de positie opnieuw te bepalen",
    moving_open: "opent", moving_close: "sluit", calibrating: "Looptijd meten", offline: "Relais offline", offline_title: "Niet beschikbaar: ",
    status: {
      storm: "Stormmodus", wind: "Wind: veilige stand", stowed: "Veilige stand", manual: "Handmatig",
      paused: "Gepauzeerd na handmatige beweging", off: "Auto uit", startup: "Wacht op data",
      stale: "Vasthouden: geen winddata", night: "Nachtstand", diffuse: "Bewolkt: plat", snow: "Sneeuw afglijden",
      rain: "Zware regen", frost: "Vorst", fixed: "Jaaroptimum", seasonal: "Seizoenscurve", daily: "Dagoptimum",
      tracking: "Volgt de zon",
    },
    reasons: {
      strategy: "Strategie", night: "Nachtstand", diffuse: "Bewolkt", manual: "Handmatig", wind: "Wind",
      storm: "Stormmodus", stow: "Veilige stand", snow: "Sneeuw", rain: "Zware regen", frost: "Vorst", calibrate: "Kalibratie",
    },
    editor: {
      title: "Titel", entities: "Panelen (doelhoeksensoren, leeg = alle)", show_wind: "Windmeter",
      show_curve: "Plan voor vandaag", show_history: "Laatste bewegingen", history_count: "Aantal bewegingen",
      show_controls: "Bediening",
    },
  },
};

// Entity keys on the panel device (translation_key -> default entity id suffix).
const RELATED = {
  current: ["sensor", "current_angle", "current_angle"],
  mode: ["select", "mode", "mode"],
  manual: ["number", "manual_angle", "manual_angle"],
  auto: ["switch", "auto", "automatic_control"],
  storm: ["binary_sensor", "storm", "storm_mode"],
  wind: ["binary_sensor", "wind_stow", "wind_stow"],
  last: ["sensor", "last_move", "last_move"],
  moves: ["sensor", "moves_today", "moves_today"],
  gain: ["sensor", "gain", "estimated_gain"],
};

const DEFAULTS = { show_wind: true, show_curve: true, show_history: true, show_controls: true, history_count: 4 };

function esc(value) {
  return String(value === undefined || value === null ? "" : value).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

function num(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function deg(value, digits = 0) {
  const n = num(value);
  return n === null ? DASH : `${n.toFixed(digits)}${DEG}`;
}

function rad(d) {
  return (d * Math.PI) / 180;
}

function minutesOf(hhmm) {
  const [h, m] = String(hhmm).split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
}

function timeOf(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** Find the panels' target angle sensors (configured, or all of them). */
function findTargets(hass, config) {
  if (Array.isArray(config.entities) && config.entities.length) return config.entities.map(String);
  if (config.entity) return [String(config.entity)];
  const reg = hass.entities || {};
  const fromRegistry = Object.values(reg)
    .filter((e) => e && e.platform === DOMAIN && e.translation_key === "target_angle")
    .map((e) => e.entity_id);
  if (fromRegistry.length) return fromRegistry.sort();
  return Object.keys(hass.states || {})
    .filter((id) => id.startsWith("sensor.") && id.endsWith("_target_angle"))
    .filter((id) => {
      const a = hass.states[id].attributes || {};
      return Array.isArray(a.today_curve) && "stow_angle" in a;
    })
    .sort();
}

/** Entity ids of the other entities on the same panel device. */
function relatedIds(hass, targetId) {
  const out = {};
  const reg = hass.entities || {};
  const entry = reg[targetId];
  if (entry && entry.device_id) {
    for (const e of Object.values(reg)) {
      if (!e || e.device_id !== entry.device_id || e.platform !== DOMAIN) continue;
      for (const [key, [domain, tk]] of Object.entries(RELATED)) {
        if (e.translation_key === tk && e.entity_id.startsWith(`${domain}.`)) out[key] = e.entity_id;
      }
    }
  }
  const base = targetId.replace(/^sensor\./, "").replace(/_target_angle$/, "");
  for (const [key, [domain, , suffix]] of Object.entries(RELATED)) {
    if (!out[key]) out[key] = `${domain}.${base}_${suffix}`;
  }
  return out;
}

function panelName(hass, targetId, state) {
  const reg = (hass.entities || {})[targetId];
  const device = reg && reg.device_id && hass.devices ? hass.devices[reg.device_id] : null;
  if (device && (device.name_by_user || device.name)) return device.name_by_user || device.name;
  const friendly = (state && state.attributes && state.attributes.friendly_name) || targetId;
  return String(friendly).replace(/\s*(Target angle|Doelhoek)$/i, "");
}

/** Status label and colour class for a panel. */
function statusOf(t, attrs, stormOn) {
  const s = t.status;
  const safety = attrs.safety;
  if (stormOn || safety === "storm") return [s.storm, "bad"];
  if (safety === "wind") return [s.wind, "bad"];
  if (attrs.stowed || attrs.reason === "stow") return [s.stowed, "warn"];
  if (safety === "startup") return [s.startup, "idle"];
  if (safety === "stale") return [s.stale, "idle"];
  if (["snow", "rain", "frost"].includes(safety)) return [s[safety], "cold"];
  if (attrs.mode === "manual") return [s.manual, "info"];
  if (attrs.paused_until) return [s.paused, "info"];
  if (attrs.auto === false) return [s.off, "idle"];
  if (attrs.reason === "night") return [s.night, "night"];
  if (attrs.reason === "diffuse") return [s.diffuse, "cold"];
  return [s[attrs.strategy] || s.daily, "ok"];
}

const SVG_W = 300;
const SVG_H = 170;
const CX = 150;
const CY = 140;
const DOME = 118;
const PANEL = 104;
const PIVOT_Y = CY - 56;

/** Side-view angle of the sun (0 = horizon in front, 90 = overhead, 180 = behind). */
function profileAngle(azimuth, elevation, panelAzimuth) {
  const h = Math.cos(rad(elevation)) * Math.cos(rad(azimuth - panelAzimuth));
  return (Math.atan2(Math.sin(rad(elevation)), h) * 180) / Math.PI;
}

function domePoint(angle) {
  return [CX + DOME * Math.cos(rad(angle)), CY - DOME * Math.sin(rad(angle))];
}

function panelLine(angle, pivotY) {
  const dx = (PANEL / 2) * Math.cos(rad(angle));
  const dy = (PANEL / 2) * Math.sin(rad(angle));
  // Faces right: the left (back) edge is raised.
  return [CX - dx, pivotY - dy, CX + dx, pivotY + dy];
}

function sideView(attrs, current, target, cls) {
  const pivotY = PIVOT_Y;
  const parts = [];
  // Sky dome and horizon.
  parts.push(`<path class="dome" d="M ${CX - DOME} ${CY} A ${DOME} ${DOME} 0 0 1 ${CX + DOME} ${CY}"/>`);
  parts.push(`<line class="ground" x1="8" y1="${CY}" x2="${SVG_W - 8}" y2="${CY}"/>`);
  // The band of sky the sun crosses today, seen from the side.
  const paz = num(attrs.azimuth) ?? 180;
  const angles = (Array.isArray(attrs.sun_path) ? attrs.sun_path : [])
    .filter((p) => Array.isArray(p) && num(p[1]) !== null && num(p[1]) > 0 && num(p[2]) !== null)
    .map((p) => profileAngle(num(p[2]), num(p[1]), paz))
    .filter((a) => a <= 90); // in front of the panel
  if (angles.length > 1) {
    const [x0, y0] = domePoint(Math.min(...angles));
    const [x1, y1] = domePoint(Math.max(...angles));
    parts.push(`<path class="sunpath" d="M ${x0.toFixed(1)} ${y0.toFixed(1)} A ${DOME} ${DOME} 0 0 0 ${x1.toFixed(1)} ${y1.toFixed(1)}"/>`);
  }
  // Post and actuator arm.
  parts.push(`<line class="post" x1="${CX}" y1="${CY}" x2="${CX}" y2="${pivotY}"/>`);
  const a = current ?? target ?? 0;
  const armX = CX - 34 * Math.cos(rad(a));
  const armY = pivotY - 34 * Math.sin(rad(a));
  const baseX = CX - 46;
  parts.push(`<line class="arm" x1="${baseX}" y1="${CY}" x2="${armX.toFixed(1)}" y2="${armY.toFixed(1)}"/>`);
  parts.push(`<circle class="joint" cx="${baseX}" cy="${CY}" r="3"/>`);
  // Target ghost.
  if (target !== null && current !== null && Math.abs(target - current) > 0.5) {
    const g = panelLine(target, pivotY);
    parts.push(`<line class="ghost" x1="${g[0].toFixed(1)}" y1="${g[1].toFixed(1)}" x2="${g[2].toFixed(1)}" y2="${g[3].toFixed(1)}"/>`);
  }
  // Panel.
  const p = panelLine(a, pivotY);
  parts.push(`<line class="pv ${cls}" x1="${p[0].toFixed(1)}" y1="${p[1].toFixed(1)}" x2="${p[2].toFixed(1)}" y2="${p[3].toFixed(1)}"/>`);
  parts.push(`<circle class="joint" cx="${CX}" cy="${pivotY}" r="3.5"/>`);
  // Sun now.
  const el = num(attrs.sun_elevation);
  const az = num(attrs.sun_azimuth);
  if (el !== null && az !== null && el > -1) {
    const [sx, sy] = domePoint(profileAngle(az, Math.max(el, 0), paz));
    parts.push(`<line class="ray" x1="${sx.toFixed(1)}" y1="${sy.toFixed(1)}" x2="${CX}" y2="${pivotY}"/>`);
    parts.push(`<circle class="sun" cx="${sx.toFixed(1)}" cy="${sy.toFixed(1)}" r="9"/>`);
  } else {
    parts.push(`<circle class="moon" cx="${SVG_W - 34}" cy="30" r="8"/><circle class="moon-cut" cx="${SVG_W - 30}" cy="27" r="7"/>`);
  }
  return `<svg class="side" viewBox="0 0 ${SVG_W} ${SVG_H}" role="img" aria-label="${esc(deg(current))}">${parts.join("")}</svg>`;
}

function curveStrip(attrs, current, nowMinutes) {
  const curve = (Array.isArray(attrs.today_curve) ? attrs.today_curve : []).filter((p) => Array.isArray(p) && num(p[1]) !== null);
  if (curve.length < 2) return "";
  const lo = Math.min(num(attrs.min_angle) ?? 0, ...curve.map((p) => num(p[1])));
  const hi = Math.max(num(attrs.max_angle) ?? 90, ...curve.map((p) => num(p[1])));
  const span = hi - lo || 1;
  const x = (m) => ((m / 1440) * 296 + 2).toFixed(1);
  const y = (v) => (54 - ((v - lo) / span) * 46).toFixed(1);
  const sun = (Array.isArray(attrs.sun_path) ? attrs.sun_path : []).filter((p) => Array.isArray(p) && num(p[1]) !== null);
  const maxEl = Math.max(1, ...sun.map((p) => num(p[1])));
  let area = "";
  if (sun.length > 1) {
    const pts = sun.map((p) => `${x(minutesOf(p[0]))},${(56 - (Math.max(0, num(p[1])) / maxEl) * 30).toFixed(1)}`);
    area = `<polygon class="sunarea" points="${x(0)},56 ${pts.join(" ")} ${x(1440)},56"/>`;
  }
  const line = curve.map((p) => `${x(minutesOf(p[0]))},${y(num(p[1]))}`).join(" ");
  const nowX = x(nowMinutes);
  const dot = current !== null ? `<circle class="nowdot" cx="${nowX}" cy="${y(Math.max(lo, Math.min(hi, current)))}" r="3"/>` : "";
  return `<svg class="curve" viewBox="0 0 300 60" preserveAspectRatio="none">${area}<polyline class="plan" points="${line}"/><line class="nowline" x1="${nowX}" y1="2" x2="${nowX}" y2="58"/>${dot}</svg>
    <div class="axis"><span>00:00</span><span>${esc(deg(lo))} ${DASH} ${esc(deg(hi))}</span><span>24:00</span></div>`;
}

function windGauge(t, wind) {
  const a = (wind && wind.attributes) || {};
  const speed = num(a.wind_speed);
  const stow = num(a.stow_speed) ?? 50;
  const storm = num(a.storm_speed) ?? 75;
  const max = Math.max(storm * 1.15, (speed ?? 0) * 1.05, 1);
  const pct = (v) => Math.max(0, Math.min(100, (v / max) * 100)).toFixed(1);
  const cls = speed === null ? "idle" : speed >= storm ? "bad" : speed >= stow ? "warn" : "ok";
  return `<div class="wind">
    <div class="wind-head"><span>${esc(t.wind)}</span><span class="wind-value">${speed === null ? DASH : esc(speed.toFixed(0))} km/h</span></div>
    <div class="gauge"><div class="fill ${cls}" style="width:${speed === null ? 0 : pct(speed)}%"></div>
      <div class="mark" style="left:${pct(stow)}%" title="${esc(t.stow_at)}"></div>
      <div class="mark storm" style="left:${pct(storm)}%" title="${esc(t.storm_at)}"></div></div>
    <div class="gauge-labels"><span style="left:${pct(stow)}%">${esc(t.stow_at)} ${esc(stow.toFixed(0))}</span><span style="left:${pct(storm)}%">${esc(t.storm_at)} ${esc(storm.toFixed(0))}</span></div>
  </div>`;
}

class HeliosTiltCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { ...DEFAULTS };
    this._seen = new Map();
    this._busy = new Set();
    this._error = "";
    this._dragging = false;
  }

  static getConfigElement() {
    return document.createElement("helios-tilt-card-editor");
  }

  static getStubConfig(hass) {
    const targets = hass ? findTargets(hass, {}) : [];
    return targets.length ? { entities: targets.slice(0, 1) } : {};
  }

  setConfig(config) {
    if (!config || typeof config !== "object" || Array.isArray(config)) {
      throw new Error("Invalid configuration");
    }
    if (config.entities !== undefined && !Array.isArray(config.entities)) {
      throw new Error("entities must be a list of target angle sensors");
    }
    this._config = { ...DEFAULTS, ...config };
    this._seen.clear();
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._dragging) return;
    if (this._changed(hass)) this._render();
  }

  get hass() {
    return this._hass;
  }

  getCardSize() {
    const n = this._hass ? findTargets(this._hass, this._config).length : 1;
    return Math.max(1, n) * 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _t() {
    const lang = ((this._hass && (this._hass.locale?.language || this._hass.language)) || "en").slice(0, 2);
    return I18N[lang] || I18N.en;
  }

  _ids() {
    const out = [];
    for (const target of findTargets(this._hass, this._config)) {
      out.push(target, ...Object.values(relatedIds(this._hass, target)));
    }
    return out;
  }

  _changed(hass) {
    const ids = this._ids();
    let changed = ids.length !== this._seen.size;
    const next = new Map();
    for (const id of ids) {
      const state = hass.states[id];
      next.set(id, state);
      if (this._seen.get(id) !== state) changed = true;
    }
    this._seen = next;
    return changed || !this.shadowRoot.querySelector(".wrap");
  }

  async _call(service, data, key) {
    if (this._busy.has(key)) return;
    this._busy.add(key);
    this._error = "";
    this._render();
    try {
      await this._hass.callService(DOMAIN, service, data);
    } catch (err) {
      this._error = `${this._t().failed}: ${err && err.message ? err.message : err}`;
    } finally {
      this._busy.delete(key);
      this._render();
    }
  }

  _panel(targetId, t) {
    const hass = this._hass;
    const state = hass.states[targetId];
    const ids = relatedIds(hass, targetId);
    const name = panelName(hass, targetId, state);
    if (!state || state.state === "unavailable") {
      return `<section class="panel"><div class="head"><div class="name">${esc(name)}</div><span class="chip idle">${esc(t.unavailable)}</span></div></section>`;
    }
    const attrs = state.attributes || {};
    const get = (key) => hass.states[ids[key]];
    const currentState = get("current");
    const current = num(currentState && currentState.state);
    const target = num(state.state);
    const wind = get("wind");
    const storm = get("storm");
    const [label, cls] = statusOf(t, attrs, storm && storm.state === "on");
    const cur = (currentState && currentState.attributes) || {};
    const relays = cur.actuator_type === "relays";
    const estimated = cur.source === "estimate" || cur.estimated === true;
    const uncertain = relays && cur.position_uncertain === true;
    const moving = cur.direction === "opening" ? t.moving_open : cur.direction === "closing" ? t.moving_close : "";
    const calibrating = relays && cur.calibration && cur.calibration.phase;
    const offline = relays && cur.actuator_available === false;
    const offlineList = Array.isArray(cur.unavailable_entities) ? cur.unavailable_entities.join(", ") : "";
    const detail = attrs.safety_detail || attrs.detail || "";
    const gainState = get("gain");
    const gain = num(gainState && gainState.state);
    const gainNow = gainState ? num(gainState.attributes.instant_gain) : null;
    const pct = (v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
    const movesState = get("moves");
    const moves = num(movesState && movesState.state);
    const cfg = this._config;
    const lo = num(attrs.min_angle) ?? 0;
    const hi = num(attrs.max_angle) ?? 90;
    const manualState = get("manual");
    const sliderValue = num(manualState && manualState.state) ?? current ?? target ?? lo;
    const busy = (k) => (this._busy.has(`${targetId}:${k}`) ? " disabled" : "");
    const active = (on) => (on ? " active" : "");
    const isManual = attrs.mode === "manual";
    const isStow = Boolean(attrs.stowed) || attrs.safety === "storm" || attrs.safety === "wind";
    const now = new Date();
    const nowMinutes = now.getHours() * 60 + now.getMinutes();

    let html = `<section class="panel ${cls}" data-entity="${esc(targetId)}">
      <div class="head">
        <div class="name">${esc(name)}</div>
        <span class="chip ${cls}">${esc(label)}</span>
      </div>
      ${offline || uncertain || calibrating ? `<div class="badges">${offline ? `<span class="chip bad badge-offline" title="${esc(t.offline_title + offlineList)}">${esc(t.offline)}</span>` : ""}${uncertain ? `<span class="chip warn badge-uncertain">${esc(t.uncertain)}</span>` : ""}${calibrating ? `<span class="chip info">${esc(t.calibrating)}</span>` : ""}</div>` : ""}
      <div class="hero">
        ${sideView(attrs, current, target, cls)}
        <div class="figures">
          <div class="big">${esc(deg(current))}${estimated ? `<span class="est">${esc(t.estimated)}</span>` : ""}</div>
          ${moving ? `<div class="sub moving">${esc(moving)}</div>` : ""}
          <div class="sub">${esc(t.target)} ${esc(deg(target))}</div>
          ${detail ? `<div class="detail">${esc(detail)}</div>` : ""}
          <div class="sub">${esc(t.sun)} ${esc(deg(attrs.sun_azimuth))} / ${esc(deg(attrs.sun_elevation))}</div>
          ${gain !== null ? `<div class="sub" title="${esc(gainState.attributes.basis || "")}">${esc(pct(gain))} ${esc(t.gain)}${gainNow !== null ? ` <span class="dim">(${esc(t.gain_now)} ${esc(pct(gainNow))})</span>` : ""}</div>` : ""}
          ${moves !== null ? `<div class="sub">${esc(moves.toFixed(0))} ${esc(t.moves_today)}</div>` : ""}
        </div>
      </div>`;
    if (cfg.show_wind) html += windGauge(t, wind);
    if (cfg.show_controls) {
      html += `<div class="controls">
        <button data-action="auto" class="${active(!isManual && !isStow)}"${busy("auto")}>${esc(t.auto)}</button>
        <button data-action="stow" class="${active(isStow)}"${busy("stow")}>${esc(t.stow)}</button>
        <button data-action="manual" class="${active(isManual)}"${busy("manual")}>${esc(t.manual)}</button>
        ${relays ? `<button data-action="home" class="${uncertain ? "attention" : ""}" title="${esc(t.home_title)}"${offline ? " disabled" : busy("home")}>${esc(t.home)}</button>` : ""}
      </div>
      <label class="slider"><span>${esc(t.angle)}</span>
        <input type="range" min="${esc(lo)}" max="${esc(hi)}" step="1" value="${esc(sliderValue)}"${busy("tilt")}>
        <output>${esc(deg(sliderValue))}</output></label>`;
    }
    if (cfg.show_curve) {
      const strip = curveStrip(attrs, current, nowMinutes);
      if (strip) html += `<div class="block"><div class="label">${esc(t.plan)}</div>${strip}</div>`;
    }
    if (cfg.show_history) {
      const last = get("last");
      const history = (last && last.attributes && Array.isArray(last.attributes.history) ? last.attributes.history : []).slice(
        0,
        Math.max(0, num(cfg.history_count) ?? 4),
      );
      html += `<div class="block"><div class="label">${esc(t.moves)}</div>`;
      html += history.length
        ? `<ul class="history">${history
            .map(
              (m) =>
                `<li><span class="dot r-${esc(m.reason)}"></span><span class="time">${esc(timeOf(m.time))}</span><span class="deg">${esc(deg(m.angle))}</span><span class="why">${esc(t.reasons[m.reason] || m.reason)}${m.detail ? ` ${DOT} ${esc(m.detail)}` : ""}</span></li>`,
            )
            .join("")}</ul>`
        : `<div class="empty">${esc(t.no_moves)}</div>`;
      html += "</div>";
    }
    return `${html}</section>`;
  }

  _render() {
    if (!this._hass) return;
    const t = this._t();
    const targets = findTargets(this._hass, this._config);
    const title = this._config.title ? `<div class="title">${esc(this._config.title)}</div>` : "";
    const body = targets.length
      ? `<div class="grid">${targets.map((id) => this._panel(id, t)).join("")}</div>`
      : `<div class="notice">${esc(t.not_found)}</div>`;
    const error = this._error ? `<div class="notice error">${esc(this._error)}</div>` : "";
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="wrap">${title}${error}${body}</div></ha-card>`;
    this._bind();
  }

  _bind() {
    for (const section of this.shadowRoot.querySelectorAll(".panel[data-entity]")) {
      const id = section.dataset.entity;
      const key = (k) => `${id}:${k}`;
      section.querySelectorAll("button[data-action]").forEach((button) => {
        button.addEventListener("click", () => {
          const action = button.dataset.action;
          if (action === "auto") this._call("resume_auto", { entity_id: id }, key("auto"));
          else if (action === "stow") this._call("stow", { entity_id: id }, key("stow"));
          else if (action === "manual") this._call("set_mode", { entity_id: id, mode: "manual" }, key("manual"));
          else if (action === "home") this._call("home", { entity_id: id }, key("home"));
        });
      });
      const slider = section.querySelector("input[type=range]");
      if (slider) {
        const out = section.querySelector(".slider output");
        slider.addEventListener("input", () => {
          this._dragging = true;
          out.textContent = deg(slider.value);
        });
        slider.addEventListener("change", () => {
          this._dragging = false;
          this._call("set_tilt", { entity_id: id, angle: Number(slider.value) }, key("tilt"));
        });
      }
    }
  }
}

const STYLE = `
  :host { display: block; container-type: inline-size; }
  ha-card { overflow: hidden; }
  .wrap { padding: 16px; color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, inherit); }
  .title { font-size: 1.25em; font-weight: 500; margin-bottom: 12px; }
  .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
  .panel { border: 1px solid var(--divider-color, rgba(127,127,127,.25)); border-radius: 12px; padding: 12px; min-width: 0; }
  .head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
  .name { font-weight: 600; font-size: 1.05em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chip { font-size: .8em; padding: 3px 10px; border-radius: 999px; white-space: nowrap; color: #fff; background: var(--hc-c); }
  .ok { --hc-c: var(--success-color, #2e9e5b); }
  .warn { --hc-c: var(--warning-color, #e08a00); }
  .bad { --hc-c: var(--error-color, #d93b3b); }
  .info { --hc-c: var(--info-color, #2f80ed); }
  .idle { --hc-c: var(--disabled-text-color, #8a8f98); }
  .cold { --hc-c: #1aa5c4; }
  .night { --hc-c: #5b5fc7; }
  .hero { display: flex; gap: 12px; align-items: center; }
  .side { flex: 1 1 auto; min-width: 0; width: 100%; max-width: 360px; height: auto; }
  .figures { flex: 0 0 auto; min-width: 104px; }
  .big { font-size: 2.2em; font-weight: 600; line-height: 1.1; }
  .sub { color: var(--secondary-text-color); font-size: .9em; margin-top: 2px; }
  .sub .dim { opacity: .75; white-space: nowrap; }
  .detail { font-size: .85em; margin-top: 4px; color: var(--hc-c, var(--secondary-text-color)); }
  .dome { fill: none; stroke: var(--divider-color, rgba(127,127,127,.3)); stroke-dasharray: 3 4; }
  .ground { stroke: var(--secondary-text-color); stroke-width: 2; opacity: .6; }
  .sunpath { fill: none; stroke: #f5a623; stroke-width: 7; stroke-linecap: round; opacity: .28; }
  .sun { fill: #f5a623; stroke: #ffd27a; stroke-width: 3; }
  .ray { stroke: #f5a623; stroke-width: 1; stroke-dasharray: 2 3; opacity: .6; }
  .moon { fill: var(--secondary-text-color); opacity: .6; }
  .moon-cut { fill: var(--card-background-color, var(--ha-card-background, #fff)); }
  .post { stroke: var(--secondary-text-color); stroke-width: 4; stroke-linecap: round; }
  .arm { stroke: var(--secondary-text-color); stroke-width: 3; stroke-linecap: round; opacity: .8; }
  .joint { fill: var(--primary-text-color); }
  .pv { stroke: var(--hc-c); stroke-width: 9; stroke-linecap: round; }
  .ghost { stroke: var(--primary-text-color); stroke-width: 2; stroke-dasharray: 5 4; opacity: .45; }
  .wind { margin: 10px 0 4px; }
  .wind-head { display: flex; justify-content: space-between; font-size: .9em; color: var(--secondary-text-color); }
  .wind-value { color: var(--primary-text-color); font-weight: 500; }
  .gauge { position: relative; height: 8px; border-radius: 4px; background: var(--divider-color, rgba(127,127,127,.2)); margin-top: 4px; }
  .fill { height: 100%; border-radius: 4px; background: var(--hc-c); transition: width .4s; }
  .mark { position: absolute; top: -3px; width: 2px; height: 14px; background: var(--warning-color, #e08a00); }
  .mark.storm { background: var(--error-color, #d93b3b); }
  .gauge-labels { position: relative; height: 16px; font-size: .72em; color: var(--secondary-text-color); }
  .gauge-labels span { position: absolute; transform: translateX(-50%); white-space: nowrap; top: 2px; }
  .controls { display: grid; grid-template-columns: repeat(auto-fit, minmax(60px, 1fr)); gap: 8px; margin-top: 10px; }
  button.attention { border-color: var(--warning-color, #f5a623); color: var(--warning-color, #f5a623); font-weight: 600; }
  .badges { display: flex; gap: 6px; flex-wrap: wrap; margin: -4px 0 6px; }
  .est { font-size: .4em; font-weight: 500; margin-left: 6px; padding: 1px 6px; border-radius: 6px; vertical-align: middle; color: var(--secondary-text-color); border: 1px dashed var(--secondary-text-color); }
  .moving { font-style: italic; }
  button { font: inherit; padding: 8px 4px; border-radius: 8px; cursor: pointer; border: 1px solid var(--divider-color, rgba(127,127,127,.3)); background: transparent; color: var(--primary-text-color); }
  button.active { background: var(--primary-color, #03a9f4); border-color: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
  button:disabled { opacity: .5; cursor: progress; }
  .slider { display: grid; grid-template-columns: auto 1fr 3.2em; align-items: center; gap: 8px; margin-top: 10px; font-size: .9em; color: var(--secondary-text-color); }
  .slider input { width: 100%; accent-color: var(--primary-color, #03a9f4); }
  .slider output { text-align: right; color: var(--primary-text-color); }
  .block { margin-top: 12px; }
  .label { font-size: .8em; text-transform: uppercase; letter-spacing: .04em; color: var(--secondary-text-color); margin-bottom: 4px; }
  .curve { width: 100%; height: 60px; display: block; }
  .sunarea { fill: #f5a623; opacity: .14; }
  .plan { fill: none; stroke: var(--primary-color, #03a9f4); stroke-width: 2; vector-effect: non-scaling-stroke; }
  .nowline { stroke: var(--secondary-text-color); stroke-dasharray: 2 3; vector-effect: non-scaling-stroke; }
  .nowdot { fill: var(--primary-text-color); }
  .axis { display: flex; justify-content: space-between; font-size: .72em; color: var(--secondary-text-color); }
  .history { list-style: none; margin: 0; padding: 0; }
  .history li { display: grid; grid-template-columns: 10px 3.2em 3em 1fr; gap: 6px; align-items: baseline; font-size: .88em; padding: 3px 0; border-bottom: 1px solid var(--divider-color, rgba(127,127,127,.15)); }
  .history li:last-child { border-bottom: 0; }
  .why { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--secondary-text-color); min-width: 0; }
  .time { color: var(--secondary-text-color); }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success-color, #2e9e5b); align-self: center; }
  .r-wind, .r-storm { background: var(--error-color, #d93b3b); }
  .r-stow { background: var(--warning-color, #e08a00); }
  .r-manual, .r-calibrate { background: var(--info-color, #2f80ed); }
  .r-night { background: #5b5fc7; }
  .r-diffuse, .r-snow, .r-rain, .r-frost { background: #1aa5c4; }
  .empty, .notice { color: var(--secondary-text-color); font-size: .9em; }
  .notice { padding: 8px 0; }
  .notice.error { color: var(--error-color, #d93b3b); }
  @container (max-width: 420px) {
    .wrap { padding: 12px; }
    .hero { flex-direction: column; align-items: stretch; }
    .figures { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: baseline; }
    .big { font-size: 1.8em; }
  }
`;

class HeliosTiltCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._render();
  }

  _render() {
    if (!this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => {
        const lang = ((this._hass && this._hass.language) || "en").slice(0, 2);
        return (I18N[lang] || I18N.en).editor[schema.name] || schema.name;
      };
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...this._config, ...ev.detail.value };
        for (const key of Object.keys(config)) {
          if (config[key] === "" || config[key] === undefined) delete config[key];
        }
        if (Array.isArray(config.entities) && !config.entities.length) delete config.entities;
        this._config = config;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.schema = [
      { name: "title", selector: { text: {} } },
      { name: "entities", selector: { entity: { multiple: true, filter: { integration: DOMAIN, domain: "sensor" } } } },
      { name: "show_wind", selector: { boolean: {} } },
      { name: "show_controls", selector: { boolean: {} } },
      { name: "show_curve", selector: { boolean: {} } },
      { name: "show_history", selector: { boolean: {} } },
      { name: "history_count", selector: { number: { min: 0, max: 10, mode: "box" } } },
    ];
    this._form.data = { ...DEFAULTS, ...this._config };
    if (this._hass) this._form.hass = this._hass;
  }
}

if (!customElements.get("helios-tilt-card")) customElements.define("helios-tilt-card", HeliosTiltCard);
if (!customElements.get("helios-tilt-card-editor")) customElements.define("helios-tilt-card-editor", HeliosTiltCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "helios-tilt-card")) {
  window.customCards.push({
    type: "helios-tilt-card",
    name: "Helios Tilt",
    description: "Solar panel tilt: side view with the sun, wind, controls and today's plan.",
    preview: true,
    documentationURL: "https://github.com/DonTranQuiL/helios-tilt",
  });
}
console.info(`%c HELIOS-TILT-CARD %c ${VERSION} `, "color:#0b1f3a;background:#f5a623;font-weight:700", "color:#f5a623;background:#0b1f3a");
