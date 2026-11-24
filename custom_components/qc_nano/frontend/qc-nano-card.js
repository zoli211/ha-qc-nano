/* qc-nano-card — dashboard card for the QC nano water dispenser.
 *
 * Shipped with the qc_nano integration, which loads it on every dashboard.
 * Usage:  type: custom:qc-nano-card
 * Options:
 *   device_id: <id>   only needed when the account has more than one dispenser
 *   title: <text>     header text (default: "Water dispenser" / "Vízadagoló")
 *   embedded: true    no own card chrome and header (for dashboards that wrap
 *                     cards in their own panels)
 *
 * Entities are found through the integration's translation keys, so the card
 * works whatever language the entity ids were created in.
 */
const QCN_VERSION = '0.2.0';

const LEVELS = ['mega', 'large', 'normal', 'small', 'tiny'];   // largest first
const KINDS = ['hot', 'ambient', 'cold'];                       // order of the device buttons
const KIND_COLOR = { hot: '#f87171', ambient: '#cfd6e2', cold: '#60a5fa' };
const COOLING_MODES = ['off', 'standard', 'boost'];
const TEMP_MIN = 4, TEMP_MAX = 16;
const PORTION_MIN = 50, PORTION_MAX = 3000, PORTION_STEP = 10;

const TEXT = {
  en: {
    title: 'Water dispenser', today: 'Today', filter: 'Filter', cooling: 'Cooling',
    change: 'change', details: 'Open water dispenser details', close: 'Close',
    off: 'Off', standard: 'Standard', boost: 'Boost', target: 'Target temperature',
    switches: 'Settings', child_lock: 'Child lock', light_off: 'Lights off',
    energy_saver: 'Energy saver', volume_sliders: 'Portion buttons', portions: 'Portions',
    hot: 'Hot', ambient: 'Room', cold: 'Cold',
    mega: 'Mega', large: 'Large', normal: 'Normal', small: 'Small', tiny: 'Tiny',
    info: 'Status', filter_left: 'Filter remaining', next_filter: 'Next filter change',
    next_cleaning: 'Next cleaning', cloud: 'Cloud', live: 'Live data',
    connected: 'Connected', disconnected: 'Disconnected',
    alert_filter: 'Filter change due', alert_cleaning: 'Cleaning needed',
    alert_offline: 'Dispenser offline', no_device: 'No QC nano dispenser found.',
    decrease: 'Decrease', increase: 'Increase', enabled: 'enabled', disabled: 'disabled',
    dispensing: 'Dispensing', locked: 'Child lock on', ml: 'mL', l: 'L',
    good: 'Good', warning: 'Warning', poor: 'Poor',
  },
  hu: {
    title: 'Vízadagoló', today: 'Ma', filter: 'Szűrő', cooling: 'Hűtés',
    change: 'csere', details: 'Vízadagoló részletei', close: 'Bezárás',
    off: 'Ki', standard: 'Normál', boost: 'Gyorshűtés', target: 'Célhőmérséklet',
    switches: 'Beállítások', child_lock: 'Gyerekzár', light_off: 'Fények kikapcsolása',
    energy_saver: 'Energiatakarékos mód', volume_sliders: 'Adaggombok', portions: 'Adagok',
    hot: 'Forró', ambient: 'Szoba', cold: 'Hideg',
    mega: 'Mega', large: 'Nagy', normal: 'Normál', small: 'Kicsi', tiny: 'Mini',
    info: 'Állapot', filter_left: 'Szűrő hátralévő kapacitása', next_filter: 'Következő szűrőcsere',
    next_cleaning: 'Következő tisztítás', cloud: 'Felhő', live: 'Élő adatok',
    connected: 'Kapcsolódva', disconnected: 'Nincs kapcsolat',
    alert_filter: 'Szűrőcsere esedékes', alert_cleaning: 'Tisztítás szükséges',
    alert_offline: 'A vízadagoló nem elérhető', no_device: 'Nem található QC nano vízadagoló.',
    decrease: 'Csökkentés', increase: 'Növelés', enabled: 'engedélyezve', disabled: 'letiltva',
    dispensing: 'Csapolás', locked: 'Gyerekzár bekapcsolva', ml: 'mL', l: 'l',
    good: 'Jó', warning: 'Figyelmeztetés', poor: 'Rossz',
  },
};

// translation keys of the integration's entities
const KEYS = {
  water_today: 'sensor', cold_water_today: 'sensor', hot_water_today: 'sensor', ambient_water_today: 'sensor',
  filter_remaining: 'sensor', next_filter_change: 'sensor', filter_status: 'sensor',
  cleaning_status: 'sensor', next_cleaning: 'sensor',
  cooling_mode: 'select', cold_temperature: 'number',
  child_lock: 'switch', light_off: 'switch', energy_saver: 'switch', volume_sliders: 'switch',
  cooling: 'binary_sensor', heating: 'binary_sensor', power: 'binary_sensor',
  cold_valve: 'binary_sensor', hot_valve: 'binary_sensor', ambient_valve: 'binary_sensor',
  cloud_connection: 'binary_sensor', live_connection: 'binary_sensor',
  filter_problem: 'binary_sensor', cleaning_problem: 'binary_sensor',
};
for (const k of KINDS) for (const l of LEVELS) {
  KEYS[`${k}_${l}_volume`] = 'number';
  KEYS[`${k}_${l}_enabled`] = 'switch';
}

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ---------------------------------------------------------------- styles */

const CSS = `
:host { display: block; --qcn-txt: var(--primary-text-color, #f3f5f9); --qcn-txt2: var(--secondary-text-color, #b3bccb);
  --qcn-dim: var(--disabled-text-color, #8a93a3); --qcn-blue: #60a5fa; --qcn-green: #34d399; --qcn-amber: #fbbf24;
  --qcn-red: #f87171; --qcn-line: rgba(255,255,255,.10); --qcn-fill: rgba(255,255,255,.06); }
ha-card { overflow: hidden; }
ha-card.embedded { background: transparent; border: none; box-shadow: none; }
.card { padding: 16px 18px; color: var(--qcn-txt); font-family: inherit; }
.embedded .card { padding: 0; }
.head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; color: var(--qcn-txt2);
  font-size: 15px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.head ha-icon { --mdc-icon-size: 20px; }
.embedded .head { display: none; }
.main { display: grid; grid-template-columns: 116px minmax(0, 1fr); gap: 16px; align-items: center;
  cursor: pointer; border-radius: 16px; outline: none; -webkit-tap-highlight-color: transparent; }
.main:focus-visible { box-shadow: 0 0 0 2px var(--qcn-blue); }
svg.dev { width: 116px; height: auto; display: block; overflow: visible; }
.stats { display: grid; gap: 10px; min-width: 0; }
.stat { background: var(--qcn-fill); border: 1px solid var(--qcn-line); border-radius: 14px; padding: 9px 12px; min-width: 0; }
.stat .l { font-size: 12.5px; font-weight: 600; color: var(--qcn-txt2); }
.stat .v { font-size: 20px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stat .s { font-size: 12.5px; color: var(--qcn-txt2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.alerts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.alerts:empty { display: none; }
.chip { display: inline-flex; align-items: center; gap: 6px; min-height: 34px; padding: 0 12px; border-radius: 17px;
  font-size: 13.5px; font-weight: 600; border: 1px solid; }
.chip ha-icon { --mdc-icon-size: 18px; }
.chip.warn { background: rgba(251,191,36,.14); border-color: rgba(251,191,36,.6); color: #fde68a; }
.chip.err { background: rgba(248,113,113,.18); border-color: rgba(248,113,113,.7); color: #fecaca; }
.empty { color: var(--qcn-txt2); padding: 8px 0; }

/* device drawing */
.cap { fill: url(#qcnSilver); }
.body { fill: url(#qcnBody); }
.panel { fill: #0d1118; stroke: rgba(255,255,255,.18); stroke-width: .8; }
.btn-ring { fill: none; stroke: rgba(255,255,255,.28); stroke-width: 1; transition: stroke .3s, fill .3s; }
.glyph { fill: none; stroke: rgba(255,255,255,.55); stroke-width: 1.3; stroke-linecap: round; stroke-linejoin: round; transition: stroke .3s; }
.glyph.solid { fill: rgba(255,255,255,.55); stroke: none; }
.b.run .btn-ring { stroke: var(--c); }
.b.run .glyph { stroke: var(--c); }
.b.run .glyph.solid { fill: var(--c); }
.b.open .btn-ring { stroke: var(--c); fill: color-mix(in srgb, var(--c) 35%, transparent); }
.b.open .glyph { stroke: #fff; }
.b.open .glyph.solid { fill: #fff; }
.stream { opacity: 0; transition: opacity .25s; }
.stream.on { opacity: 1; }
.stream .water { stroke-width: 6; stroke-linecap: round; opacity: .55; }
.stream .flow { stroke: rgba(255,255,255,.75); stroke-width: 2; stroke-linecap: round; stroke-dasharray: 4 9; }
.lock { opacity: 0; transition: opacity .3s; }
.lock.on { opacity: 1; }
.offline svg.dev { opacity: .45; filter: grayscale(1); }
@keyframes qcnflow { to { stroke-dashoffset: -26; } }
@keyframes qcnpulse { 0%, 100% { opacity: 1; } 50% { opacity: .45; } }
@media (prefers-reduced-motion: no-preference) {
  .stream.on .flow { animation: qcnflow .5s linear infinite; }
  .b.run:not(.open) { animation: qcnpulse 2.4s ease-in-out infinite; }
}

/* dialog */
.ov { position: fixed; inset: 0; z-index: 9999; display: none; place-items: center; padding: 24px;
  background: rgba(5,8,14,.62); -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px); }
.ov.open { display: grid; }
.dlg { width: min(960px, 100%); max-height: calc(100vh - 48px); overflow: auto; box-sizing: border-box;
  background: linear-gradient(160deg, #1c2333, #141a26); border: 1px solid var(--qcn-line); border-radius: 22px;
  box-shadow: 0 20px 60px rgba(0,0,0,.5); padding: 16px 24px 20px; color: var(--qcn-txt); font-family: inherit; }
.dh { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.dh h2 { margin: 0; font-size: 22px; font-weight: 700; flex: 1; }
.dh .sub { font-size: 14px; color: var(--qcn-txt2); font-weight: 500; margin-left: 8px; }
button { font: inherit; color: inherit; cursor: pointer; -webkit-tap-highlight-color: transparent; }
button:focus-visible { outline: 2px solid var(--qcn-blue); outline-offset: 2px; }
button:active:not([disabled]) { transform: scale(.96); }
button[disabled] { opacity: .35; cursor: default; }
.rb { width: 54px; height: 54px; border-radius: 50%; border: 1px solid rgba(255,255,255,.16); background: var(--qcn-fill);
  display: grid; place-items: center; padding: 0; flex: none; }
.rb ha-icon { --mdc-icon-size: 28px; }
.sec { margin-top: 14px; }
.sec > .t { font-size: 13px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--qcn-txt2); margin-bottom: 10px; }
.row2 { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 18px; }
.seg { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.sb { height: 58px; border-radius: 16px; border: 1px solid rgba(255,255,255,.12); background: var(--qcn-fill);
  font-size: 16px; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 8px; }
.sb ha-icon { --mdc-icon-size: 22px; }
.sb.on { background: rgba(96,165,250,.20); border-color: rgba(96,165,250,.6); color: #dbeafe; }
.temp { display: flex; align-items: center; justify-content: space-between; gap: 12px; height: 58px; }
.temp .val { font-size: 32px; font-weight: 300; letter-spacing: -.02em; white-space: nowrap; }
.tg { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.tb { min-height: 64px; border-radius: 18px; border: 1px solid rgba(255,255,255,.12); background: var(--qcn-fill);
  display: flex; align-items: center; gap: 10px; padding: 10px 14px; text-align: left; font-size: 15px; font-weight: 700; }
.tb ha-icon { --mdc-icon-size: 26px; color: var(--qcn-dim); flex: none; }
.tb .st { display: block; font-size: 12.5px; font-weight: 600; color: var(--qcn-txt2); }
.tb.on { background: rgba(96,165,250,.15); border-color: rgba(96,165,250,.6); }
.tb.on ha-icon { color: var(--qcn-blue); }
.pg { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.pc { background: rgba(255,255,255,.035); border: 1px solid var(--qcn-line); border-radius: 18px; padding: 12px; }
.pc h3 { margin: 0 0 8px; display: flex; align-items: center; gap: 8px; font-size: 16px; }
.pc h3 .dot { width: 12px; height: 12px; border-radius: 50%; background: var(--c); }
.pr { display: grid; grid-template-columns: minmax(64px, 1fr) 50px minmax(64px, auto) 50px; gap: 8px; align-items: center; margin-top: 6px; }
.pr .rb { width: 50px; height: 50px; }
.pr .rb ha-icon { --mdc-icon-size: 24px; }
.nm { height: 50px; border-radius: 14px; border: 1px solid rgba(255,255,255,.12); background: transparent; font-size: 14px;
  font-weight: 700; color: var(--qcn-dim); text-decoration: line-through; padding: 0 8px; }
.nm.on { background: color-mix(in srgb, var(--c) 18%, transparent); border-color: color-mix(in srgb, var(--c) 60%, transparent);
  color: var(--qcn-txt); text-decoration: none; }
.pv { text-align: center; font-size: 18px; font-weight: 700; white-space: nowrap; }
.pv small { font-size: 12px; font-weight: 600; color: var(--qcn-txt2); margin-left: 2px; }
.pv.pend { color: var(--qcn-amber); }
.info { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.ic { background: var(--qcn-fill); border: 1px solid var(--qcn-line); border-radius: 14px; padding: 10px 12px; min-width: 0; }
.ic .l { font-size: 12.5px; font-weight: 600; color: var(--qcn-txt2); }
.ic .v { font-size: 16px; font-weight: 700; margin-top: 2px; }
.ic .s { font-size: 12px; color: var(--qcn-txt2); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.badge { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 12px; border-radius: 15px; font-size: 13px; font-weight: 700;
  border: 1px solid currentColor; }
.badge::before { content: ''; width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.badge.ok { background: rgba(52,211,153,.12); } .badge.bad { background: rgba(248,113,113,.14); }
.ok { color: var(--qcn-green); } .bad { color: var(--qcn-red); } .mid { color: var(--qcn-amber); }
@media (max-width: 760px) {
  .row2, .pg { grid-template-columns: minmax(0, 1fr); }
  .tg, .info { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
`;

/* ------------------------------------------------------------- drawing */

// simple own glyphs (centred on 0,0, about 8 px)
const GLYPH = {
  hot: '<path class="glyph" d="M0 4.6c-2.4 0-3.8-1.6-3.8-3.4 0-2.2 2-3.2 2.4-5.6 1.2 1 1.6 2.2 1.4 3.4 .8-.4 1.4-1.2 1.6-2.2 1.4 1.2 2.2 2.6 2.2 4.4 0 1.8-1.4 3.4-3.8 3.4z"/>',
  ambient: '<path class="glyph" d="M-1.1 1.8v-5.6a1.1 1.1 0 0 1 2.2 0v5.6"/><circle class="glyph" cx="0" cy="3.2" r="2"/>',
  cold: '<path class="glyph" d="M0-5v10M-4.3-2.5l8.6 5M-4.3 2.5l8.6-5M-1.4-4.2L0-3l1.4-1.2M-1.4 4.2L0 3l1.4 1.2"/>',
};

function deviceSvg(t) {
  const btn = (kind, x) => `
    <g class="b" data-kind="${kind}" style="--c:${KIND_COLOR[kind]}" transform="translate(${x} 20)">
      <circle class="btn-ring" r="8.5"/>${GLYPH[kind]}
    </g>`;
  return `
  <svg class="dev" viewBox="0 0 116 220" role="img" aria-labelledby="qcnSvgT">
    <title id="qcnSvgT">${esc(t.title)}</title>
    <defs>
      <linearGradient id="qcnSilver" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#9aa3b0"/><stop offset=".45" stop-color="#e4e8ee"/><stop offset="1" stop-color="#8e97a4"/>
      </linearGradient>
      <linearGradient id="qcnBody" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#0f1217"/><stop offset=".5" stop-color="#22262e"/><stop offset="1" stop-color="#0f1217"/>
      </linearGradient>
      <linearGradient id="qcnTray" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#c9ced6"/><stop offset="1" stop-color="#7f8894"/>
      </linearGradient>
    </defs>
    <!-- cap with the touch panel (on the real device it is on top) -->
    <rect class="cap" x="6" y="4" width="104" height="38" rx="12"/>
    <rect class="panel" x="13" y="9" width="90" height="22" rx="11"/>
    ${btn('hot', 31)}${btn('ambient', 58)}${btn('cold', 85)}
    <!-- body -->
    <path class="body" d="M14 42h88v142a6 6 0 0 1-6 6H20a6 6 0 0 1-6-6z"/>
    <!-- spout -->
    <rect x="49" y="42" width="18" height="7" rx="2.5" fill="#aab2bd"/>
    <!-- water stream -->
    <g class="stream">
      <line class="water" x1="58" y1="50" x2="58" y2="188"/>
      <line class="flow" x1="58" y1="50" x2="58" y2="188"/>
    </g>
    <!-- child lock -->
    <g class="lock" transform="translate(32 64)" aria-hidden="true">
      <circle r="13" fill="rgba(251,191,36,.16)" stroke="rgba(251,191,36,.7)"/>
      <rect x="-5.5" y="-2" width="11" height="8.5" rx="2" fill="#fbbf24"/>
      <path d="M-3.4-2v-2.6a3.4 3.4 0 0 1 6.8 0V-2" fill="none" stroke="#fbbf24" stroke-width="1.8"/>
    </g>
    <!-- drip tray with grille -->
    <rect x="10" y="186" width="96" height="16" rx="6" fill="url(#qcnTray)"/>
    <ellipse cx="58" cy="192" rx="36" ry="3.4" fill="none" stroke="#2a2f38" stroke-width="1.4"/>
    <ellipse cx="58" cy="192" rx="24" ry="2.2" fill="none" stroke="#2a2f38" stroke-width="1.4"/>
    <ellipse cx="58" cy="192" rx="12" ry="1.2" fill="none" stroke="#2a2f38" stroke-width="1.4"/>
    <!-- base -->
    <rect x="6" y="200" width="104" height="14" rx="7" fill="url(#qcnSilver)"/>
  </svg>`;
}

/* ---------------------------------------------------------------- card */

class QcNanoCard extends HTMLElement {
  static getStubConfig() { return {}; }

  setConfig(config) {
    this._config = config || {};
    this._built = false;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 4; }
  getGridOptions() { return { columns: 12, min_columns: 6, rows: 'auto' }; }

  connectedCallback() {
    this._onKey = (e) => this._key(e);
    document.addEventListener('keydown', this._onKey);
  }

  disconnectedCallback() {
    document.removeEventListener('keydown', this._onKey);
    for (const t of Object.values(this._timers || {})) clearTimeout(t);
    this._stopRepeat();
  }

  get t() {
    const lang = (this._hass?.locale?.language || this._hass?.language || 'en').slice(0, 2);
    return TEXT[lang] || TEXT.en;
  }

  get lang() { return this._hass?.locale?.language || this._hass?.language || 'en'; }

  /* ----- entity lookup through translation keys ----- */

  _findEntities() {
    const reg = this._hass.entities || {};
    const devices = new Map();
    for (const [eid, e] of Object.entries(reg)) {
      if (e.platform !== 'qc_nano' || !e.device_id || !e.translation_key) continue;
      if (this._config.device_id && e.device_id !== this._config.device_id) continue;
      if (!devices.has(e.device_id)) devices.set(e.device_id, {});
      const domain = eid.split('.')[0];
      if (KEYS[e.translation_key] === domain) devices.get(e.device_id)[e.translation_key] = eid;
    }
    const [deviceId, map] = devices.entries().next().value || [null, {}];
    return { deviceId, map };
  }

  _st(key) { const id = this._ent[key]; return id ? this._hass.states[id] : undefined; }
  _on(key) { return this._st(key)?.state === 'on'; }
  _num(key) { const v = parseFloat(this._st(key)?.state); return Number.isFinite(v) ? v : null; }
  _avail(key) { const s = this._st(key); return !!s && s.state !== 'unavailable' && s.state !== 'unknown'; }
  _fmt(v, d = 1) { return v === null ? '—' : v.toLocaleString(this.lang, { minimumFractionDigits: d, maximumFractionDigits: d }); }
  _date(key) {
    const s = this._st(key)?.state;
    const d = s ? new Date(s) : null;
    return d && !isNaN(d) ? new Intl.DateTimeFormat(this.lang, { year: 'numeric', month: 'short', day: 'numeric' }).format(d) : '—';
  }

  /* ----- build once, update on every hass change ----- */

  _render() {
    if (!this._hass || !this._config) return;
    const { deviceId, map } = this._findEntities();
    const sig = deviceId + ':' + Object.keys(map).length + ':' + (this._hass.locale?.language || '');
    if (!this._built || sig !== this._sig) {
      this._ent = map;
      this._deviceId = deviceId;
      this._sig = sig;
      this._build();
    }
    this._update();
  }

  _build() {
    const t = this.t;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._pending = {};
    this._timers = {};
    const dev = this._hass.devices?.[this._deviceId];
    const devName = dev?.name_by_user || dev?.name || 'QC nano';
    const title = this._config.title || t.title;
    const embedded = !!this._config.embedded;
    if (!this._deviceId) {
      this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card class="${embedded ? 'embedded' : ''}"><div class="card"><div class="empty">${esc(t.no_device)}</div></div></ha-card>`;
      this._built = true;
      return;
    }
    const portionCol = (kind) => `
      <div class="pc" style="--c:${KIND_COLOR[kind]}">
        <h3><span class="dot" aria-hidden="true"></span>${esc(t[kind])}</h3>
        ${LEVELS.map((lvl) => `
          <div class="pr" data-kind="${kind}" data-level="${lvl}">
            <button class="nm" data-act="pen" aria-pressed="false">${esc(t[lvl])}</button>
            <button class="rb" data-act="pdec" aria-label="${esc(`${t[kind]} ${t[lvl]}: ${t.decrease}`)}"><ha-icon icon="mdi:minus"></ha-icon></button>
            <div class="pv" aria-live="polite"><span>—</span><small>${t.ml}</small></div>
            <button class="rb" data-act="pinc" aria-label="${esc(`${t[kind]} ${t[lvl]}: ${t.increase}`)}"><ha-icon icon="mdi:plus"></ha-icon></button>
          </div>`).join('')}
      </div>`;
    const toggle = (key, icon) => `
      <button class="tb" data-act="toggle" data-key="${key}" aria-pressed="false">
        <ha-icon icon="${icon}"></ha-icon><span>${esc(t[key])}<span class="st"></span></span>
      </button>`;
    this.shadowRoot.innerHTML = `
      <style>${CSS}</style>
      <ha-card class="${embedded ? 'embedded' : ''}">
        <div class="card">
          <div class="head"><ha-icon icon="mdi:water"></ha-icon><span>${esc(title)}</span></div>
          <div class="main" role="button" tabindex="0" aria-haspopup="dialog" aria-label="${esc(t.details)}">
            ${deviceSvg(t)}
            <div class="stats">
              <div class="stat"><div class="l">${esc(t.today)}</div><div class="v" id="vToday">—</div></div>
              <div class="stat"><div class="l">${esc(t.filter)}</div><div class="v" id="vFilter">—</div><div class="s" id="sFilter"></div></div>
              <div class="stat"><div class="l">${esc(t.cooling)}</div><div class="v" id="vCool">—</div></div>
            </div>
          </div>
          <div class="alerts" id="alerts" role="status"></div>
        </div>
      </ha-card>
      <div class="ov" id="ov">
        <div class="dlg" role="dialog" aria-modal="true" aria-labelledby="dTitle">
          <div class="dh">
            <h2 id="dTitle">${esc(title)}<span class="sub">${esc(devName)}</span></h2>
            <span class="badge" id="iCloud"></span><span class="badge" id="iLive"></span>
            <button class="rb" data-act="close" aria-label="${esc(t.close)}"><ha-icon icon="mdi:close"></ha-icon></button>
          </div>
          <div class="row2">
            <div>
              <div class="sec" style="margin-top:0"><div class="t" id="tCool">${esc(t.cooling)}</div>
                <div class="seg" role="group" aria-labelledby="tCool">
                  ${COOLING_MODES.map((m) => `<button class="sb" data-act="mode" data-mode="${m}" aria-pressed="false">
                    <ha-icon icon="${m === 'off' ? 'mdi:power' : m === 'boost' ? 'mdi:snowflake-alert' : 'mdi:snowflake'}"></ha-icon>${esc(t[m])}</button>`).join('')}
                </div>
              </div>
            </div>
            <div>
              <div class="sec" style="margin-top:0"><div class="t" id="tTemp">${esc(t.target)}</div>
                <div class="temp" role="group" aria-labelledby="tTemp">
                  <button class="rb" data-act="tdec" aria-label="${esc(`${t.target}: ${t.decrease}`)}"><ha-icon icon="mdi:minus"></ha-icon></button>
                  <div class="val" id="vTemp" aria-live="polite">—</div>
                  <button class="rb" data-act="tinc" aria-label="${esc(`${t.target}: ${t.increase}`)}"><ha-icon icon="mdi:plus"></ha-icon></button>
                </div>
              </div>
            </div>
          </div>
          <div class="sec"><div class="t">${esc(t.switches)}</div>
            <div class="tg">
              ${toggle('child_lock', 'mdi:lock')}${toggle('light_off', 'mdi:lightbulb-off')}
              ${toggle('energy_saver', 'mdi:leaf')}${toggle('volume_sliders', 'mdi:cup-water')}
            </div>
          </div>
          <div class="sec"><div class="t">${esc(t.portions)}</div>
            <div class="pg">${KINDS.map(portionCol).join('')}</div>
          </div>
          <div class="sec"><div class="t">${esc(t.info)}</div>
            <div class="info">
              <div class="ic"><div class="l">${esc(t.today)}</div><div class="v" id="iToday">—</div><div class="s" id="iTodayS"></div></div>
              <div class="ic"><div class="l">${esc(t.filter_left)}</div><div class="v" id="iFilter">—</div></div>
              <div class="ic"><div class="l">${esc(t.next_filter)}</div><div class="v" id="iNextFilter">—</div></div>
              <div class="ic"><div class="l">${esc(t.next_cleaning)}</div><div class="v" id="iNextClean">—</div></div>
            </div>
          </div>
        </div>
      </div>`;
    const root = this.shadowRoot;
    const main = root.querySelector('.main');
    main.addEventListener('click', () => this._open());
    main.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this._open(); } });
    root.getElementById('ov').addEventListener('click', (e) => { if (e.target.id === 'ov') this._close(); });
    root.querySelector('.dlg').addEventListener('click', (e) => this._click(e));
    for (const ev of ['pointerdown']) root.querySelector('.dlg').addEventListener(ev, (e) => this._press(e));
    for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) root.querySelector('.dlg').addEventListener(ev, () => this._stopRepeat());
    this._built = true;
  }

  _update() {
    if (!this._deviceId || !this.shadowRoot) return;
    const t = this.t, r = this.shadowRoot, $ = (id) => r.getElementById(id);
    const online = this._on('cloud_connection');
    r.querySelector('ha-card').classList.toggle('offline', !online);

    // compact card
    const today = this._num('water_today');
    $('vToday').textContent = today === null ? '—' : `${this._fmt(today, today < 10 ? 2 : 1)} ${t.l}`;
    const fl = this._num('filter_remaining');
    $('vFilter').textContent = fl === null ? '—' : `${this._fmt(fl, 0)} %`;
    $('vFilter').className = 'v ' + (this._on('filter_problem') ? 'mid' : '');
    $('sFilter').textContent = `${t.change}: ${this._date('next_filter_change')}`;
    const mode = this._st('cooling_mode')?.state;
    const temp = this._num('cold_temperature');
    $('vCool').textContent = COOLING_MODES.includes(mode)
      ? (mode === 'off' ? t.off : `${t[mode]} · ${temp === null ? '—' : this._fmt(temp, 0)} ℃`) : '—';

    // drawing
    const open = { hot: this._on('hot_valve'), ambient: this._on('ambient_valve'), cold: this._on('cold_valve') };
    const running = { hot: this._on('heating'), ambient: false, cold: this._on('cooling') };
    for (const g of r.querySelectorAll('svg.dev .b')) {
      const k = g.dataset.kind;
      g.classList.toggle('open', open[k]);
      g.classList.toggle('run', running[k]);
    }
    const flowing = KINDS.find((k) => open[k]);
    const stream = r.querySelector('.stream');
    stream.classList.toggle('on', !!flowing);
    if (flowing) stream.querySelector('.water').setAttribute('stroke', KIND_COLOR[flowing]);
    r.querySelector('.lock').classList.toggle('on', this._on('child_lock'));
    const desc = [flowing ? `${t.dispensing}: ${t[flowing]}` : '', this._on('child_lock') ? t.locked : ''].filter(Boolean).join(', ');
    r.querySelector('.main').setAttribute('aria-label', desc ? `${t.details}. ${desc}` : t.details);

    // alerts
    const alerts = [];
    if (!online) alerts.push(['err', 'mdi:cloud-off-outline', t.alert_offline]);
    if (this._on('filter_problem')) alerts.push(['warn', 'mdi:filter-remove-outline', t.alert_filter]);
    if (this._on('cleaning_problem')) alerts.push(['warn', 'mdi:spray-bottle', t.alert_cleaning]);
    const html = alerts.map(([c, i, txt]) => `<span class="chip ${c}"><ha-icon icon="${i}"></ha-icon>${esc(txt)}</span>`).join('');
    if ($('alerts').innerHTML !== html) $('alerts').innerHTML = html;

    // dialog: cooling mode and temperature
    for (const b of r.querySelectorAll('[data-act="mode"]')) {
      const on = b.dataset.mode === mode;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', String(on));
      b.disabled = !this._avail('cooling_mode');
    }
    if (this._pending.temp !== undefined && this._pending.temp === temp && !this._flushers?.temp) delete this._pending.temp;
    const shownTemp = this._pending.temp ?? temp;
    $('vTemp').textContent = shownTemp === null ? '—' : `${this._fmt(shownTemp, 0)} ℃`;
    r.querySelector('[data-act="tdec"]').disabled = shownTemp === null || shownTemp <= TEMP_MIN;
    r.querySelector('[data-act="tinc"]').disabled = shownTemp === null || shownTemp >= TEMP_MAX;

    // dialog: switches
    for (const b of r.querySelectorAll('[data-act="toggle"]')) {
      const key = b.dataset.key, on = this._on(key);
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', String(on));
      b.disabled = !this._avail(key);
      b.querySelector('.st').textContent = on ? t.enabled : t.disabled;
    }

    // dialog: portions
    for (const row of r.querySelectorAll('.pr')) {
      const base = `${row.dataset.kind}_${row.dataset.level}`;
      const en = this._on(`${base}_enabled`);
      const nm = row.querySelector('.nm');
      nm.classList.toggle('on', en);
      nm.setAttribute('aria-pressed', String(en));
      nm.setAttribute('aria-label', `${t[row.dataset.kind]} ${t[row.dataset.level]}: ${en ? t.enabled : t.disabled}`);
      nm.disabled = !this._avail(`${base}_enabled`);
      if (this._pending[base] !== undefined && this._pending[base] === this._num(`${base}_volume`) && !this._flushers?.[base]) delete this._pending[base];
      const pend = this._pending[base];
      const val = pend ?? this._num(`${base}_volume`);
      const pv = row.querySelector('.pv');
      pv.classList.toggle('pend', pend !== undefined);
      pv.querySelector('span').textContent = val === null ? '—' : this._fmt(val, 0);
      row.querySelector('[data-act="pdec"]').disabled = val === null || val <= PORTION_MIN;
      row.querySelector('[data-act="pinc"]').disabled = val === null || val >= PORTION_MAX;
    }

    // dialog: info
    const parts = ['cold', 'hot', 'ambient'].map((k) => `${t[k]} ${this._fmt(this._num(`${k}_water_today`), 2)}`);
    $('iToday').textContent = today === null ? '—' : `${this._fmt(today, 2)} ${t.l}`;
    $('iTodayS').textContent = today === null ? '' : parts.join(' · ');
    $('iFilter').textContent = fl === null ? '—' : `${this._fmt(fl, 0)} %`;
    $('iNextFilter').textContent = this._date('next_filter_change');
    $('iNextClean').textContent = this._date('next_cleaning');
    for (const [id, key, label] of [['iCloud', 'cloud_connection', t.cloud], ['iLive', 'live_connection', t.live]]) {
      const on = this._on(key);
      $(id).textContent = label;
      $(id).className = 'badge ' + (on ? 'ok' : 'bad');
      $(id).setAttribute('aria-label', `${label}: ${on ? t.connected : t.disconnected}`);
    }
  }

  /* ----- dialog ----- */

  _open() {
    const ov = this.shadowRoot.getElementById('ov');
    this._lastFocus = this.shadowRoot.activeElement || document.activeElement;
    ov.classList.add('open');
    this.shadowRoot.querySelector('[data-act="close"]').focus();
  }

  _close() {
    this._flushAll();
    this.shadowRoot.getElementById('ov').classList.remove('open');
    this.shadowRoot.querySelector('.main')?.focus();
  }

  _isOpen() { return this.shadowRoot?.getElementById('ov')?.classList.contains('open'); }

  _key(e) {
    if (!this._isOpen()) return;
    if (e.key === 'Escape') { e.preventDefault(); this._close(); return; }
    if (e.key !== 'Tab') return;
    const items = [...this.shadowRoot.querySelectorAll('.dlg button:not([disabled])')];
    if (!items.length) return;
    const cur = this.shadowRoot.activeElement;
    const i = items.indexOf(cur);
    if (e.shiftKey && (i <= 0)) { e.preventDefault(); items[items.length - 1].focus(); }
    else if (!e.shiftKey && (i === -1 || i === items.length - 1)) { e.preventDefault(); items[0].focus(); }
  }

  _click(e) {
    const b = e.target.closest('button');
    if (!b || b.disabled) return;
    const act = b.dataset.act;
    if (act === 'close') return this._close();
    if (act === 'mode') return this._call('select', 'select_option', 'cooling_mode', { option: b.dataset.mode });
    if (act === 'toggle') return this._call('switch', 'toggle', b.dataset.key);
    if (act === 'pen') {
      const row = b.closest('.pr');
      return this._call('switch', 'toggle', `${row.dataset.kind}_${row.dataset.level}_enabled`);
    }
    // +/- buttons: a plain click (keyboard, screen reader) steps once;
    // pointer presses are handled in _press with auto-repeat
    if (e.detail === 0) this._step(b);
  }

  _press(e) {
    const b = e.target.closest('button');
    if (!b || b.disabled || !['tdec', 'tinc', 'pdec', 'pinc'].includes(b.dataset.act)) return;
    this._stopRepeat();
    this._step(b);
    this._repeat = setTimeout(() => {
      this._repeat = setInterval(() => { if (!b.disabled) this._step(b); }, 120);
    }, 450);
  }

  _stopRepeat() { clearTimeout(this._repeat); clearInterval(this._repeat); this._repeat = null; }

  _step(b) {
    const act = b.dataset.act;
    if (act === 'tdec' || act === 'tinc') {
      const cur = this._pending.temp ?? this._num('cold_temperature');
      if (cur === null) return;
      const next = Math.min(TEMP_MAX, Math.max(TEMP_MIN, cur + (act === 'tinc' ? 1 : -1)));
      this._pending.temp = next;
      this._debounce('temp', () => this._call('number', 'set_value', 'cold_temperature', { value: next }), 700);
    } else {
      const row = b.closest('.pr');
      const base = `${row.dataset.kind}_${row.dataset.level}`;
      const cur = this._pending[base] ?? this._num(`${base}_volume`);
      if (cur === null) return;
      const next = Math.min(PORTION_MAX, Math.max(PORTION_MIN, cur + (act === 'pinc' ? PORTION_STEP : -PORTION_STEP)));
      this._pending[base] = next;
      this._debounce(base, () => this._call('number', 'set_value', `${base}_volume`, { value: next }), 900);
    }
    this._update();
  }

  // write after the user stopped pressing, so a long press is one cloud call
  _debounce(key, fn, ms) {
    clearTimeout(this._timers[key]);
    this._timers[key] = setTimeout(() => this._flush(key, fn), ms);
    this._flushers = this._flushers || {};
    this._flushers[key] = fn;
  }

  async _flush(key, fn) {
    clearTimeout(this._timers[key]);
    delete this._flushers?.[key];
    try { await fn(); } finally {
      // keep the pending value until the entity reports it, max 15 s
      setTimeout(() => { delete this._pending[key]; this._update(); }, 15000);
    }
  }

  _flushAll() {
    for (const [key, fn] of Object.entries(this._flushers || {})) this._flush(key, fn);
  }

  async _call(domain, service, key, data = {}) {
    const entity_id = this._ent[key];
    if (!entity_id) return;
    try {
      await this._hass.callService(domain, service, { entity_id, ...data });
    } catch (err) {
      this.dispatchEvent(new CustomEvent('hass-notification', {
        detail: { message: `QC nano: ${err?.message || err}` }, bubbles: true, composed: true,
      }));
    }
  }
}

if (!customElements.get('qc-nano-card')) {
  customElements.define('qc-nano-card', QcNanoCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'qc-nano-card',
    name: 'QC nano',
    description: 'Water dispenser card with live state and settings.',
    preview: false,
    documentationURL: 'https://github.com/zoli211/ha-qc-nano',
  });
  console.info(`%c QC-NANO-CARD %c ${QCN_VERSION} `, 'background:#60a5fa;color:#0b1220;font-weight:700', 'background:#1c2333;color:#f3f5f9');
}
