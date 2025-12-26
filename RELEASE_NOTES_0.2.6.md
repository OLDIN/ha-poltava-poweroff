# Release 0.2.6

## 🐛 Bug Fixes

### Automatic Sensor Updates
- **Fixed sensor auto-updates**: Added `CoordinatorEntity` inheritance to sensor and calendar entities
- Sensors now automatically refresh every 5 minutes when coordinator fetches new data
- Previously, sensors would display `—` (unavailable) because they weren't subscribed to coordinator updates

### Midnight Period Handling
- **Fixed calendar event validation error** for power outage periods crossing midnight (e.g., 22:00-00:00)
- Added logic to correctly handle overnight periods by adjusting end datetime when it's earlier than start

### Type Safety
- Fixed mypy type hints for `CoordinatorEntity` generic types
- Improved type safety for coordinator interactions

## 📝 Changes

- `custom_components/poltava_poweroff/sensor.py`: Added `CoordinatorEntity` base class
- `custom_components/poltava_poweroff/calendar.py`: Added `CoordinatorEntity` base class
- `custom_components/poltava_poweroff/entities.py`: Fixed `to_datetime_period()` for midnight crossover

## ⚙️ Technical Details

Before this fix:
- Sensors created once at startup but never updated
- Users saw `—` instead of actual power state/times
- Coordinator fetched data but sensors didn't reflect changes

After this fix:
- Sensors automatically update when coordinator refreshes (every 5 minutes)
- Real-time power state and schedule information displayed correctly
- Full Home Assistant integration lifecycle support

## 🔄 Update Instructions

1. Update via HACS
2. Restart Home Assistant
3. Sensors will now update automatically every 5 minutes
