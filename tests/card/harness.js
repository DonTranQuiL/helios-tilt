// Browser test harness for the Helios Tilt card. Runs in headless Chrome
// (see tests/test_card.py) after the card module; writes JSON results to #out.
const results = { errors: [], calls: [], checks: {} };
const origError = console.error;
console.error = (...args) => { results.errors.push(args.map(String).join(" ")); origError(...args); };
window.addEventListener("error", (ev) => results.errors.push(String(ev.message)));
window.addEventListener("unhandledrejection", (ev) => results.errors.push(String(ev.reason)));

// Minimal stand-in for Home Assistant's form element used by the editor.
customElements.define("ha-form", class extends HTMLElement {});

const DATA = JSON.parse(document.getElementById("states").textContent);
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const clone = (v) => JSON.parse(JSON.stringify(v));

function makeHass(states, fail = false, extra = {}) {
  return {
    states,
    entities: DATA.entities,
    devices: DATA.devices,
    language: "en",
    callService: async (domain, service, data) => {
      results.calls.push({ domain, service, data });
      if (fail) throw new Error("boom <b>bold</b>");
    },
    ...extra,
  };
}

const text = (card) => card.shadowRoot.querySelector(".wrap").textContent.replace(/\s+/g, " ");

async function newCard(config, hass, width = 900) {
  const box = document.createElement("div");
  box.style.width = `${width}px`;
  document.body.appendChild(box);
  const card = document.createElement("helios-tilt-card");
  card.setConfig(config);
  box.appendChild(card);
  card.hass = hass;
  await flush();
  return card;
}

async function click(card, selector) {
  const el = card.shadowRoot.querySelector(selector);
  if (!el) return false;
  el.click();
  await flush();
  await flush();
  return true;
}

(async () => {
  const c = results.checks;
  try {
    const card = await newCard({}, makeHass(DATA.states));
    const root = card.shadowRoot;
    const t = text(card);
    c.panels = root.querySelectorAll("section.panel").length;
    c.names = [...root.querySelectorAll(".name")].map((el) => el.textContent);
    c.chip = root.querySelector(".chip").textContent;
    c.big = root.querySelector(".big").textContent;
    c.bad_text = ["??", "undefined", "NaN", "null", "[object Object]"].filter((x) => t.includes(x));
    c.sun = root.querySelectorAll("circle.sun").length;
    c.sunpath = root.querySelectorAll("path.sunpath").length;
    c.plan_points = (root.querySelector(".plan")?.getAttribute("points") || "").split(" ").filter(Boolean).length;
    c.wind_text = root.querySelector(".wind-value")?.textContent;
    c.marks = root.querySelectorAll(".gauge .mark").length;
    c.history = root.querySelectorAll(".history li").length;
    c.history_first = root.querySelector(".history li .why")?.textContent;
    c.buttons = [...root.querySelectorAll("button[data-action]")].map((b) => b.dataset.action);
    c.active = [...root.querySelectorAll("button.active")].map((b) => b.dataset.action);
    c.slider = { min: root.querySelector("input[type=range]").min, max: root.querySelector("input[type=range]").max };

    // Same state objects again: no re-render.
    let renders = 0;
    const real = card._render.bind(card);
    card._render = () => { renders += 1; real(); };
    card.hass = makeHass(DATA.states);
    c.renders_same = renders;
    card.hass = makeHass({ ...DATA.states, "sensor.unrelated": { state: "1", attributes: {} } });
    c.renders_unrelated = renders;
    card._render = real;

    // Buttons and slider.
    for (const action of ["auto", "stow", "manual"]) await click(card, `button[data-action="${action}"]`);
    const slider = card.shadowRoot.querySelector("input[type=range]");
    slider.value = "35";
    slider.dispatchEvent(new Event("input"));
    c.slider_output = card.shadowRoot.querySelector(".slider output").textContent;
    card.hass = makeHass({ ...DATA.states, "sensor.x": { state: "2", attributes: {} } });
    c.kept_while_dragging = card.shadowRoot.querySelector("input[type=range]") === slider;
    slider.dispatchEvent(new Event("change"));
    await flush();
    await flush();

    // Errors are shown escaped and buttons are usable again.
    card.hass = makeHass(clone(DATA.states), true);
    await click(card, 'button[data-action="stow"]');
    c.error = card.shadowRoot.querySelector(".notice.error")?.textContent || "";
    c.error_markup = card.shadowRoot.querySelectorAll(".notice b").length;
    c.enabled_after_error = !card.shadowRoot.querySelector('button[data-action="stow"]').disabled;

    // A ghost panel when moving towards a different target; stowed status.
    const moving = clone(DATA.states);
    moving[DATA.target].state = "45.0";
    moving[DATA.target].attributes.stowed = true;
    const ghost = await newCard({ entities: [DATA.target] }, makeHass(moving));
    c.ghost = ghost.shadowRoot.querySelectorAll(".ghost").length;
    c.stowed_chip = ghost.shadowRoot.querySelector(".chip").textContent;

    // Night: a moon instead of the sun.
    const night = clone(DATA.states);
    night[DATA.target].attributes.sun_elevation = -20;
    const nightCard = await newCard({}, makeHass(night));
    c.moon = nightCard.shadowRoot.querySelectorAll(".moon").length;
    c.night_sun = nightCard.shadowRoot.querySelectorAll("circle.sun").length;

    // HTML in names and details is shown as text.
    const evil = clone(DATA.states);
    evil[DATA.target].attributes.safety_detail = '<img src="x" onerror="window.__xss=1">';
    evil[DATA.last].attributes.history[0].detail = "<b>bold</b>";
    const entitiesNoReg = {};
    const xss = await newCard({ title: "<i>T</i>" }, makeHass(evil, false, { entities: entitiesNoReg, devices: {} }));
    c.xss_nodes = xss.shadowRoot.querySelectorAll('img[src="x"], b, i').length;
    c.xss_text = text(xss).includes('<img src="x"');
    c.xss_fired = window.__xss || 0;
    c.fallback_names = [...xss.shadowRoot.querySelectorAll(".name")].map((el) => el.textContent);
    c.fallback_history = xss.shadowRoot.querySelectorAll(".history li").length;

    // Two relays (timed): estimated position, uncertain badge, Home button.
    const relayStates = clone(DATA.states);
    Object.assign(relayStates[DATA.current].attributes, {
      actuator_type: "relays", source: "estimate", estimated: true, position_uncertain: true, direction: "closing",
    });
    const relayCard = await newCard({ entities: [DATA.target] }, makeHass(relayStates));
    const rr = relayCard.shadowRoot;
    c.relay_est = rr.querySelector(".big .est")?.textContent;
    c.relay_badge = rr.querySelector(".badge-uncertain")?.textContent;
    c.relay_moving = rr.querySelector(".moving")?.textContent;
    c.relay_buttons = [...rr.querySelectorAll("button[data-action]")].map((b) => b.dataset.action);
    c.relay_home_attention = rr.querySelector('button[data-action="home"]')?.classList.contains("attention");
    await click(relayCard, 'button[data-action="home"]');
    c.plain_est = root.querySelectorAll(".est, .badge-uncertain").length;
    const relayNl = await newCard({ entities: [DATA.target] }, makeHass(relayStates, false, { language: "nl" }));
    c.relay_nl = [relayNl.shadowRoot.querySelector(".est")?.textContent, relayNl.shadowRoot.querySelector('button[data-action="home"]')?.textContent];

    // Missing and unavailable.
    const none = await newCard({}, makeHass({}, false, { entities: {} }));
    c.not_found = text(none).includes("No Helios Tilt panels found");
    const down = clone(DATA.states);
    down[DATA.target] = { entity_id: DATA.target, state: "unavailable", attributes: {} };
    const downCard = await newCard({ entities: [DATA.target] }, makeHass(down));
    c.unavailable = text(downCard).includes("Unavailable");

    // Dutch.
    const nl = await newCard({}, makeHass(DATA.states, false, { language: "nl" }));
    c.nl_buttons = [...nl.shadowRoot.querySelectorAll("button[data-action]")].map((b) => b.textContent);

    // Narrow: stacked hero, nothing overflows.
    const narrow = await newCard({}, makeHass(DATA.states), 340);
    c.narrow_direction = getComputedStyle(narrow.shadowRoot.querySelector(".hero")).flexDirection;
    const panel = narrow.shadowRoot.querySelector("section.panel");
    c.narrow_overflow = panel.scrollWidth > panel.clientWidth + 1;
    const wide = await newCard({}, makeHass(DATA.states), 900);
    c.wide_direction = getComputedStyle(wide.shadowRoot.querySelector(".hero")).flexDirection;

    // Options hide blocks.
    const bare = await newCard({ show_wind: false, show_curve: false, show_history: false, show_controls: false }, makeHass(DATA.states));
    c.bare_blocks = bare.shadowRoot.querySelectorAll(".wind, .curve, .history, button, input").length;

    // Config validation, stub and editor.
    try { document.createElement("helios-tilt-card").setConfig("nope"); c.bad_config = "accepted"; } catch (err) { c.bad_config = "rejected"; }
    try { document.createElement("helios-tilt-card").setConfig({ entities: "sensor.x" }); c.bad_entities = "accepted"; } catch (err) { c.bad_entities = "rejected"; }
    const Card = customElements.get("helios-tilt-card");
    c.stub = Card.getStubConfig(makeHass(DATA.states));
    c.card_size = card.getCardSize();
    const editor = Card.getConfigElement();
    let changed = null;
    editor.addEventListener("config-changed", (ev) => { changed = ev.detail.config; });
    editor.setConfig({ type: "custom:helios-tilt-card" });
    editor.hass = makeHass(DATA.states);
    const form = editor.querySelector("ha-form");
    c.editor_fields = form.schema.map((s) => s.name);
    c.editor_label = form.computeLabel({ name: "show_wind" });
    form.dispatchEvent(new CustomEvent("value-changed", { detail: { value: { ...form.data, title: "Roof", entities: [] } } }));
    c.editor_config = changed;
    c.registered = (window.customCards || []).filter((x) => x.type === "helios-tilt-card").length;
  } catch (err) {
    results.errors.push(`harness: ${err && err.stack ? err.stack : err}`);
  }
  document.getElementById("out").textContent = JSON.stringify(results);
})();
