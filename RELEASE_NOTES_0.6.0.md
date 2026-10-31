# Release 0.6.0

Released: 2026-10-31

## ✨ Features

- **Choose where the schedule comes from.** Adding the integration now asks for the schedule source, then the queue. For Poltava oblast:
  - poe.pl.ua (Poltavaoblenergo, official) with energy-ua.info as a fallback — the default;
  - poe.pl.ua only;
  - energy-ua.info only (the behaviour before this release).
- Existing entries move to the default source automatically. To change the source or the queue later: Settings → Devices & Services → the entry → ⋮ → Reconfigure; entities, history and automations stay.
- Sources are pluggable: other regions can be added as new modules in `sources/` (see "Adding a schedule source" in the README).

## 🐛 Bug Fixes

- The schedule disappeared ("no outages today") when energy-ua.info came back after its downtime without data: an empty hourly scale under "Немає даних" is now "no data", and the last known schedule stays
- When all sources are down, the error names them

## 🔄 Update Instructions

1. Update via HACS or manually pull the latest version
2. Restart Home Assistant
