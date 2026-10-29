# Release 0.5.0

Released: 2026-10-30

## ✨ Features

- `event.poweroff_schedule_changed`: fires when your queue's schedule is published (e.g. tomorrow's in the evening) or changes, with the new and previous outages in the attributes
- Blueprints, importable with one click from the README:
  - **Schedule changed** — push notification with the new schedule (and the old one when it changed)
  - **Outage warning** — notification and optional TTS announcement N minutes before the next outage, plus any extra actions
- Visual editor for the timeline card with a live preview: schedule sensor, queue switcher, battery runtime sensor, auto switch to tomorrow
- New card options `show_queue_switcher` and `auto_tomorrow`

## 🐛 Bug Fixes

- The queue switcher disappeared from the card when `queue_entity` was set explicitly

## 🔄 Update Instructions

1. Update via HACS or manually pull the latest version
2. Restart Home Assistant
3. Clear browser cache if needed
