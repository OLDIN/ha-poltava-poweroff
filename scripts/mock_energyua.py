"""Mock-сервер energy-ua.info для dev/e2e.

Віддає сторінку /cherga/<група> у тому ж HTML-форматі, що й справжній сайт,
і має тестові ручки, щоб «ламати» сайт наживо:

  GET  /_test/state                 — поточний режим і графік
  POST /_test/mode   {"mode": "..."} — ok | nodata | http500 | garbage | timeout
  POST /_test/schedule {"group": "4-1", "today": [[8, 9.5]], "tomorrow": [[9, 11]] | null}
  POST /_test/delay  {"seconds": 2}  — повільний сайт (видно стан «завантажую» в картці)

Запуск окремо:  python scripts/mock_energyua.py   (порт з POLTAVA_MOCK_PORT, типово 8798)
"""

from __future__ import annotations

import asyncio
import os

from aiohttp import web

DEFAULT_SCHEDULE: dict[str, dict[str, list | None]] = {
    "default": {
        "today": [[8, 9.5], [14, 16], [20, 22]],
        "tomorrow": [[9, 11], [15, 17.5], [21, 22.5]],
    },
}


def _hhmm(value: float) -> str:
    value = float(value)
    h = int(value) % 24
    m = round((value - int(value)) * 60)
    return f"{h:02d}:{m:02d}"


def _day_block(title: str, label: str, periods: list | None) -> str:
    if periods is None:
        # день оголошено, але графіка ще немає (як на справжньому сайті ввечері)
        return f'<h4 class="ch_day_title">Відключення {title}</h4>'
    hours = []
    for hour in range(24):
        active = any(float(s) <= hour < (24 if float(e) == 0 else float(e)) for s, e in periods)
        cls = "hour_active" if active else ""
        hours.append(
            f'<div class="scale_hours_el"><span class="hour_info"><i class="hour_info_from">{hour:02d}:00</i>'
            f'<i class="hour_info_to">{(hour + 1) % 24:02d}:00</i></span><span class="hour_status {cls}"></span></div>'
        )
    spans = "".join(f"<span>З <b>{_hhmm(s)}</b> до <b>{_hhmm(e)}</b>, тривалість</span>" for s, e in periods)
    info = (
        f'<div class="scale_info_periods"><h4 class="scale_info_title">Періоди відключень на {label}</h4>'
        f'<div class="periods_items">{spans}</div></div>'
        if periods
        else ""
    )
    return f'<h4 class="ch_day_title">Відключення {title}</h4><div class="scale_hours new_scale">{"".join(hours)}</div>{info}'


def render_page(group: str, today: list | None, tomorrow: list | None) -> str:
    q = group.replace("-", ".")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>Графік відключень світла у Полтавській області (сьогодні): {q} черга</title></head>"
        f"<body><main><div class='container'>{_day_block('сьогодні', 'сьогодні', today)}"
        f"{_day_block('завтра', 'завтра', tomorrow)}</div></main></body></html>"
    )


def build_app() -> web.Application:
    app = web.Application()
    app["mode"] = os.environ.get("POLTAVA_MOCK_MODE", "ok")
    app["schedule"] = {k: dict(v) for k, v in DEFAULT_SCHEDULE.items()}
    app["hits"] = 0
    app["delay"] = float(os.environ.get("POLTAVA_MOCK_DELAY", "0"))

    async def cherga(request: web.Request) -> web.StreamResponse:
        app["hits"] += 1
        group = request.match_info["group"]
        mode = app["mode"]
        if app["delay"]:
            await asyncio.sleep(app["delay"])
        if mode == "http500":
            return web.Response(status=502, text="<html><body>502 Bad Gateway</body></html>", content_type="text/html")
        if mode == "garbage":
            return web.Response(
                text="<html><title>Just a moment...</title>Checking your browser</html>", content_type="text/html"
            )
        if mode == "timeout":
            await asyncio.sleep(120)
        sched = app["schedule"].get(group) or app["schedule"]["default"]
        if mode == "nodata":
            return web.Response(text=render_page(group, None, None), content_type="text/html")
        return web.Response(text=render_page(group, sched["today"], sched["tomorrow"]), content_type="text/html")

    async def set_mode(request: web.Request) -> web.Response:
        body = await request.json()
        app["mode"] = body["mode"]
        return web.json_response({"ok": True, "mode": app["mode"]})

    async def set_schedule(request: web.Request) -> web.Response:
        body = await request.json()
        app["schedule"][body.get("group", "default")] = {"today": body.get("today"), "tomorrow": body.get("tomorrow")}
        return web.json_response({"ok": True, "schedule": app["schedule"]})

    async def set_delay(request: web.Request) -> web.Response:
        app["delay"] = float((await request.json())["seconds"])
        return web.json_response({"ok": True, "delay": app["delay"]})

    async def state(request: web.Request) -> web.Response:
        return web.json_response(
            {"mode": app["mode"], "delay": app["delay"], "hits": app["hits"], "schedule": app["schedule"]}
        )

    app.router.add_get("/cherga/{group}", cherga)
    app.router.add_post("/_test/mode", set_mode)
    app.router.add_post("/_test/schedule", set_schedule)
    app.router.add_post("/_test/delay", set_delay)
    app.router.add_get("/_test/state", state)
    return app


if __name__ == "__main__":
    web.run_app(build_app(), host="127.0.0.1", port=int(os.environ.get("POLTAVA_MOCK_PORT", "8798")))
