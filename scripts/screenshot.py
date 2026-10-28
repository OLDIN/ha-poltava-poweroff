"""Скріншот dev-дашборда «Відключення» (Playwright, без ручного логіну).

usage: screenshot.py <base_url> <access_token> <out.png> [--light] [--path /poweroff/0] [--card]
  --card  — лише сама картка poweroff-timeline-card (замість усього екрана)
"""

import asyncio
import json
import sys
import time

from playwright.async_api import async_playwright


async def main() -> None:
    base, token, out = sys.argv[1], sys.argv[2], sys.argv[3]
    args = sys.argv[4:]
    path = args[args.index("--path") + 1] if "--path" in args else "/poweroff/0"
    scheme = "light" if "--light" in args else "dark"
    tokens = {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": 1800,
        "hassUrl": base,
        "clientId": base + "/",
        "expires": int(time.time() * 1000) + 30 * 60 * 1000,
        "refresh_token": "",
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 520, "height": 1000},
            device_scale_factor=2,
            color_scheme=scheme,
            locale="uk-UA",
            timezone_id="Europe/Kyiv",
        )
        await ctx.add_init_script(f"localStorage.setItem('hassTokens', {json.dumps(json.dumps(tokens))});")
        page = await ctx.new_page()
        await page.goto(base + path)
        card = page.locator("poweroff-timeline-card")
        try:
            await card.wait_for(timeout=30000)
        except Exception:
            await page.screenshot(path=out.replace(".png", "-error.png"), full_page=True)
            raise
        await page.wait_for_timeout(1500)  # іконки / шрифти
        if "--card" in args:
            await card.screenshot(path=out)
        else:
            await page.screenshot(path=out, full_page=True)
        await browser.close()
    print(f"📸 {out}")


asyncio.run(main())
