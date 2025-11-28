class PowerOffTimelineCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity');
    }
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;

    if (!this.card) {
      this.card = document.createElement('ha-card');
      this.card.header = this.config.title || 'Відключення сьогодні';
      this.appendChild(this.card);

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

    const periods = entity.attributes.poweroff_periods || [];
    const nextOff = entity.attributes.next_off;
    const nextOn = entity.attributes.next_on;
    const now = new Date();

    const pattern = this.buildPattern(periods);
    const currentIndex = now.getHours() * 2 + (now.getMinutes() >= 30 ? 1 : 0);

    this.content.innerHTML = `
      <style>
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
        ${this.renderSpiral(pattern, currentIndex, now, entity)}
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

  renderSpiral(pattern, currentIndex, now, entity) {
    const SEGMENT_COLORS = {
      0: 'rgb(255 182 193)', // рожевий для відключення
      1: 'rgb(144 238 144)', // світло-зелений для світла
      2: '#ffee5f', // жовтий для переходів
    };
    const ARC_WIDTH = 45;
    const INITIAL_RADIUS = 35;
    const RADIUS_STEP = 2.3;
    const ANGLE_STEP = (Math.PI * 2) / 24;

    const segments = Array.from({length: 48}, (_, i) => {
      const startAngle = ANGLE_STEP * i;
      const endAngle = ANGLE_STEP * (i + 1);
      const startRadius = INITIAL_RADIUS + i * RADIUS_STEP + ARC_WIDTH;
      const endRadius = INITIAL_RADIUS + (i + 1) * RADIUS_STEP + ARC_WIDTH;
      const path = this.createSpiralPath(startRadius, endRadius, ARC_WIDTH, startAngle, endAngle);
      const slot = parseInt(pattern[i], 10);
      const color = SEGMENT_COLORS[slot] || SEGMENT_COLORS[1];
      const isCurrent = i === currentIndex;
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
    const dateStr = now.toLocaleDateString('uk', {weekday: 'short', day: '2-digit', month: '2-digit'});

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
