"""Write a separate "Power outages" dashboard with the card into .storage (before HA first starts).

usage: inject_dashboard.py <config_dir>
"""

import json
import sys
from pathlib import Path

cfg = Path(sys.argv[1])
storage = cfg / ".storage"
storage.mkdir(parents=True, exist_ok=True)

cards = [
    {"type": "custom:poweroff-timeline-card", "entity": "sensor.power_state"},
    {"type": "calendar", "initial_view": "listWeek", "entities": ["calendar.poltava_poweroff_calendar"]},
    {
        "type": "entities",
        "title": "Integration sensors",
        "entities": [
            "sensor.power_state",
            "sensor.next_power_off",
            "sensor.next_power_on",
            "sensor.schedule_updated",
            "sensor.schedule_last_fetch",
            "select.poweroff_view_queue",
            "calendar.poltava_poweroff_calendar",
        ],
    },
]
battery_card = {
    "type": "custom:poweroff-timeline-card",
    "entity": "sensor.power_state",
    "battery_entity": "sensor.dev_battery_runtime",
}
(storage / "lovelace.poweroff").write_text(
    json.dumps(
        {
            "version": 1,
            "minor_version": 1,
            "key": "lovelace.poweroff",
            "data": {
                "config": {
                    "title": "Power outages",
                    "views": [
                        {"title": "Power outages", "path": "0", "cards": cards},
                        # Card with the battery runout mark; the sensor state is set via the REST API
                        {"title": "Battery", "path": "battery", "cards": [battery_card]},
                    ],
                }
            },
        },
        ensure_ascii=False,
        indent=2,
    )
)
(storage / "lovelace_dashboards").write_text(
    json.dumps(
        {
            "version": 1,
            "minor_version": 1,
            "key": "lovelace_dashboards",
            "data": {
                "items": [
                    {
                        "id": "poweroff",
                        "icon": "mdi:transmission-tower-off",
                        "title": "Power outages",
                        "url_path": "poweroff",
                        "show_in_sidebar": True,
                        "mode": "storage",
                        "require_admin": False,
                    }
                ]
            },
        },
        ensure_ascii=False,
        indent=2,
    )
)
print('"Power outages" dashboard written (/poweroff/0, /poweroff/battery)')
