"""Надійний онбординг/логін HA і видача access-токена (замість bash+curl).

usage: ha_auth.py <base_url> <username> <password>
друкує access_token у stdout (останній рядок).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

CLIENT = None  # заповнюється з base


def _post(url, data, headers=None, form=False):
    if form:
        body = "&".join(f"{k}={v}" for k, v in data.items()).encode()
        h = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        body = json.dumps(data).encode()
        h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def _get_json(url):
    try:
        with urllib.request.urlopen(url) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def main():
    base, user, pw = sys.argv[1], sys.argv[2], sys.argv[3]
    client = base if base.endswith("/") else base + "/"

    # чекати готовності onboarding API
    for _ in range(30):
        ob = _get_json(f"{base}/api/onboarding")
        if isinstance(ob, list):
            break
        time.sleep(2)

    ob = _get_json(f"{base}/api/onboarding")
    user_done = isinstance(ob, list) and next(
        (s["done"] for s in ob if s["step"] == "user"), True
    )

    auth_code = None
    if isinstance(ob, list) and not user_done:
        # створити owner
        st, resp = _post(f"{base}/api/onboarding/users", {
            "client_id": client, "name": "Admin",
            "username": user, "password": pw, "language": "uk"})
        auth_code = resp.get("auth_code")
        # завершити решту кроків
        _, tok = _post(f"{base}/auth/token", {
            "client_id": client, "grant_type": "authorization_code",
            "code": auth_code}, form=True)
        access = tok.get("access_token")
        for step in ("core_config", "analytics"):
            _post(f"{base}/api/onboarding/{step}", {},
                  headers={"Authorization": f"Bearer {access}"})
        _post(f"{base}/api/onboarding/integration",
              {"client_id": client, "redirect_uri": client},
              headers={"Authorization": f"Bearer {access}"})
        print(access)
        return

    # onboarding вже пройдено -> логін через login_flow
    st, flow = _post(f"{base}/auth/login_flow", {
        "client_id": client, "handler": ["homeassistant", None],
        "redirect_uri": client})
    flow_id = flow.get("flow_id")
    st, step = _post(f"{base}/auth/login_flow/{flow_id}", {
        "client_id": client, "username": user, "password": pw})
    code = step.get("result")
    st, tok = _post(f"{base}/auth/token", {
        "client_id": client, "grant_type": "authorization_code",
        "code": code}, form=True)
    print(tok.get("access_token", ""))


if __name__ == "__main__":
    main()
