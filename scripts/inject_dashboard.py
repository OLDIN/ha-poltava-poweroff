"""Записати в .storage окремий dashboard «Відключення» з карткою (до першого старту HA).

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
        "title": "Сенсори інтеграції",
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
(storage / "lovelace.poweroff").write_text(
    json.dumps(
        {
            "version": 1,
            "minor_version": 1,
            "key": "lovelace.poweroff",
            "data": {
                "config": {"title": "Відключення", "views": [{"title": "Відключення", "path": "0", "cards": cards}]}
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
                        "title": "Відключення",
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
print("dashboard «Відключення» записано (/poweroff/0)")
