class PowerOffTimelineCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity');
    }
    this.config = config;
    this.selectedTab = 'today'; // 'today' або 'tomorrow'
  }

  set hass(hass) {
    this._hass = hass;

    if (!this.card) {
      this.card = document.createElement('ha-card');
      this.appendChild(this.card);

      // Створюємо кастомний заголовок з перемикачами
      this.headerContainer = document.createElement('div');
      this.headerContainer.style.display = 'flex';
      this.headerContainer.style.alignItems = 'center';
      this.headerContainer.style.justifyContent = 'space-between';
      this.headerContainer.style.padding = '16px 16px 0';
      this.headerContainer.style.width = '100%';
      this.headerContainer.style.boxSizing = 'border-box';
      this.headerContainer.style.minWidth = '0';

      // Створюємо текст заголовка (зліва)
      this.headerText = document.createElement('span');
      this.headerText.style.fontSize = '16px';
      this.headerText.style.fontWeight = '500';
      this.headerText.style.color = 'var(--primary-text-color)';
      this.headerText.style.flexShrink = '1';
      this.headerText.style.minWidth = '0';
      this.headerText.style.overflow = 'hidden';
      this.headerText.style.textOverflow = 'ellipsis';
      this.headerText.style.whiteSpace = 'nowrap';
      this.headerContainer.appendChild(this.headerText);

      // Створюємо контейнер для перемикачів (справа)
      this.daySwitcher = document.createElement('div');
      this.daySwitcher.className = 'day-switcher';
      this.daySwitcher.style.cssText = 'display: flex; align-items: center; gap: 4px; background: var(--card-background-color, #1e1e1e); border-radius: 12px; padding: 2px; flex-shrink: 0;';

      // Створюємо кнопки перемикачів
      this.todayButton = document.createElement('button');
      this.todayButton.className = 'day-switcher-button';
      this.todayButton.setAttribute('data-tab', 'today');
      this.todayButton.setAttribute('title', 'Сьогодні');
      this.todayButton.style.cssText = 'display: grid; place-items: center; width: 32px; height: 32px; border-radius: 10px; cursor: pointer; transition: all 0.2s ease; color: var(--secondary-text-color, #b5b5b5); background: transparent; border: none; padding: 0; margin: 0;';
      const todayIcon = document.createElement('ha-icon');
      todayIcon.setAttribute('icon', 'mdi:calendar-today');
      todayIcon.style.cssText = 'width: 24px; height: 24px; margin: 0; padding: 0; display: block;';
      this.todayButton.appendChild(todayIcon);

      this.tomorrowButton = document.createElement('button');
      this.tomorrowButton.className = 'day-switcher-button';
      this.tomorrowButton.setAttribute('data-tab', 'tomorrow');
      this.tomorrowButton.setAttribute('title', 'Завтра');
      this.tomorrowButton.style.cssText = 'display: grid; place-items: center; width: 32px; height: 32px; border-radius: 10px; cursor: pointer; transition: all 0.2s ease; color: var(--secondary-text-color, #b5b5b5); background: transparent; border: none; padding: 0; margin: 0;';
      const tomorrowIcon = document.createElement('ha-icon');
      tomorrowIcon.setAttribute('icon', 'mdi:calendar-arrow-right');
      tomorrowIcon.style.cssText = 'width: 24px; height: 24px; margin: 0; padding: 0; display: block;';
      this.tomorrowButton.appendChild(tomorrowIcon);

      this.daySwitcher.appendChild(this.todayButton);
      this.daySwitcher.appendChild(this.tomorrowButton);
      this.headerContainer.appendChild(this.daySwitcher);

      // Додаємо обробники подій
      this.todayButton.addEventListener('click', () => {
        if (this.selectedTab !== 'today') {
          this.selectedTab = 'today';
          this.updateTimeline();
        }
      });

      this.tomorrowButton.addEventListener('click', () => {
        if (this.selectedTab !== 'tomorrow') {
          this.selectedTab = 'tomorrow';
          this.updateTimeline();
        }
      });

      this.card.appendChild(this.headerContainer);

      this.content = document.createElement('div');
      this.content.style.padding = '16px';
      this.card.appendChild(this.content);
    }

    this.updateTimeline();
  }

  updateTimeline() {
    const entity = this._hass.states[this.config.entity];
    if (!entity) {
      this.content.innerHTML = '<div>Entity not found</div>';
      return;
    }

    const todayPeriods = entity.attributes.poweroff_periods_today || [];
    const tomorrowPeriods = entity.attributes.poweroff_periods_tomorrow || [];
    const nextOff = entity.attributes.next_off;
    const nextOn = entity.attributes.next_on;
    const now = new Date();

    // Автоматично вибираємо таб: якщо сьогодні немає більше періодів, показуємо завтра
    if (this.selectedTab === 'today' && todayPeriods.length === 0 && tomorrowPeriods.length > 0) {
      // Перевіряємо, чи є ще сьогоднішні події в майбутньому
      const hasFutureToday = todayPeriods.some(period => {
        const endHour = Number(period.end);
        const endTime = new Date(now);
        endTime.setHours(Math.floor(endHour), (endHour % 1) * 60, 0, 0);
        return endTime > now;
      });
      if (!hasFutureToday) {
        this.selectedTab = 'tomorrow';
      }
    }

    // Визначаємо періоди та дату в залежності від вибраного таба
    const periods = this.selectedTab === 'today' ? todayPeriods : tomorrowPeriods;
    const displayDate = new Date(now);
    if (this.selectedTab === 'tomorrow') {
      displayDate.setDate(displayDate.getDate() + 1);
    }

    const pattern = this.buildPattern(periods);
    const currentIndex = this.selectedTab === 'today'
      ? (now.getHours() * 2 + (now.getMinutes() >= 30 ? 1 : 0))
      : -1; // Для завтра не показуємо поточний час

    // Оновлюємо тільки текст заголовка та класи активності (без перестворення HTML)
    const titleText = this.selectedTab === 'today' ? 'Відключення сьогодні' : 'Відключення завтра';
    this.headerText.textContent = titleText;

    // Оновлюємо класи активності для кнопок
    if (this.selectedTab === 'today') {
      this.todayButton.classList.add('active');
      this.tomorrowButton.classList.remove('active');
      this.todayButton.style.background = 'var(--primary-color, #03a9f4)';
      this.todayButton.style.color = 'white';
      this.tomorrowButton.style.background = 'transparent';
      this.tomorrowButton.style.color = 'var(--secondary-text-color, #b5b5b5)';
    } else {
      this.todayButton.classList.remove('active');
      this.tomorrowButton.classList.add('active');
      this.todayButton.style.background = 'transparent';
      this.todayButton.style.color = 'var(--secondary-text-color, #b5b5b5)';
      this.tomorrowButton.style.background = 'var(--primary-color, #03a9f4)';
      this.tomorrowButton.style.color = 'white';
    }

    this.content.innerHTML = `
      <style>
        .day-switcher {
          display: flex;
          align-items: center;
          gap: 4px;
          background: var(--card-background-color, #1e1e1e);
          border-radius: 12px;
          padding: 2px;
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

        .day-switcher-button ha-icon {
          width: 20px;
          height: 20px;
          margin: 0;
          padding: 0;
          display: block;
        }

        .day-switcher-button ha-icon svg {
          display: block;
          width: 100%;
          height: 100%;
          margin: 0;
        }

        .day-switcher-button:hover:not(.active) {
          background: var(--divider-color, rgba(255, 255, 255, 0.1));
          color: var(--primary-text-color);
        }

        .spiral-wrapper {
          display: flex;
          flex-direction: column;
          gap: 12px;
          align-items: center;
          text-align: center;
        }

        .spiral-chart {
          width: 100%;
          max-width: 520px;
        }

        .spiral-segment {
          transition: opacity 0.3s ease;
        }

        .spiral-hour-label {
          font-size: 22px;
          font-weight: 700;
          fill: #0f3547;
        }

        .spiral-center-text {
          font-family: "TT Firs Neue", "Segoe UI", sans-serif;
          fill: #b1b1b1;
          text-anchor: middle;
        }

        .center-queue {
          font-size: 36px;
          font-weight: 700;
          fill: #aab1b6;
        }

        .center-date {
          font-size: 18px;
          font-weight: 600;
        }

        .center-stats {
          font-size: 22px;
          font-weight: 700;
        }

        .center-stats tspan:first-child {
          fill: #cf6f6f;
        }

        .center-stats tspan:last-child {
          fill: #65a46f;
        }

        .legend {
          display: flex;
          gap: 18px;
          font-size: 14px;
          color: var(--secondary-text-color, #b5b5b5);
        }

        .legend-item {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .legend-dot {
          width: 18px;
          height: 18px;
          border-radius: 4px;
        }

        .info-line {
          font-size: 14px;
          color: var(--secondary-text-color, #b5b5b5);
        }
      </style>

      <div class="spiral-wrapper">
        ${this.renderSpiral(pattern, currentIndex, displayDate, entity, this.selectedTab)}
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
        <div class="legend">
          <div>Наступне вимкнення: ${this.formatTime(nextOff)}</div>
          <div>Наступне увімкнення: ${this.formatTime(nextOn)}</div>
        </div>
      </div>
    `;
  }

  buildPattern(periods) {
    const slots = Array(48).fill('1');
    periods.forEach(period => {
      // Використовуємо Math.floor для початку та Math.ceil для кінця,
      // щоб правильно покрити періоди з хвилинами (наприклад, 14:30)
      const startHour = Number(period.start);
      const endHour = Number(period.end);
      const start = Math.max(0, Math.min(48, Math.floor(startHour * 2)));
      const end = Math.max(start, Math.min(48, Math.ceil(endHour * 2)));
      for (let i = start; i < end; i += 1) {
        slots[i] = '0';
      }
    });
    return slots.join('');
  }

  renderSpiral(pattern, currentIndex, displayDate, entity, selectedTab) {
    const SEGMENT_COLORS = {
      0: 'rgb(255 182 193)', // рожевий для відключення
      1: 'rgb(144 238 144)', // світло-зелений для світла
      2: '#ffee5f', // жовтий для переходів
    };
    const ARC_WIDTH = 45;
    const INITIAL_RADIUS = 35;
    const RADIUS_STEP = 2.3;
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
      const isCurrent = selectedTab === 'today' && i === currentIndex;
      // Для обох табів: минулі години мають opacity 0.65, майбутні - 1
      // Для завтрашнього дня всі години в майбутньому, тому opacity = 1 для всіх
      // Для сьогоднішнього: перевіряємо відносно поточного часу
      // Використовуємо однакову логіку opacity для обох табів, щоб кольори виглядали однаково
      const opacity = Math.floor(i / 2) < now.getHours() ? 0.65 : 1;
      const stroke = isCurrent ? `stroke="${SEGMENT_COLORS[slot] || 'rgb(144 238 144)'}" stroke-width="5"` : '';
      return `<path d="${path}" class="spiral-segment" style="fill:${color};opacity:${opacity};" ${stroke}></path>`;
    }).join('');

    const hourLabels = Array.from({length: 24}, (_, hour) => {
      const index = hour * 2;
      const angle = ANGLE_STEP * index;
      const radius = INITIAL_RADIUS + index * RADIUS_STEP + ARC_WIDTH * 1.2 + 10;
      const x = radius * Math.sin(angle);
      const y = radius * -Math.cos(angle);
      return `<text class="spiral-hour-label" x="${x}" y="${y}" dy="0.35em">${hour}</text>`;
    }).join('');

    const centerCircle = '<circle r="120" fill="rgba(22,22,22,0.8)"></circle>';
    const queue = entity.attributes.queue || entity.attributes.group || '1.1';
    const dateStr = displayDate.toLocaleDateString('uk', {weekday: 'short', day: '2-digit', month: '2-digit'});

    const offCount = (pattern.match(/0/g) || []).length / 2;
    const onCount = (pattern.match(/1/g) || []).length / 2;

    return `
      <svg class="spiral-chart" viewBox="0 0 470 470" preserveAspectRatio="xMidYMid meet">
        <g transform="translate(235,235)">
          ${centerCircle}
          ${segments}
          ${hourLabels}
          <text class="spiral-center-text center-queue" x="0" y="-20">${queue} черга</text>
          <text class="spiral-center-text center-date" x="0" y="10">${dateStr}</text>
          <text class="spiral-center-text center-stats" x="0" y="45">
            <tspan>- ${offCount}</tspan>
            <tspan dx="8">+ ${onCount}</tspan>
          </text>
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
  '%c POWEROFF-TIMELINE-CARD %c Version 1.0.0 ',
  'color: white; background: #3a3a38; font-weight: 700;',
  'color: #3a3a38; background: white; font-weight: 700;'
);
