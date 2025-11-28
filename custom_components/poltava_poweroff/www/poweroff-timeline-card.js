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

    // Отримуємо періоди відключень з атрибутів
    const periods = entity.attributes.poweroff_periods || [];
    const now = new Date();
    const currentHour = now.getHours();
    const currentMinutes = now.getMinutes();

    this.content.innerHTML = `
      <style>
        .scale_hours {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          width: 100%;
          gap: 2px;
          overflow-x: auto;
          min-width: 0;
        }

        .scale_hours_el {
          flex: 1 1 0;
          min-width: 0;
          display: flex;
          flex-direction: column;
          justify-content: flex-start;
          align-items: center;
          box-sizing: border-box;
        }

        .hour_info {
          display: block;
          font-size: 9px;
          font-weight: 400;
          text-align: center;
          color: var(--primary-text-color);
          margin-bottom: 4px;
          white-space: nowrap;
          width: 100%;
        }

        .hour_info_from {
          display: block;
          text-align: center;
        }

        .hour_info_to {
          display: block;
        }

        .hour_status {
          display: flex;
          gap: 4px;
          width: 100%;
          margin-top: 8px;
        }

        .half_hour {
          flex: 1;
          height: 40px;
          border-radius: 4px;
          background: var(--card-background-color, #f0eee8);
          opacity: 0.5;
          position: relative;
          box-sizing: border-box;
        }

        .half_hour.hour_active {
          background: #3a3a38;
          opacity: 1;
        }

        .half_hour.current_half {
          border: 2px solid var(--primary-color);
          opacity: 1;
        }

        .half_hour .status-indicator {
          position: absolute;
          bottom: 5px;
          right: 5px;
          width: 8px;
          height: 8px;
          background-color: #33a933;
          border-radius: 50%;
          animation: blink 2s infinite;
        }

        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }

        .scale_info {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-top: 16px;
          font-size: 12px;
          color: var(--secondary-text-color);
        }

        .info_legend {
          display: flex;
          gap: 16px;
        }

        .legend_item {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .legend_box {
          width: 20px;
          height: 20px;
          border-radius: 4px;
        }

        .legend_off {
          background: #3a3a38;
        }

        .legend_on {
          background: var(--card-background-color, #f0eee8);
        }
      </style>

      <div class="scale_hours">
        ${this.renderHours(periods, currentHour, currentMinutes)}
      </div>

      <div class="scale_info">
        <div class="info_legend">
          <div class="legend_item">
            <div class="legend_box legend_off"></div>
            <span>Відключення</span>
          </div>
          <div class="legend_item">
            <div class="legend_box legend_on"></div>
            <span>Світло є</span>
          </div>
        </div>
      </div>
    `;
  }

  renderHours(periods, currentHour, currentMinutes) {
    const hours = Array.from({length: 24}, (_, i) => i);
    const currentHalfIndex = currentMinutes >= 30 ? 1 : 0;

    return hours.map(hour => {
      const firstHalfOff = this.isPowerOffRange(hour, hour + 0.5, periods);
      const secondHalfOff = this.isPowerOffRange(hour + 0.5, hour + 1, periods);
      const isCurrentHour = hour === currentHour;
      const isCurrentFirst = isCurrentHour && currentHalfIndex === 0;
      const isCurrentSecond = isCurrentHour && currentHalfIndex === 1;

      return `
        <div class="scale_hours_el">
          <span class="hour_info">
            <i class="hour_info_from">${hour.toString().padStart(2, '0')}:00</i>
            <i class="hour_info_to">${hour.toString().padStart(2, '0')}:30</i>
          </span>
          <div class="hour_status">
            <span class="half_hour ${firstHalfOff ? 'hour_active' : ''} ${isCurrentFirst ? 'current_half' : ''}">
              ${isCurrentFirst ? '<div class="status-indicator"></div>' : ''}
            </span>
            <span class="half_hour ${secondHalfOff ? 'hour_active' : ''} ${isCurrentSecond ? 'current_half' : ''}">
              ${isCurrentSecond ? '<div class="status-indicator"></div>' : ''}
            </span>
          </div>
        </div>
      `;
    }).join('');
  }

  isPowerOffRange(startHour, endHour, periods) {
    return periods.some(period => {
      const periodStart = Number(period.start);
      const periodEnd = Number(period.end);
      if (Number.isNaN(periodStart) || Number.isNaN(periodEnd)) {
        return false;
      }
      return periodStart < endHour && periodEnd > startHour;
    });
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
