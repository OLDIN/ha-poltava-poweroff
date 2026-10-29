# Release 0.4.0

Released: 2026-10-29

## ✨ Features

- Optional battery runout mark on the timeline card: set `battery_entity` to a battery/UPS runtime sensor and the card draws a red line on the spiral when the battery runs out, plus a line saying whether the charge lasts until power returns (#5)
- Integration icon and logo shipped in `brand/`, so Home Assistant 2026.3+ shows them

## 🔧 Other Changes

- `scripts/bump_version.py`: PR-based release flow (`patch|minor|major --pr`, `release`) (#3)
- Release workflow publishes GitHub Releases automatically after a version bump is merged; recovery when a release step fails (#4)

## 🔄 Update Instructions

1. Update via HACS or manually pull the latest version
2. Restart Home Assistant
3. Clear browser cache if needed
