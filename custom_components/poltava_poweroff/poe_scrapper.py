"""Outage schedule from the official Poltavaoblenergo site (poe.pl.ua).

The page https://www.poe.pl.ua/disconnection/power-outages/ loads the hourly outage
schedule (ГПВ) with one POST request per date:

    POST /customs/newgpv-info.php   seldate={"date_in": "31-10-2026"}

The answer is an HTML fragment for all sub-queues at once:
  * ``ul.gpv-periods`` — "1.1 — 06:00–07:30, 12:00–14:30, …" (what is parsed first);
  * ``table.gpv-table`` — 48 half-hour cells per sub-queue: ``gpv-s1`` power on,
    ``gpv-s2`` power off, ``gpv-s3`` switching (power is being restored), used as a fallback.

An empty answer means the schedule for that date is not published yet.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import cloudscraper  # type: ignore[import-untyped]
from bs4 import BeautifulSoup, Tag

from .energyua_scrapper import DayPeriods, EnergyUaScrapper, ScraperError
from .entities import PowerOffPeriod

LOGGER = logging.getLogger(__name__)

# Can be overridden via an environment variable (dev/e2e against a mock server)
POE_URL = os.environ.get("POLTAVA_POWEROFF_POE_URL", "https://www.poe.pl.ua/customs/newgpv-info.php")
POE_PAGE = "https://www.poe.pl.ua/disconnection/power-outages/"
REQUEST_TIMEOUT = 30  # seconds
KYIV = ZoneInfo("Europe/Kyiv")

_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*[–—-]\s*(\d{1,2}):(\d{2})")


def _hours(h: str, m: str) -> float:
    value = int(h) + int(m) / 60
    return 0.0 if value >= 24 else value  # 24:00 is stored as 0.0 (midnight at the end of the day)


class PoeScrapper:
    """Schedule of one sub-queue from poe.pl.ua."""

    def __init__(self, group: str) -> None:
        self.group = str(group)
        self.queue = self.group.replace("-", ".")  # "1-1" -> "1.1", as the site writes it
        self.scraper = None

    async def _get_scraper(self):
        if self.scraper is None:
            self.scraper = await asyncio.to_thread(
                cloudscraper.create_scraper, browser={"browser": "chrome", "platform": "windows", "desktop": True}
            )
        return self.scraper

    async def _fetch_day(self, day: date) -> str:
        scraper = await self._get_scraper()
        data = {"seldate": json.dumps({"date_in": day.strftime("%d-%m-%Y")})}
        headers = {"Referer": POE_PAGE, "X-Requested-With": "XMLHttpRequest", "Cache-Control": "no-cache"}
        try:
            response = await asyncio.to_thread(
                scraper.post, POE_URL, data=data, headers=headers, timeout=REQUEST_TIMEOUT
            )
        except Exception as err:  # network, DNS, timeout, cloudscraper challenge
            LOGGER.debug("Request to %s failed: %r", POE_URL, err)
            raise ScraperError("Не вдалося з'єднатися з poe.pl.ua") from err
        status = getattr(response, "status_code", None)
        if status != 200:
            LOGGER.debug("%s returned HTTP %s", POE_URL, status)
            raise ScraperError(f"Сайт Полтаваобленерго відповів помилкою HTTP {status}")
        return response.text or ""

    async def get_power_off_periods(self) -> tuple[DayPeriods, DayPeriods]:
        """(today, tomorrow); None for a day whose schedule the site does not have."""
        today = datetime.now(KYIV).date()
        today_html = await self._fetch_day(today)
        tomorrow_html = await self._fetch_day(today + timedelta(days=1))
        return self.parse(today_html, today=True), self.parse(tomorrow_html, today=False)

    async def validate(self) -> bool:
        try:
            await self._fetch_day(datetime.now(KYIV).date())
        except ScraperError:
            return False
        return True

    def parse(self, html: str, today: bool) -> DayPeriods:
        """Periods of this sub-queue from one answer; None when there is no schedule in it."""
        if not html.strip():
            return None
        soup = BeautifulSoup(html, "html.parser")

        periods_list = soup.find("ul", class_="gpv-periods")
        if isinstance(periods_list, Tag):
            for item in periods_list.find_all("li"):
                label = item.find("b")
                if isinstance(label, Tag) and label.get_text(strip=True) == self.queue:
                    periods = [
                        PowerOffPeriod(_hours(h1, m1), _hours(h2, m2), today=today)
                        for h1, m1, h2, m2 in _RANGE.findall(item.get_text(" "))
                    ]
                    return EnergyUaScrapper.merge_periods(periods)

        table = soup.find("table", class_="gpv-table")
        if isinstance(table, Tag):
            for row in table.find_all("tr"):
                head = row.find("td", class_="gpv-q")
                if isinstance(head, Tag) and head.get_text(strip=True) == self.queue:
                    return self._periods_from_cells(row.find_all("td", class_="gpv-c"), today)

        # An answer without this sub-queue (an announcement, a page from a firewall, a new layout):
        # unknown rather than "no outages", so another source or the cache is used.
        LOGGER.debug("poe.pl.ua answer has no schedule for queue %s: %.200s", self.queue, html)
        return None

    @staticmethod
    def _periods_from_cells(cells: list, today: bool) -> list[PowerOffPeriod]:
        """48 half-hour cells -> periods. Only gpv-s2 is "off": in gpv-s3 power is being restored."""
        periods: list[PowerOffPeriod] = []
        start: int | None = None
        for index, cell in enumerate([*cells, None]):
            off = cell is not None and "gpv-s2" in cell.get("class", [])
            if off and start is None:
                start = index
            elif not off and start is not None:
                periods.append(PowerOffPeriod(start / 2, 0.0 if index >= 48 else index / 2, today=today))
                start = None
        return periods
