"""Перезняти скріни для README (pics/*.png) у локальному HA з mock energy-ua.

Викликається з `scripts/dev_ha_ui.sh readme` (HA і mock мають бути запущені).
usage: readme_screenshots.py <ha_base_url> <access_token> <mock_base_url> <out_dir>
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

BASE, TOKEN, MOCK, OUT = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4])
SCHEDULE = {"today": [[8, 9.5], [14, 16], [21, 0]], "tomorrow": [[0, 2], [9, 11], [15, 17.5]]}


def post(url: str, body: dict, auth: bool = False) -> None:
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    urllib.request.urlopen(req).read()


def refresh() -> None:
    post(f"{BASE}/api/services/poltava_poweroff/refresh", {}, auth=True)
    time.sleep(2)


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    post(f"{MOCK}/_test/mode", {"mode": "ok"})
    post(f"{MOCK}/_test/delay", {"seconds": 0})
    post(f"{MOCK}/_test/schedule", SCHEDULE)
    post(
        f"{BASE}/api/services/select/select_option", {"entity_id": "select.poweroff_view_queue", "option": "4.1"}, True
    )
    refresh()

    tokens = {
        "access_token": TOKEN,
        "token_type": "Bearer",
        "expires_in": 1800,
        "hassUrl": BASE,
        "clientId": BASE + "/",
        "expires": int(time.time() * 1000) + 1800000,
        "refresh_token": "",
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 440, "height": 1400},
            device_scale_factor=2,
            color_scheme="dark",
            locale="uk-UA",
            timezone_id="Europe/Kyiv",
        )
        await ctx.add_init_script(f"localStorage.setItem('hassTokens', {json.dumps(json.dumps(tokens))});")
        page = await ctx.new_page()

        async def open_dashboard():
            await page.goto(BASE + "/poweroff/0")
            card = page.locator("poweroff-timeline-card")
            await card.wait_for(timeout=60000)
            await page.wait_for_timeout(2000)
            return card

        card = await open_dashboard()
        await card.screenshot(path=str(OUT / "card.png"))

        await card.locator(".queue-chip").click()
        await page.wait_for_timeout(300)
        box = await card.bounding_box()
        await page.screenshot(
            path=str(OUT / "card_queue_switcher.png"),
            clip={"x": box["x"], "y": box["y"], "width": box["width"], "height": 420},
        )
        await card.locator(".queue-chip").click()

        await page.locator("hui-calendar-card").screenshot(path=str(OUT / "calendar.png"))
        await page.locator("hui-entities-card").screenshot(path=str(OUT / "sensors.png"))

        # сайт лежить: банер + tooltip з часом останньої вдалої перевірки
        post(f"{MOCK}/_test/mode", {"mode": "http500"})
        refresh()
        card = await open_dashboard()
        await card.locator(".updated-line").hover()
        await page.wait_for_timeout(400)
        await card.screenshot(path=str(OUT / "card_site_down.png"))
        post(f"{MOCK}/_test/mode", {"mode": "ok"})
        await browser.close()
    print("📸", ", ".join(sorted(f.name for f in OUT.glob("*.png"))))


asyncio.run(main())
