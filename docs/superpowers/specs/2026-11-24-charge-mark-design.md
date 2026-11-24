# Charge-complete mark on the timeline card — design

## Intent
The card already shows a red mark where the battery runs out (`battery_entity`). Add a **blue mark** for the
moment the battery finishes charging, so the user sees at a glance whether charging fits into the time
the power is on. The source sensor and the target % are configurable, so the card works for anyone
(not only for one BMS / one "charge to" slider).

## Goals
- Blue radial mark on the spiral at the charge-complete time, same look and glide animation as the red one.
- Source sensor chosen in the card config / visual editor.
- Target % configurable; default 100.
- A line under the spiral: "Зарядиться до 90% о 17:25, світло до 18:00" — green if it fits, red if not.

## Non-goals
- No charge-time model of our own (no power / capacity maths); the source sensor gives the time to full.
- No control of the charger.

## Anti-goals
- Card must look exactly as before without the new options, and while the sensor is unavailable.
- Must not require the user's `input_number.battery_charge_target` or any specific BMS.

## Approaches considered
- **A (chosen): scale the sensor's time to the target.** `t_target = t_full × (target − soc) / (100 − soc)`.
  Linear approximation, good for LiFePO4 up to ~95%. Needs a SOC sensor only when target < 100.
- B: show the sensor time as is, no target. Simpler, but the user's "charge to" setting would not matter.

## Config
```yaml
charge_entity: sensor.lifepo4_time_to_full        # time to full: h / min / s / d units, "H:MM", "0h 29m"
charge_soc_entity: sensor.lifepo4_280ah_battery   # only needed when charge_target < 100
charge_target: input_number.battery_charge_target # number (80) or entity id; default 100
```

## Behaviour (my calls)
- Time parser also accepts `"Xh Ym"` (`"0h 29m"`, `"2h"`, `"45m"`).
- Mark hidden when: sensor missing/unavailable/unparsable, time is 0, the entity's `label` attribute contains
  "empty" (that BMS reports "Time to empty" while discharging), or SOC ≥ target.
- Target > 100 or < 0 or unreadable → 100. Target < 100 without a usable SOC → target ignored (100).
- "Light until" = `next_off` of the schedule sensor, used while the power is on. While the power is off
  the mark is still drawn (if the sensor says it is charging), but there is no fits/doesn't-fit comparison.
- Shown only for the home queue, on the tab of the day the charge ends — same rules as the red mark.
- Both marks can coexist; when charging, the red one normally is not shown (runtime is unknown/idle).

## Left to the builder
Exact legend wording, colours (`#1e88e5`), editor labels/helpers (Ukrainian), README section, tests (vitest).
Edit only `custom_components/poltava_poweroff/www/poweroff-timeline-card.js`; `config/www` is a dev copy.
