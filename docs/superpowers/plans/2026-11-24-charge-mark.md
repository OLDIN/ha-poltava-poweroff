# Charge-complete mark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Blue mark + text line on the timeline card showing when the battery finishes charging to a configurable target %.

**Architecture:** All in the single card file. Pure helpers (duration parsing, target resolution, forecast) feed `updateTimeline()`, which passes a second mark to `renderSpiral()`. Same pattern as the existing red battery mark.

**Tech Stack:** Vanilla JS custom element, vitest + jsdom.

**Spec:** `docs/superpowers/specs/2026-11-24-charge-mark-design.md`

## Global Constraints

- Edit only `custom_components/poltava_poweroff/www/poweroff-timeline-card.js` (`config/www` is a dev copy), `tests/js/poweroff-timeline-card.test.js`, `README.md`.
- Without the new options the card output is unchanged; existing tests keep passing.
- Defaults: `charge_target` = 100; mark colour `#1e88e5`; UI text in Ukrainian.
- Shown only for the home queue, on the tab of the day the charge ends.
- Blue mark is drawn statically (no glide animation; my call: the time-to-full value changes slowly).

## Review Focus

- `charge_target` ≤ 0, > 100, non-numeric, or an entity in `unavailable` → behaves as 100.
- `charge_target` < 100 but no/unavailable `charge_soc_entity` → target ignored (100).
- SOC ≥ target → no mark (already charged).
- `label` attribute contains "empty" (discharging) → no mark.
- Time `"0h 0m"` / `0` → no mark.
- Charge ends past midnight → mark only on the next day's tab, line still shown with "завтра".

## File Structure

Single file `poweroff-timeline-card.js`; new methods sit next to `batteryHours` / `batteryForecast`.

### Task 1: Parsing and forecast

**Files:** Modify `poweroff-timeline-card.js` (near `batteryHours`, ~line 651); Test `tests/js/poweroff-timeline-card.test.js` (new `describe('Charge mark')`).

**Interfaces:**
- Produces: `parseDurationHours(obj): number|null` (module function; `obj` is an HA state object; accepts everything `batteryHours` does plus `"Xh Ym"`, `"Xh"`, `"Ym"`); `batteryHours()` now delegates to it.
- Produces: `chargeTarget(): number` (resolves `config.charge_target`: number, numeric string, or entity id; invalid → 100; clamped to (0,100]).
- Produces: `chargeForecast(now: Date, nextOffIso?: string, powerOn: boolean): { hours, done: Date, target: number, until: Date|null, ok: boolean|null }|null`. `hours` = time to `target` (scaled: `hours_full × (target − soc) / (100 − soc)` when target < 100 and SOC readable); `until` = valid future `nextOffIso` when `powerOn`; `ok = until ? done <= until : null`. Returns `null` when the mark is hidden (see Review Focus).

- [ ] **Step 1: Write failing tests** in the new describe: `parses "0h 29m", "2h", "45m" and keeps the old formats` (0.4833, 2, 0.75; `batteryHours` tests still pass); `scales the time to the target`: full=2 h, soc 50, target 80 → 1.2 h (±0.01); `treats an invalid or missing target as 100` (`'abc'`, `150`, `-5`, `unavailable` entity); `ignores target <100 without soc`; `hides when label contains "empty"`, `when time is 0`, `when soc >= target`.
- [ ] **Step 2: Run** `npx vitest run -t "Charge mark"` — expect FAIL (methods not defined).
- [ ] **Step 3: Implement** the three functions as specified; move the body of `batteryHours` into `parseDurationHours`, add regex `/^(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+(?:\.\d+)?)\s*m(?:in)?)?$/i` (at least one group present) before the numeric branch.
- [ ] **Step 4: Run** `npx vitest run` — expect all PASS.
- [ ] **Step 5: Commit** `feat: charge forecast helpers`.

### Task 2: Mark, legend, line, re-render

**Files:** Modify `poweroff-timeline-card.js`: CSS (~line 175), `set hass` (~374), `updateTimeline` (~594–626), `renderSpiral` signature + `renderBatteryMark` (~693, ~771, ~825); Test same file.

**Interfaces:**
- Consumes: `chargeForecast` from Task 1.
- Produces: `renderChargeMark(done: Date): string` (blue radial line `.charge-mark`, same geometry as `renderBatteryMark`, stroke `#1e88e5`); `renderChargeLine(charge): string` (`.charge-line`, class `ok`/`short`/none); `renderSpiral(..., battery = null, charge = null)`.

- [ ] **Step 1: Write failing tests** (pattern of `Battery runout mark` describe, `makeHass` plus `sensor.charge_time`, `sensor.soc`, `input_number.target`): `draws a blue line at the charge-complete time and a legend item`; `puts the line only on the tab of the day the charge ends`; `says it fits: "Зарядиться до 100% о", class ok, when done before next_off`; `warns when charging ends after next_off` (class `short`); `shows no comparison while power is off` (state "Power OFF"/`off`, no `ok`/`short` class); `shows nothing without charge_entity`; `re-renders when only charge, soc or target entity changes`; `red and blue marks can coexist`.
- [ ] **Step 2: Run** `npx vitest run -t "Charge mark"` — FAIL.
- [ ] **Step 3: Implement**: `.legend-charge` CSS like `.legend-battery` (`#1e88e5`), legend item «Зарядиться»; `.charge-line` styled like `.battery-line` with icon `mdi:battery-charging`; line text «Зарядиться до {target}% о <b>HH:MM</b>, світло до <b>HH:MM</b>» (without «світло до …» when `until` is null); `set hass` also tracks `charge_entity`, `charge_soc_entity`, and `charge_target` (when it is an entity id) states for the re-render check; `updateTimeline` computes `charge` only for the home queue and passes it to `renderSpiral` only when `charge.done` falls on `displayDate`; `powerOn` from `sensor.state` ∈ {`on`, `Power ON`} (case-insensitive).
- [ ] **Step 4: Run** `npx vitest run` — all PASS (image snapshot tests unchanged).
- [ ] **Step 5: Commit** `feat: blue charge-complete mark`.

### Task 3: Editor, README, manual check

**Files:** Modify `poweroff-timeline-card.js` (`EDITOR_LABELS`, `EDITOR_HELPERS`, `getConfigForm` ~280–315); `README.md` (after "Battery runout mark"); Test same file (`Visual editor` describe).

- [ ] **Step 1: Update the failing editor test**: schema names become `['entity','show_queue_switcher','queue_entity','battery_entity','charge_entity','charge_soc_entity','charge_target','auto_tomorrow']`; labels «Час до повного заряду», «Сенсор заряду, %», «Заряджати до, %»; helper for `charge_entity` mentions «синю лінію». `charge_target` uses `{ selector: { entity: { filter: { domain: ['input_number','number','sensor'] } } } }`; the form also accepts a plain number in YAML (document in README; the visual field takes an entity).
- [ ] **Step 2: Run** — FAIL; **Step 3: implement**; **Step 4: Run** `npx vitest run` — PASS.
- [ ] **Step 5: README** section «Charge-complete mark (optional)» with the YAML from the spec, the formats, hide conditions, scaling formula and its linear-approximation caveat.
- [ ] **Step 6: Commit** `feat: editor fields and docs for charge mark`.
