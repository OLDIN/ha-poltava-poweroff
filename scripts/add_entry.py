"""Add the poltava_poweroff integration through the real config flow (REST API).

usage: add_entry.py <base_url> <token> <group>
"""

import json
import sys
import urllib.request

base, token, group = sys.argv[1], sys.argv[2], sys.argv[3]


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


flow = post("/api/config/config_entries/flow", {"handler": "poltava_poweroff", "show_advanced_options": False})
result = post(f"/api/config/config_entries/flow/{flow['flow_id']}", {"poweroff_group": group})
print(f"config flow: {result.get('type')} {result.get('title', '')} {result.get('errors', '')}")
