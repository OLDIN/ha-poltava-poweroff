const CARD_VERSION = '1.3.1';

// The card's own font: the same look on any OS/browser (and identical screenshots in tests).
// Inter (SIL OFL 1.1), Latin + Cyrillic only, ~67 KB. The files live next to the card: www/fonts/.
const FONT_FAMILY = 'PoweroffInter';
const FONT_STACK = `"${FONT_FAMILY}", var(--ha-font-family-body, Roboto), system-ui, sans-serif`;
const FONT_BASE = '/local/poltava_poweroff/fonts/';
const FONT_FILES = [
  {
    file: 'inter-latin-wght-normal.woff2',
    unicodeRange: 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD',
  },
  { file: 'inter-cyrillic-wght-normal.woff2', unicodeRange: 'U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116' },
];

/**
 * Browsers ignore @font-face inside shadow DOM (where HA cards live),
 * so the font is registered globally via the FontFace API, once per page.
 */
function loadCardFonts() {
  if (typeof FontFace === 'undefined' || !document.fonts || window.__poweroffFontsLoaded) return;
  window.__poweroffFontsLoaded = true;
  FONT_FILES.forEach(({ file, unicodeRange }) => {
    const face = new FontFace(FONT_FAMILY, `url(${FONT_BASE}${file}) format('woff2')`, {
      weight: '100 900',
      style: 'normal',
      display: 'swap',
      unicodeRange,
    });
    document.fonts.add(face);
    face.load().catch(() => { /* no file: the fallback font from the stack is used */ });
  });
}

// Spiral geometry: shared by the segments and the battery mark (also while it animates).
const SPIRAL = { ARC_WIDTH: 45, INITIAL_RADIUS: 35, RADIUS_STEP: 2.3 };
// How long the battery mark glides to its new spot when the forecast changes.
const BATTERY_MARK_ANIM_MS = 1200;

const QUEUES = ['1.1', '1.2', '2.1', '2.2', '3.1', '3.2', '4.1', '4.2', '5.1', '5.2', '6.1', '6.2'];

const CARD_STYLES = `
  poweroff-timeline-card ha-card { overflow: visible; font-family: ${FONT_STACK}; }
  poweroff-timeline-card button { font-family: inherit; }

  .pot-header {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 16px 16px 0;
    width: 100%;
    box-sizing: border-box;
    min-width: 0;
  }

  .pot-title {
    font-size: 16px;
    font-weight: 500;
    color: var(--primary-text-color);
    flex-shrink: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pot-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

  .day-switcher {
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--card-background-color, #1e1e1e);
    border-radius: 12px;
    padding: 2px;
    flex-shrink: 0;
  }

  .day-switcher-button {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
    color: var(--secondary-text-color, #b5b5b5);
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
  }

  .day-switcher-button.active { background: var(--primary-color, #03a9f4); color: #fff; }
  .day-switcher-button:hover:not(.active) {
    background: var(--divider-color, rgba(255, 255, 255, 0.1));
    color: var(--primary-text-color);
  }
  .day-switcher-button ha-icon { --mdc-icon-size: 22px; display: block; }

  .queue-chip {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 34px;
    padding: 0 8px 0 10px;
    border-radius: 10px;
    border: 1px solid var(--divider-color, #3a3a3a);
    background: var(--secondary-background-color, #262626);
    color: var(--primary-text-color);
    font: inherit;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }
  .queue-chip[hidden] { display: none; }
  .queue-chip.open { border-color: var(--primary-color, #03a9f4); }
  .queue-chip ha-icon { --mdc-icon-size: 18px; color: var(--secondary-text-color, #9e9e9e); }

  .queue-menu {
    position: absolute;
    top: 56px;
    right: 16px;
    z-index: 10;
    width: 268px;
    box-sizing: border-box;
    padding: 12px;
    border-radius: 14px;
    background: var(--card-background-color, #2a2a2a);
    border: 1px solid var(--divider-color, #3a3a3a);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
  }
  .queue-menu[hidden] { display: none; }
  .queue-menu-caption { font-size: 12px; font-weight: 500; color: var(--secondary-text-color, #a8a8a8); margin-bottom: 8px; }
  .queue-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
  .queue-option {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 3px;
    height: 44px;
    border-radius: 10px;
    border: 1px solid var(--divider-color, #333);
    background: transparent;
    color: var(--primary-text-color);
    font: inherit;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }
  .queue-option.home { border-color: var(--secondary-text-color, #6a6a6a); }
  .queue-option.selected { background: var(--primary-color, #03a9f4); border-color: var(--primary-color, #03a9f4); color: #fff; }
  .queue-option ha-icon { --mdc-icon-size: 14px; }
  .queue-menu-hint { display: flex; align-items: center; gap: 6px; margin-top: 10px; font-size: 12px; color: var(--secondary-text-color, #a8a8a8); }
  .queue-menu-hint ha-icon { --mdc-icon-size: 14px; }

  .spiral-wrapper { display: flex; flex-direction: column; gap: 12px; align-items: center; text-align: center; }
  .spiral-chart { width: 100%; max-width: 520px; }
  .spiral-segment { transition: opacity 0.3s ease; }
  .spiral-hour-label { font-size: 24px; font-weight: 900; fill: #0f3547; text-anchor: middle; dominant-baseline: middle; }
  .spiral-chart text { font-family: ${FONT_STACK}; }
  .spiral-center-text { fill: #b1b1b1; text-anchor: middle; }
  .center-queue { font-size: 36px; font-weight: 700; fill: #aab1b6; }
  .center-date { font-size: 18px; font-weight: 600; }
  .center-stats { font-size: 22px; font-weight: 700; }
  .center-stats tspan:first-child { fill: #cf6f6f; }
  .center-stats tspan:last-child { fill: #65a46f; }
  .center-loading { font-size: 18px; font-weight: 500; }

  .legend { display: flex; gap: 4px 18px; flex-wrap: wrap; justify-content: center; font-size: 14px; color: var(--secondary-text-color, #b5b5b5); }
  .legend-item { display: flex; align-items: center; gap: 6px; }
  .legend-dot { width: 18px; height: 18px; border-radius: 4px; }
  .next-line { font-size: 14px; color: var(--secondary-text-color, #b5b5b5); }
  .next-line b { font-weight: 600; color: var(--primary-text-color); white-space: nowrap; }
  .status-chips { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; width: 100%; }
  .chip { flex: 1 1 130px; min-width: 0; display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 10px; text-align: left; background: var(--secondary-background-color, rgba(127, 127, 127, 0.14)); }
  .chip-bar { flex-shrink: 0; width: 4px; height: 30px; border-radius: 2px; }
  .chip b { display: block; font-size: 14px; font-weight: 600; color: var(--primary-text-color); }
  .chip small { display: block; font-size: 12px; color: var(--secondary-text-color, #b5b5b5); }
  .chip.ok small { color: rgb(144 238 144); }
  .chip.short small { color: #ff7f7c; }

  .info-banner, .stale-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    box-sizing: border-box;
    padding: 8px 12px;
    border-radius: 10px;
    font-size: 13px;
    text-align: left;
    color: var(--primary-text-color);
  }
  .info-banner { justify-content: space-between; background: rgba(138, 180, 248, 0.12); border: 1px solid rgba(138, 180, 248, 0.35); }
  .info-banner button {
    border: none;
    background: none;
    color: var(--primary-color, #8ab4f8);
    font: inherit;
    font-weight: 600;
    cursor: pointer;
    padding: 6px 0;
  }
  .stale-banner { align-items: flex-start; background: rgba(255, 167, 38, 0.15); border: 1px solid rgba(255, 167, 38, 0.45); }
  .stale-banner ha-icon { --mdc-icon-size: 18px; color: #ffa726; flex-shrink: 0; }

  .no-data-note { font-size: 13px; color: var(--secondary-text-color, #b5b5b5); }

  .updated-line {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    font-size: 12px;
    color: var(--secondary-text-color, #b5b5b5);
    opacity: 0.85;
    cursor: help;
    border: none;
    background: none;
    font-family: inherit;
    padding: 4px 8px;
  }
  .updated-line .updated-main { display: flex; align-items: center; gap: 6px; }
  .updated-line ha-icon { --mdc-icon-size: 16px; }

  /* Tooltip above the "Графік оновлено" line: hover/focus on desktop, tap on phones */
  .updated-wrap { position: relative; display: inline-flex; justify-content: center; }
  .updated-tooltip {
    position: absolute;
    bottom: calc(100% + 10px);
    left: 50%;
    z-index: 10;
    box-sizing: border-box;
    width: max-content;
    max-width: min(300px, 90vw);
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--secondary-background-color, #2f2f2f);
    border: 1px solid var(--divider-color, #444);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
    color: var(--primary-text-color, #e1e1e1);
    font-size: 12px;
    line-height: 1.5;
    text-align: left;
    pointer-events: none;
    opacity: 0;
    visibility: hidden;
    transform: translate(-50%, 4px);
    transition: opacity 0.15s ease, transform 0.15s ease, visibility 0.15s;
  }
  .updated-tooltip::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -6px;
    border: 6px solid transparent;
    border-top-color: var(--secondary-background-color, #2f2f2f);
  }
  .updated-wrap:hover .updated-tooltip,
  .updated-wrap:focus-within .updated-tooltip,
  .updated-wrap.open .updated-tooltip {
    opacity: 1;
    visibility: visible;
    transform: translate(-50%, 0);
  }
  .tooltip-row { display: flex; align-items: flex-start; gap: 6px; }
  .tooltip-row ha-icon { flex-shrink: 0; margin-top: 1px; }
  .tooltip-row ha-icon { --mdc-icon-size: 14px; color: var(--secondary-text-color, #a8a8a8); }
  .tooltip-row.ok ha-icon { color: #65a46f; }
  .tooltip-row.error { color: #ffb74d; overflow-wrap: anywhere; }
  .tooltip-row.error ha-icon { color: #ffa726; }
`;

// Visual editor (HA's built-in form): labels and hints shown in the card editor
const EDITOR_LABELS = {
  entity: 'Сутність графіка',
  show_queue_switcher: 'Показувати перемикач черг',
  queue_entity: 'Сутність перемикача черг',
  battery_entity: 'Час роботи акумулятора',
  charge_entity: 'Час до повного заряду',
  charge_soc_entity: 'Сенсор заряду, %',
  charge_target: 'Заряджати до, %',
  auto_tomorrow: 'Автоматично перемикати на «Завтра»',
};
const EDITOR_HELPERS = {
  entity: 'Сенсор стану світла з інтеграції Poltava Power Offline (зазвичай sensor.power_state).',
  queue_entity: 'Можна залишити порожнім: картка знайде select.poweroff_view_queue сама.',
  battery_entity:
    'Необов\'язково. Сенсор із залишком часу роботи акумулятора чи ДБЖ (год, хв, с або «Г:ХХ»). '
    + 'Картка покаже червону лінію, коли він сяде.',
  charge_entity:
    'Необов\'язково. Сенсор із часом до повного заряду (год, хв, с, «Г:ХХ», «0h 29m») '
    + 'або з моментом, коли зарядиться (дата й час, device_class: timestamp). '
    + 'Картка покаже синю лінію, коли акумулятор зарядиться.',
  charge_soc_entity:
    'Потрібен, лише якщо заряджати не до 100%: заряд акумулятора у відсотках. '
    + 'Час до повного заряду буде перераховано до вибраної цілі.',
  charge_target:
    'До скількох відсотків заряджати: сутність, наприклад повзунок input_number. '
    + 'Порожньо: 100. Число можна вказати в YAML (charge_target: 80).',
  auto_tomorrow: 'Коли сьогоднішні відключення минули, показувати графік на завтра.',
};

/**
 * Remaining time of a state object, in hours: hours by default, or converted from the entity's unit
 * (min, s, d); "H:MM[:SS]" and "Xh Ym" ("0h 29m", "2h", "45m") strings are accepted too. A moment in time
 * (an ISO timestamp, as a `device_class: timestamp` sensor has) counts as the time left until it, from `now`.
 * null when unknown, or when that moment has passed.
 */
function parseDurationHours(obj, now = new Date()) {
  if (!obj) return null;
  const raw = String(obj.state).trim();
  let hours;
  const moment = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(raw) ? Date.parse(raw.replace(' ', 'T')) : null;
  const clock = raw.match(/^(\d+):(\d{1,2})(?::(\d{1,2}))?$/);
  const words = raw.match(/^(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+(?:\.\d+)?)\s*m(?:in)?)?$/i);
  if (moment !== null) {
    if (Number.isNaN(moment)) return null;
    hours = (moment - now.getTime()) / 3600000;
  } else if (clock) {
    hours = Number(clock[1]) + Number(clock[2]) / 60 + Number(clock[3] || 0) / 3600;
  } else if (words && (words[1] || words[2])) {
    hours = Number(words[1] || 0) + Number(words[2] || 0) / 60;
  } else {
    const value = Number(raw);
    if (raw === '' || !Number.isFinite(value)) return null;
    const unit = String((obj.attributes || {}).unit_of_measurement || 'h').toLowerCase();
    const factor = { s: 1 / 3600, sec: 1 / 3600, min: 1 / 60, m: 1 / 60, d: 24 }[unit] ?? 1;
    hours = value * factor;
  }
  return hours >= 0 ? hours : null;
}

class PowerOffTimelineCard extends HTMLElement {
  /** Default config for the card picker: the integration's state sensor, if there is one. */
  static getStubConfig(hass) {
    const states = (hass && hass.states) || {};
    const found = Object.keys(states).find(
      (id) => id.startsWith('sensor.') && Array.isArray(states[id].attributes?.poweroff_periods_today),
    );
    return { entity: found || 'sensor.power_state' };
  }

  /** Schema for HA's built-in visual editor (no custom editor element needed). */
  static getConfigForm() {
    return {
      schema: [
        { name: 'entity', required: true, selector: { entity: { filter: { integration: 'poltava_poweroff', domain: 'sensor' } } } },
        { name: 'show_queue_switcher', default: true, selector: { boolean: {} } },
        { name: 'queue_entity', selector: { entity: { filter: { integration: 'poltava_poweroff', domain: 'select' } } } },
        { name: 'battery_entity', selector: { entity: { filter: { domain: 'sensor' } } } },
        { name: 'charge_entity', selector: { entity: { filter: { domain: 'sensor' } } } },
        { name: 'charge_soc_entity', selector: { entity: { filter: { domain: 'sensor' } } } },
        { name: 'charge_target', selector: { entity: { filter: { domain: ['input_number', 'number', 'sensor'] } } } },
        { name: 'auto_tomorrow', default: true, selector: { boolean: {} } },
      ],
      computeLabel: (schema) => EDITOR_LABELS[schema.name],
      computeHelper: (schema) => EDITOR_HELPERS[schema.name],
      assertConfig: (config) => {
        if (config.queue_entity === false) {
          // The old YAML way to hide the switcher; the form cannot show `false` in an entity field
          throw new Error('queue_entity: false — замініть на show_queue_switcher: false, щоб редагувати візуально');
        }
      },
    };
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity');
    }
    this.config = config;
    this.selectedTab = 'today'; // 'today' or 'tomorrow'
    this._userPickedTab = false; // after a manual choice the tab is not switched automatically
    this._lastState = undefined;
    this._lastQueueState = undefined;
    this._lastRenderAt = 0;
    this._menuOpen = false;
    this._pendingQueue = null;
    this._showDetails = false;
    this._queueEntityId = null;
    this._lastBatteryState = undefined;
    // In the card editor setConfig is called on every change: redraw the preview right away
    if (this.card && this._hass) this.hass = this._hass;
  }

  /** The "view queue" select entity: from the config or discovered automatically. */
  findQueueEntity(hass) {
    // The result is remembered in _queueEntityId: dataSource() reads the schedule from it
    if (this.config.queue_entity === false || this.config.show_queue_switcher === false) {
      this._queueEntityId = null;
      return null;
    }
    if (this.config.queue_entity) {
      this._queueEntityId = hass.states[this.config.queue_entity] ? this.config.queue_entity : null;
      return this._queueEntityId;
    }
    if (this._queueEntityId && hass.states[this._queueEntityId]) return this._queueEntityId;
    const home = hass.states[this.config.entity]?.attributes?.queue;
    const found = Object.keys(hass.states).find((id) => {
      if (!id.startsWith('select.')) return false;
      const a = hass.states[id].attributes || {};
      return a.home_queue !== undefined && (!home || a.home_queue === home);
    });
    this._queueEntityId = found || null;
    return this._queueEntityId;
  }

  set hass(hass) {
    this._hass = hass;

    // hass is set on EVERY state change of any entity in HA. Re-render only when our
    // entities changed, or once a minute (so the current-time marker moves).
    const stateObj = hass.states[this.config.entity];
    const queueId = this.findQueueEntity(hass);
    const queueObj = queueId ? hass.states[queueId] : undefined;
    const batteryObj = this.config.battery_entity ? hass.states[this.config.battery_entity] : undefined;
    const chargeObjs = this.chargeStates(hass);
    if (
      this.card &&
      stateObj === this._lastState &&
      queueObj === this._lastQueueState &&
      batteryObj === this._lastBatteryState &&
      chargeObjs.length === (this._lastChargeStates || []).length &&
      chargeObjs.every((obj, i) => obj === this._lastChargeStates[i]) &&
      Date.now() - this._lastRenderAt < 60000
    ) {
      return;
    }
    this._lastState = stateObj;
    this._lastQueueState = queueObj;
    this._lastBatteryState = batteryObj;
    this._lastChargeStates = chargeObjs;

    if (!this.card) {
      this.buildSkeleton();
    }

    this.updateTimeline();
  }

  /** State objects the charge mark depends on (sensor, charge level, target when it is an entity), for change detection. */
  chargeStates(hass) {
    const { charge_entity: charge, charge_soc_entity: soc, charge_target: target } = this.config;
    if (!charge) return [];
    return [charge, soc, typeof target === 'string' ? target : undefined].map((id) => (id ? hass.states[id] : undefined));
  }

  buildSkeleton() {
    loadCardFonts();
    this.card = document.createElement('ha-card');
    this.appendChild(this.card);

    this.styleEl = document.createElement('style');
    this.styleEl.textContent = CARD_STYLES;
    this.card.appendChild(this.styleEl);

    this.headerContainer = document.createElement('div');
    this.headerContainer.className = 'pot-header';

    this.headerText = document.createElement('span');
    this.headerText.className = 'pot-title';
    this.headerContainer.appendChild(this.headerText);

    const actions = document.createElement('div');
    actions.className = 'pot-actions';

    // Queue chip (shown only when the select entity exists)
    this.queueChip = document.createElement('button');
    this.queueChip.type = 'button';
    this.queueChip.className = 'queue-chip';
    this.queueChip.setAttribute('aria-haspopup', 'true');
    this.queueChip.setAttribute('aria-expanded', 'false');
    this.queueChip.setAttribute('title', 'Обрати чергу для перегляду');
    this.queueChip.hidden = true;
    this.queueChip.addEventListener('click', (ev) => {
      ev.stopPropagation();
      this.setMenuOpen(!this._menuOpen);
    });
    actions.appendChild(this.queueChip);

    this.daySwitcher = document.createElement('div');
    this.daySwitcher.className = 'day-switcher';
    this.todayButton = this.makeDayButton('today', 'Сьогодні', 'mdi:calendar-today');
    this.tomorrowButton = this.makeDayButton('tomorrow', 'Завтра', 'mdi:calendar-arrow-right');
    this.daySwitcher.appendChild(this.todayButton);
    this.daySwitcher.appendChild(this.tomorrowButton);
    actions.appendChild(this.daySwitcher);
    this.headerContainer.appendChild(actions);

    // Queue picker menu
    this.queueMenu = document.createElement('div');
    this.queueMenu.className = 'queue-menu';
    this.queueMenu.hidden = true;
    this.queueMenu.addEventListener('click', (ev) => ev.stopPropagation());
    this.queueMenu.innerHTML = `
      <div class="queue-menu-caption">Показати графік черги</div>
      <div class="queue-grid">
        ${QUEUES.map((q) => `<button type="button" class="queue-option" data-queue="${q}">${q}</button>`).join('')}
      </div>
      <div class="queue-menu-hint"><ha-icon icon="mdi:home-outline"></ha-icon><span>ваша черга — сенсори й автоматизації завжди по ній</span></div>`;
    this.queueMenu.querySelectorAll('.queue-option').forEach((btn) => {
      btn.addEventListener('click', () => this.selectQueue(btn.dataset.queue));
    });
    this.headerContainer.appendChild(this.queueMenu);

    this._outsideClick = () => this.setMenuOpen(false);

    this.card.appendChild(this.headerContainer);

    this.content = document.createElement('div');
    this.content.style.padding = '16px';
    this.content.addEventListener('click', (ev) => {
      const target = ev.target.closest && ev.target.closest('[data-action]');
      if (!target) return;
      if (target.dataset.action === 'go-home') this.selectQueue(this._homeQueue);
      if (target.dataset.action === 'toggle-details') {
        this._showDetails = !this._showDetails;
        this.updateTimeline();
      }
    });
    this.card.appendChild(this.content);
  }

  makeDayButton(tab, title, icon) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'day-switcher-button';
    button.setAttribute('data-tab', tab);
    button.setAttribute('title', title);
    button.setAttribute('aria-label', title);
    const iconEl = document.createElement('ha-icon');
    iconEl.setAttribute('icon', icon);
    button.appendChild(iconEl);
    button.addEventListener('click', () => {
      this._userPickedTab = true;
      if (this.selectedTab !== tab) {
        this.selectedTab = tab;
        this.updateTimeline();
      }
    });
    return button;
  }

  setMenuOpen(open) {
    this._menuOpen = open;
    if (!this.queueMenu) return;
    this.queueMenu.hidden = !open;
    this.queueChip.classList.toggle('open', open);
    this.queueChip.setAttribute('aria-expanded', String(open));
    if (open) {
      document.addEventListener('click', this._outsideClick);
    } else {
      document.removeEventListener('click', this._outsideClick);
    }
  }

  disconnectedCallback() {
    if (this._outsideClick) document.removeEventListener('click', this._outsideClick);
  }

  selectQueue(queue) {
    this.setMenuOpen(false);
    const entityId = this._queueEntityId;
    if (!entityId || !queue) return;
    const current = this._hass.states[entityId];
    if (current && current.state === queue) return;
    this._pendingQueue = queue;
    this.updateTimeline();
    this._hass.callService('select', 'select_option', { entity_id: entityId, option: queue });
  }

  /** Where the schedule comes from: the select (view queue) or the sensor itself (old behaviour). */
  dataSource() {
    const sensor = this._hass.states[this.config.entity];
    const queueObj = this._queueEntityId ? this._hass.states[this._queueEntityId] : undefined;
    return { sensor, queueObj, source: queueObj || sensor };
  }

  updateTimeline() {
    this._lastRenderAt = Date.now();
    const { sensor, queueObj, source: entity } = this.dataSource();
    if (!sensor || !entity) {
      this.content.innerHTML = '<div>Entity not found</div>';
      return;
    }

    const attrs = entity.attributes || {};
    this._homeQueue = queueObj ? queueObj.attributes.home_queue : attrs.queue;
    const viewQueue = queueObj ? queueObj.state : attrs.queue;
    if (this._pendingQueue && viewQueue === this._pendingQueue && !attrs.loading) {
      this._pendingQueue = null;
    }
    const loading = Boolean(this._pendingQueue || attrs.loading);
    const shownQueue = this._pendingQueue || viewQueue;

    const todayPeriods = loading ? [] : attrs.poweroff_periods_today || [];
    const tomorrowPeriods = loading ? [] : attrs.poweroff_periods_tomorrow || [];
    const nextOff = attrs.next_off;
    const nextOn = attrs.next_on;
    const now = new Date();

    // Show tomorrow automatically when today's outages are over (or there are none)
    // and tomorrow has a schedule. Once the user picked a tab manually, leave it alone.
    if (!this._userPickedTab && this.config.auto_tomorrow !== false && tomorrowPeriods.length > 0) {
      const nowHours = now.getHours() + now.getMinutes() / 60;
      const hasFutureToday = todayPeriods.some((period) => {
        const end = Number(period.end) === 0 ? 24 : Number(period.end);
        return end > nowHours;
      });
      this.selectedTab = hasFutureToday ? 'today' : 'tomorrow';
    }

    const periods = this.selectedTab === 'today' ? todayPeriods : tomorrowPeriods;
    const displayDate = new Date(now);
    if (this.selectedTab === 'tomorrow') {
      displayDate.setDate(displayDate.getDate() + 1);
    }

    const pattern = this.buildPattern(periods);
    const currentIndex = this.selectedTab === 'today'
      ? (now.getHours() * 2 + (now.getMinutes() >= 30 ? 1 : 0))
      : -1;

    // Short title: on a narrow card it shares the row with the queue chip and day switcher
    const isTodayTab = this.selectedTab === 'today';
    this.headerText.textContent = isTodayTab ? 'Сьогодні' : 'Завтра';
    this.headerText.title = isTodayTab ? 'Відключення сьогодні' : 'Відключення завтра';
    this.todayButton.classList.toggle('active', this.selectedTab === 'today');
    this.tomorrowButton.classList.toggle('active', this.selectedTab === 'tomorrow');

    // Queue chip and menu
    this.queueChip.hidden = !queueObj;
    if (queueObj) {
      const isHome = shownQueue === this._homeQueue;
      this.queueChip.innerHTML = `${isHome ? '<ha-icon icon="mdi:home-outline"></ha-icon>' : ''}<span>${this.escape(shownQueue)}</span><ha-icon icon="mdi:chevron-down"></ha-icon>`;
      this.queueMenu.querySelectorAll('.queue-option').forEach((btn) => {
        const q = btn.dataset.queue;
        btn.classList.toggle('selected', q === shownQueue);
        btn.classList.toggle('home', q === this._homeQueue);
        btn.setAttribute('aria-pressed', String(q === shownQueue));
        btn.setAttribute('aria-label', `Черга ${q}${q === this._homeQueue ? ', ваша' : ''}`);
        btn.innerHTML = `${q === this._homeQueue ? '<ha-icon icon="mdi:home-outline"></ha-icon>' : ''}${q}`;
      });
    }

    // The battery powers the home, so it is shown only for the home queue.
    const battery = !loading && shownQueue === this._homeQueue
      ? this.batteryForecast(now, (sensor.attributes || {}).next_on)
      : null;
    // The "battery empty" mark goes on the tab of the day the battery runs out.
    const batteryMark = battery && battery.until.toDateString() === displayDate.toDateString() ? battery : null;
    // Charging: the blue mark goes on the tab of the day it finishes; the "light until" comparison needs the power on.
    const powerOn = /^(on|power on)$/i.test(String(sensor.state).trim());
    const charge = !loading && this.config.charge_entity && shownQueue === this._homeQueue
      ? this.chargeForecast(now, (sensor.attributes || {}).next_off, powerOn)
      : null;
    const chargeMark = charge && charge.done.toDateString() === displayDate.toDateString() ? charge : null;

    const viewEntity = { ...entity, attributes: { ...attrs, queue: shownQueue } };
    this.content.innerHTML = `
      <div class="spiral-wrapper">
        ${this.renderViewBanner(queueObj, shownQueue)}
        ${loading ? '' : this.renderStaleBanner(entity)}
        ${this.renderSpiral(pattern, currentIndex, displayDate, viewEntity, this.selectedTab, loading, batteryMark, chargeMark)}
        ${loading ? '' : this.renderNoDataNote(entity)}
        <div class="legend">
          <div class="legend-item">
            <span class="legend-dot" style="background:rgb(255 182 193);"></span>
            <span>Відключення</span>
          </div>
          <div class="legend-item">
            <span class="legend-dot" style="background:rgb(144 238 144);"></span>
            <span>Світло є</span>
          </div>
        </div>
        ${battery || charge
          ? this.renderStatusChips(nextOff, nextOn, battery, charge)
          : `<div class="next-line">${this.renderNextLine(nextOff, nextOn, loading)}</div>`}
        ${loading ? this.renderLoadingLine(shownQueue) : this.renderUpdatedLine(entity)}
      </div>
    `;
    this.animateBatteryMark();
  }

  buildPattern(periods) {
    const slots = Array(48).fill('1');
    periods.forEach((period) => {
      const startHour = Number(period.start);
      let endHour = Number(period.end);
      // end == 0 means the end of the day (24:00)
      if (endHour === 0 || endHour >= 24) {
        endHour = 24;
      }
      const start = Math.max(0, Math.min(48, Math.floor(startHour * 2)));
      const end = Math.max(start, Math.min(48, Math.ceil(endHour * 2)));
      for (let i = start; i < end; i += 1) {
        slots[i] = '0';
      }
    });
    return slots.join('');
  }

  /**
   * Battery runtime from `battery_entity`: hours by default, or converted from the
   * entity's unit (min, s, d); "H:MM[:SS]" strings are accepted too. null when unknown.
   */
  batteryHours() {
    const id = this.config.battery_entity;
    return parseDurationHours(id && this._hass.states[id]);
  }

  /** Percent the battery is charged to: `charge_target` (number or entity), 100 when missing or invalid. */
  chargeTarget() {
    const cfg = this.config.charge_target;
    if (cfg === undefined || cfg === null || cfg === '') return 100;
    let value = Number(cfg);
    if (Number.isNaN(value) && typeof cfg === 'string') {
      const obj = this._hass.states[cfg];
      value = obj ? Number(String(obj.state).trim() || NaN) : NaN;
    }
    return Number.isFinite(value) && value > 0 && value <= 100 ? value : 100;
  }

  /**
   * When charging finishes, from `charge_entity` (time to full). A target below 100% scales it by
   * the remaining percent, which needs `charge_soc_entity`. null when there is nothing to show:
   * no/unavailable sensor, zero time, a "time to empty" label (discharging) or already at the target.
   * `until` is the next power-off, used only while the power is on; `ok` says whether charging ends before it.
   */
  chargeForecast(now, nextOffIso, powerOn) {
    const states = this._hass.states;
    const id = this.config.charge_entity;
    const obj = id && states[id];
    if (!obj || /empty/i.test(String((obj.attributes || {}).label ?? ''))) return null;
    const toFull = parseDurationHours(obj, now);
    if (toFull === null || toFull <= 0) return null;

    let target = this.chargeTarget();
    let hours = toFull;
    if (target < 100) {
      const socObj = this.config.charge_soc_entity && states[this.config.charge_soc_entity];
      const raw = socObj ? String(socObj.state).trim() : '';
      const soc = raw === '' ? NaN : Number(raw);
      if (Number.isFinite(soc)) {
        if (soc >= target) return null;
        hours = (toFull * (target - soc)) / (100 - soc);
      } else {
        target = 100; // no readable charge level: the sensor's own time (to 100%) is all we have
      }
    }

    const done = new Date(now.getTime() + hours * 3600000);
    const off = nextOffIso ? new Date(nextOffIso) : null;
    const until = powerOn && off && !Number.isNaN(off.getTime()) && off > now ? off : null;
    return { hours, done, target, until, ok: until ? done <= until : null };
  }

  /** Until when the battery lasts and whether that covers the next power-on (end of the next/current outage). */
  batteryForecast(now, nextOnIso) {
    const hours = this.batteryHours();
    if (hours === null) return null;
    const until = new Date(now.getTime() + hours * 3600000);
    const target = nextOnIso ? new Date(nextOnIso) : null;
    const validTarget = target && !Number.isNaN(target.getTime()) && target > now ? target : null;
    return { hours, now, until, target: validTarget, ok: !validTarget || until >= validTarget };
  }

  /** Coordinates of the battery mark at `hours` (0..24) on the spiral. */
  batteryMarkGeometry(hours) {
    const { ARC_WIDTH, INITIAL_RADIUS, RADIUS_STEP } = SPIRAL;
    // Same geometry as the segments: two 12-hour turns, the band's inner radius grows by RADIUS_STEP per half hour
    const angle = (hours * Math.PI * 2) / 12;
    const inner = INITIAL_RADIUS + hours * 2 * RADIUS_STEP + ARC_WIDTH - 4;
    const outer = inner + ARC_WIDTH + 8;
    const x = (r) => (r * Math.sin(angle)).toFixed(2);
    const y = (r) => (r * -Math.cos(angle)).toFixed(2);
    return { x1: x(inner), y1: y(inner), x2: x(outer), y2: y(outer) };
  }

  /** Red radial line across the spiral band at the moment the battery runs out. */
  renderBatteryMark(until) {
    const hours = until.getHours() + until.getMinutes() / 60;
    const g = this.batteryMarkGeometry(hours);
    const line = `x1="${g.x1}" y1="${g.y1}" x2="${g.x2}" y2="${g.y2}" stroke-linecap="round"`;
    return `
      <g class="battery-mark" data-hours="${hours.toFixed(4)}">
        <line ${line} stroke="rgba(0,0,0,0.55)" stroke-width="8"></line>
        <line ${line} stroke="#e53935" stroke-width="4"></line>
        <circle cx="${g.x2}" cy="${g.y2}" r="5" fill="#e53935" stroke="rgba(0,0,0,0.55)" stroke-width="2"></circle>
      </g>
    `;
  }

  /** Blue radial line across the spiral band at the moment the battery finishes charging. */
  renderChargeMark(done) {
    const g = this.batteryMarkGeometry(done.getHours() + done.getMinutes() / 60);
    const line = `x1="${g.x1}" y1="${g.y1}" x2="${g.x2}" y2="${g.y2}" stroke-linecap="round"`;
    return `
      <g class="charge-mark">
        <line ${line} stroke="rgba(0,0,0,0.55)" stroke-width="8"></line>
        <line ${line} stroke="#1e88e5" stroke-width="4"></line>
        <circle cx="${g.x2}" cy="${g.y2}" r="5" fill="#1e88e5" stroke="rgba(0,0,0,0.55)" stroke-width="2"></circle>
      </g>
    `;
  }

  /**
   * The card re-renders via innerHTML, so a CSS transition can't move the mark, and it
   * travels along a spiral anyway (not a circle). Instead: draw it at the previously shown
   * spot and glide the hour value to the new one, recomputing the geometry every frame.
   */
  animateBatteryMark() {
    if (this._markAnim) cancelAnimationFrame(this._markAnim);
    this._markAnim = null;
    const mark = this.content.querySelector('.battery-mark');
    if (!mark) {
      this._markHours = null;
      return;
    }
    const target = Number(mark.dataset.hours);
    const from = this._markHours;
    const canAnimate =
      typeof requestAnimationFrame === 'function' &&
      !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    if (from == null || !canAnimate || Math.abs(target - from) < 0.01) {
      this._markHours = target;
      return;
    }

    const lines = mark.querySelectorAll('line');
    const dot = mark.querySelector('circle');
    const place = (hours) => {
      const g = this.batteryMarkGeometry(hours);
      lines.forEach((l) => {
        l.setAttribute('x1', g.x1); l.setAttribute('y1', g.y1);
        l.setAttribute('x2', g.x2); l.setAttribute('y2', g.y2);
      });
      dot.setAttribute('cx', g.x2); dot.setAttribute('cy', g.y2);
      this._markHours = hours;
    };
    const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    const start = performance.now();
    place(from);
    const step = (ts) => {
      const t = Math.min(1, (ts - start) / BATTERY_MARK_ANIM_MS);
      place(from + (target - from) * ease(t));
      this._markAnim = t < 1 ? requestAnimationFrame(step) : null;
    };
    this._markAnim = requestAnimationFrame(step);
  }

  /** "45 хв", "2 год", "1 год 30 хв": a span of time, rounded to minutes. */
  formatSpan(ms) {
    const total = Math.round(Math.abs(ms) / 60000);
    if (total < 60) return `${total} хв`;
    const hours = Math.floor(total / 60);
    const minutes = total % 60;
    return minutes ? `${hours} год ${minutes} хв` : `${hours} год`;
  }

  /**
   * Chips under the legend when a battery or charge sensor is set: the next outage, when charging
   * finishes and when the battery runs out. The coloured bar of a chip is the key for its mark on the spiral.
   * The small line says whether it fits: green with a margin, red with how much is missing.
   */
  renderStatusChips(nextOff, nextOn, battery, charge) {
    const next = this.nextEvent(nextOff, nextOn);
    const chip = (kind, color, big, small, state = '') =>
      `<div class="chip chip-${kind}${state ? ` ${state}` : ''}"><i class="chip-bar" style="background:${color}"></i><div><b>${big}</b><small>${small}</small></div></div>`;
    const chips = [chip('next', next.kind === 'on' ? 'rgb(144 238 144)' : 'rgb(255 182 193)', next.value, next.label)];
    if (charge) {
      const small = charge.ok === null
        ? 'зарядка'
        : charge.ok
          ? `запас ${this.formatSpan(charge.until - charge.done)}`
          : `не вистачає ${this.formatSpan(charge.done - charge.until)}`;
      const state = charge.ok === null ? '' : charge.ok ? 'ok' : 'short';
      chips.push(chip('charge', '#1e88e5', `${Math.round(charge.target)}% о ${this.formatWhen(charge.done)}`, small, state));
    }
    if (battery) {
      if (battery.hours >= 24 && battery.ok) {
        chips.push(chip('battery', '#e53935', 'понад добу', 'заряду вистачить', 'ok'));
      } else {
        const big = `сяде о ${this.formatWhen(battery.until)}`;
        if (!battery.target) {
          chips.push(chip('battery', '#e53935', big, 'заряду вистачить', 'ok'));
        } else if (battery.ok) {
          chips.push(chip('battery', '#e53935', big, `запас ${this.formatSpan(battery.until - battery.target)}`, 'ok'));
        } else {
          chips.push(chip('battery', '#e53935', big, `не вистачає ${this.formatSpan(battery.target - battery.until)}`, 'short'));
        }
      }
    }
    return `<div class="status-chips">${chips.join('')}</div>`;
  }

  /** "HH:MM", with "завтра" (tomorrow) in front when the moment is not today. */
  formatWhen(date) {
    return `${this.isTomorrow(date) ? 'завтра ' : ''}${this.formatTime(date.toISOString())}`;
  }

  renderSpiral(pattern, currentIndex, displayDate, entity, selectedTab, loading = false, battery = null, charge = null) {
    const SEGMENT_COLORS = {
      0: 'rgb(255 182 193)', // pink: outage
      1: 'rgb(144 238 144)', // light green: power on
      2: '#ffee5f', // yellow: transitions
    };
    const { ARC_WIDTH, INITIAL_RADIUS, RADIUS_STEP } = SPIRAL;
    const ANGLE_STEP = (Math.PI * 2) / 24;
    const now = new Date();

    const segments = Array.from({length: 48}, (_, i) => {
      const startAngle = ANGLE_STEP * i;
      const endAngle = ANGLE_STEP * (i + 1);
      const startRadius = INITIAL_RADIUS + i * RADIUS_STEP + ARC_WIDTH;
      const endRadius = INITIAL_RADIUS + (i + 1) * RADIUS_STEP + ARC_WIDTH;
      const path = this.createSpiralPath(startRadius, endRadius, ARC_WIDTH, startAngle, endAngle);
      const slot = parseInt(pattern[i], 10);
      const color = SEGMENT_COLORS[slot] || SEGMENT_COLORS[1];
      const isCurrent = selectedTab === 'today' && i === currentIndex && !loading;
      // Dim past hours only for today; for tomorrow everything is still ahead
      let opacity = selectedTab === 'today' && Math.floor(i / 2) < now.getHours() ? 0.65 : 1;
      if (loading) opacity = 0.3;
      const stroke = isCurrent ? `stroke="${SEGMENT_COLORS[slot] || 'rgb(144 238 144)'}" stroke-width="5"` : '';
      return `<path d="${path}" class="spiral-segment" style="fill:${color};opacity:${opacity};" ${stroke}></path>`;
    }).join('');

    const hourLabels = Array.from({length: 24}, (_, hour) => {
      const index = hour * 2;
      const angle = ANGLE_STEP * index;
      const radius = INITIAL_RADIUS + index * RADIUS_STEP + ARC_WIDTH * 1.2 + 10;
      const x = radius * Math.sin(angle);
      const y = radius * -Math.cos(angle);
      return `<text class="spiral-hour-label" x="${x}" y="${y}">${hour}</text>`;
    }).join('');

    const centerCircle = '<circle r="120" fill="rgba(22,22,22,0.8)"></circle>';
    const queue = entity.attributes.queue || entity.attributes.group || '1.1';
    const dateStr = displayDate.toLocaleDateString('uk', {weekday: 'short', day: '2-digit', month: '2-digit'});

    const offCount = (pattern.match(/0/g) || []).length / 2;
    const onCount = (pattern.match(/1/g) || []).length / 2;
    const stats = loading
      ? '<text class="spiral-center-text center-loading" x="0" y="45">оновлюю…</text>'
      : `<text class="spiral-center-text center-stats" x="0" y="45">
            <tspan>- ${offCount}</tspan>
            <tspan dx="8">+ ${onCount}</tspan>
          </text>`;

    return `
      <svg class="spiral-chart" viewBox="0 0 470 470" preserveAspectRatio="xMidYMid meet">
        <g transform="translate(235,235)">
          ${centerCircle}
          ${segments}
          ${hourLabels}
          ${battery ? this.renderBatteryMark(battery.until) : ''}
          ${charge ? this.renderChargeMark(charge.done) : ''}
          <text class="spiral-center-text center-queue" x="0" y="-20">${this.escape(queue)} черга</text>
          <text class="spiral-center-text center-date" x="0" y="10">${dateStr}</text>
          ${stats}
        </g>
      </svg>
    `;
  }

  createSpiralPath(startRadius, endRadius, width, startAngle, endAngle) {
    const x1 = startRadius * Math.sin(startAngle);
    const y1 = startRadius * -Math.cos(startAngle);
    const x2 = (startRadius + width) * Math.sin(startAngle);
    const y2 = (startRadius + width) * -Math.cos(startAngle);
    const x3 = endRadius * Math.sin(endAngle);
    const y3 = endRadius * -Math.cos(endAngle);
    const x4 = (endRadius + width) * Math.sin(endAngle);
    const y4 = (endRadius + width) * -Math.cos(endAngle);

    return `
      M ${x1},${y1}
      L ${x2},${y2}
      A ${startRadius},${startRadius} 1 0 1 ${x4},${y4}
      L ${x3},${y3}
      A ${startRadius},${startRadius} 0 0 0 ${x1},${y1}
    `;
  }

  /**
   * One line instead of two:
   *   "Наступне відключення: 09:00 – 11:00" (next outage) while power is on;
   *   "Світло з'явиться о 11:00" (power returns at) while it is off;
   *   "завтра" (tomorrow) before the time when the event is not today.
   */
  renderNextLine(nextOff, nextOn, loading) {
    if (loading) {
      return 'Наступне відключення: …';
    }
    return this.nextEvent(nextOff, nextOn).line;
  }

  /** The next event as { kind, label, value, line }: `line` is the sentence, `label` and `value` feed a chip. */
  nextEvent(nextOff, nextOn) {
    const off = nextOff ? new Date(nextOff) : null;
    const on = nextOn ? new Date(nextOn) : null;
    const valid = (d) => d && !Number.isNaN(d.getTime());
    const when = (d) => this.formatWhen(d);
    if (valid(on) && (!valid(off) || on < off)) {
      return { kind: 'on', label: 'Світло з\'явиться', value: when(on), line: `Світло з'явиться о <b>${when(on)}</b>` };
    }
    if (valid(off) && valid(on)) {
      const sameDay = off.toDateString() === on.toDateString();
      const value = `${when(off)} – ${sameDay ? this.formatTime(on.toISOString()) : when(on)}`;
      return { kind: 'off', label: 'Наступне відключення', value, line: `Наступне відключення: <b>${value}</b>` };
    }
    if (valid(off)) {
      return { kind: 'off', label: 'Наступне відключення', value: when(off), line: `Наступне відключення: <b>${when(off)}</b>` };
    }
    return { kind: 'off', label: 'Найближчі відключення', value: 'немає', line: 'Найближчих відключень немає' };
  }

  isTomorrow(date) {
    const t = new Date();
    t.setDate(t.getDate() + 1);
    return date.toDateString() === t.toDateString();
  }

  renderViewBanner(queueObj, shownQueue) {
    if (!queueObj || !this._homeQueue || shownQueue === this._homeQueue) {
      return '';
    }
    return `
      <div class="info-banner">
        <span>Перегляд черги ${this.escape(shownQueue)} · ваша — ${this.escape(this._homeQueue)}</span>
        <button type="button" data-action="go-home">Повернутись</button>
      </div>`;
  }

  renderStaleBanner(entity) {
    const attrs = entity.attributes || {};
    if (!attrs.data_stale) {
      return '';
    }
    const checked = this.formatTime(attrs.last_attempt_at);
    const ok = this.formatDateTime(attrs.last_success_at);
    return `
      <div class="stale-banner" title="${this.escape(attrs.last_error || '')}">
        <ha-icon icon="mdi:cloud-off-outline"></ha-icon>
        <div>Сайт графіків зараз недоступний — показано збережений графік.
          Остання вдала перевірка ${ok}, спроба о ${checked}.</div>
      </div>`;
  }

  renderNoDataNote(entity) {
    const attrs = entity.attributes || {};
    const key = this.selectedTab === 'today' ? 'today_known' : 'tomorrow_known';
    if (attrs[key] !== false) {
      return '';
    }
    const text = this.selectedTab === 'today'
      ? 'Графіка на сьогодні немає на сайті'
      : 'Графік на завтра ще не опубліковано';
    return `<div class="no-data-note">${text}</div>`;
  }

  renderLoadingLine(queue) {
    return `
      <div class="updated-line">
        <span class="updated-main"><ha-icon icon="mdi:sync"></ha-icon><span>Завантажую графік черги ${this.escape(queue)}…</span></span>
      </div>`;
  }

  /**
   * "Графік оновлено …" (schedule updated): when the schedule last CHANGED.
   * The tooltip (hover / focus / tap) shows the last successful site check, the last attempt and the error.
   */
  renderUpdatedLine(entity) {
    const attrs = entity.attributes || {};
    const changed = attrs.schedule_changed_at;
    if (!changed) {
      return '';
    }
    const rows = [
      `<div class="tooltip-row ok"><ha-icon icon="mdi:cloud-check-outline"></ha-icon><span>Дані з сайту отримано: ${this.formatDateTime(attrs.last_success_at)}</span></div>`,
    ];
    if (attrs.last_attempt_at && attrs.last_attempt_at !== attrs.last_success_at) {
      rows.push(`<div class="tooltip-row"><ha-icon icon="mdi:history"></ha-icon><span>Остання спроба: ${this.formatDateTime(attrs.last_attempt_at)}</span></div>`);
    }
    if (attrs.last_error) {
      rows.push(`<div class="tooltip-row error"><ha-icon icon="mdi:alert-circle-outline"></ha-icon><span>${this.escape(attrs.last_error)}</span></div>`);
    }
    return `
      <div class="updated-wrap${this._showDetails ? ' open' : ''}">
        <button type="button" class="updated-line" data-action="toggle-details" aria-describedby="pot-updated-tooltip" aria-expanded="${this._showDetails}">
          <span class="updated-main"><ha-icon icon="mdi:calendar-sync"></ha-icon><span>Графік оновлено ${this.formatDateTime(changed)}</span></span>
        </button>
        <div class="updated-tooltip" id="pot-updated-tooltip" role="tooltip">${rows.join('')}</div>
      </div>`;
  }

  formatDateTime(value) {
    if (!value) {
      return '—';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return '—';
    }
    const time = this.formatTime(value);
    const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const days = Math.round((startOfDay(new Date()) - startOfDay(date)) / 86400000);
    if (days === 0) return `сьогодні о ${time}`;
    if (days === 1) return `вчора о ${time}`;
    const dm = date.toLocaleDateString('uk', {day: '2-digit', month: '2-digit'});
    return `${dm} о ${time}`;
  }

  escape(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  }

  formatTime(value) {
    if (!value) {
      return '—';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return '—';
    }
    return date.toLocaleTimeString('uk', {hour: '2-digit', minute: '2-digit'});
  }

  getCardSize() {
    return 3;
  }
}

if (!customElements.get('poweroff-timeline-card')) {
  customElements.define('poweroff-timeline-card', PowerOffTimelineCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'poweroff-timeline-card',
    name: 'Power Off Timeline Card',
    description: 'Відображає графік відключень електроенергії',
    preview: true,
    documentationURL: 'https://github.com/OLDIN/ha-poltava-poweroff',
  });
  console.info(
    `%c POWEROFF-TIMELINE-CARD %c Version ${CARD_VERSION} `,
    'color: white; background: #3a3a38; font-weight: 700;',
    'color: #3a3a38; background: white; font-weight: 700;'
  );
}
