"""Provides classes for scraping power off periods from the Energy UA website."""

from __future__ import annotations

import asyncio
import logging
import re

import cloudscraper  # type: ignore[import-untyped]
from bs4 import BeautifulSoup, Tag

from .const import BASE_URL, PowerOffGroup
from .entities import PowerOffPeriod

LOGGER = logging.getLogger(__name__)

URL = BASE_URL + "/cherga/{}"

REQUEST_TIMEOUT = 30  # seconds

# Markers of a real energy-ua schedule page (the site's own Ukrainian text and CSS classes).
# If none is present (Cloudflare challenge, maintenance page, empty response),
# it is an error, not "no outages".
_PAGE_MARKERS = ("Графік відключень", "Періоди відключень", "ch_day_title", "scale_info_periods")


class ScraperError(Exception):
    """The site is unreachable or returned an unexpected page.

    The message is shown on the card as is, so it is written in Ukrainian (UI text).
    """


DayPeriods = list[PowerOffPeriod] | None  # None = the site has no data for that day


class EnergyUaScrapper:
    """Class for scraping power off periods from the Energy UA website."""

    def __init__(self, group: PowerOffGroup) -> None:
        """Initialize the EnergyUaScrapper object."""
        self.group = group
        self.scraper = None

    async def _get_scraper(self):
        """Get or create cloudscraper instance."""
        if self.scraper is None:
            self.scraper = await asyncio.to_thread(
                cloudscraper.create_scraper, browser={"browser": "chrome", "platform": "windows", "desktop": True}
            )
        return self.scraper

    async def validate(self) -> bool:
        """Validate connection to the website."""
        try:
            scraper = await self._get_scraper()
            headers = {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
            response = await asyncio.to_thread(
                scraper.get, URL.format(self.group), headers=headers, timeout=REQUEST_TIMEOUT
            )
            return response.status_code == 200
        except Exception:  # noqa: BLE001 - any error here means "cannot connect"
            return False

    @staticmethod
    def merge_periods(periods: list[PowerOffPeriod]) -> list[PowerOffPeriod]:
        """Merge adjacent/overlapping periods. An end of 0.0 means 24:00 (midnight at the end of the day)."""
        if not periods:
            return []

        def end_of(p: PowerOffPeriod) -> float:
            return 24.0 if p.end == 0.0 and p.start > 0 else p.end

        periods.sort(key=lambda x: x.start)
        merged_periods = [periods[0]]
        for current in periods[1:]:
            last = merged_periods[-1]
            if current.start <= end_of(last):
                new_end = max(end_of(last), end_of(current))
                last.end = 0.0 if new_end >= 24.0 else new_end
                continue
            merged_periods.append(current)

        return merged_periods

    async def _fetch_page(self) -> str:
        scraper = await self._get_scraper()
        # Headers that prevent caching
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        url = URL.format(self.group)
        try:
            response = await asyncio.to_thread(scraper.get, url, headers=headers, timeout=REQUEST_TIMEOUT)
        except Exception as err:  # network, DNS, timeout, cloudscraper challenge
            LOGGER.debug("Request to %s failed: %r", url, err)
            kind = (
                "таймаут"
                if "timeout" in type(err).__name__.lower() or "timed out" in str(err).lower()
                else "немає з'єднання"
            )
            raise ScraperError(f"Не вдалося з'єднатися з energy-ua.info ({kind})") from err

        status = getattr(response, "status_code", None)
        if status != 200:
            LOGGER.debug("%s returned HTTP %s", url, status)
            raise ScraperError(f"Сайт відповів помилкою HTTP {status}")

        content = response.text or ""
        if not any(marker in content for marker in _PAGE_MARKERS):
            LOGGER.debug("%s returned unexpected page (%d bytes): %.200s", url, len(content), content)
            raise ScraperError("Сайт повернув сторінку без графіка (техроботи або захист від ботів)")
        return content

    async def get_power_off_periods(self) -> tuple[DayPeriods, DayPeriods]:
        """Get power off periods from the website.

        Returns:
            Tuple of (today_periods, tomorrow_periods). Each item is:
              * a list: the site has a schedule for that day (empty list = no outages);
              * None: the site has no data for that day (not published yet / "Немає даних").

        Raises:
            ScraperError: the site is unreachable or the page doesn't look like a schedule.
        """
        content = await self._fetch_page()
        return self.parse_page(content)

    def parse_page(self, content: str) -> tuple[DayPeriods, DayPeriods]:
        """Parse the HTML of a queue page."""
        soup = BeautifulSoup(content, "html.parser")
        today_results: list[PowerOffPeriod] = []
        tomorrow_results: list[PowerOffPeriod] = []

        # First look for the scale_info_periods blocks for today and tomorrow
        all_scale_info_periods = soup.find_all("div", class_="scale_info_periods")
        today_periods_found = False
        tomorrow_periods_found = False
        # The day's periods block explicitly says "Немає даних" (no data)
        today_no_data = False
        tomorrow_no_data = False

        for scale_info_block in all_scale_info_periods:
            if not isinstance(scale_info_block, Tag):
                continue

            title = scale_info_block.find("h4", class_="scale_info_title")
            if not isinstance(title, Tag):
                continue

            title_text = title.get_text().strip().lower()
            no_data = scale_info_block.find("div", class_="no_data") is not None
            if "сьогодні" in title_text or "сегодня" in title_text:
                today_no_data = today_no_data or no_data
                periods = self._parse_periods_from_text_block(scale_info_block, today=True)
                if periods:
                    today_results.extend(periods)
                    today_periods_found = True
            elif "завтра" in title_text:
                tomorrow_no_data = tomorrow_no_data or no_data
                periods = self._parse_periods_from_text_block(scale_info_block, today=False)
                if periods:
                    tomorrow_results.extend(periods)
                    tomorrow_periods_found = True

        # Whether the page has an hourly scale for the day (the day's schedule is published,
        # even if it contains no outages).
        today_scale_found = False
        tomorrow_scale_found = False

        if not today_periods_found or not tomorrow_periods_found:
            all_day_titles = soup.find_all("h4", class_="ch_day_title")
            LOGGER.debug("Found %d ch_day_title headers", len(all_day_titles))
            for day_title in all_day_titles:
                if not isinstance(day_title, Tag):
                    continue
                title_text = day_title.get_text().strip().lower()
                scale_hours_block = None
                for sibling in day_title.next_siblings:
                    if not isinstance(sibling, Tag):
                        continue
                    if "scale_hours" in sibling.get("class", []):
                        scale_hours_block = sibling
                        break
                    if "ch_day_title" in sibling.get("class", []):
                        break  # reached the next day: there is no scale for this one

                if not scale_hours_block:
                    continue

                is_today = "сьогодні" in title_text
                is_tomorrow = "завтра" in title_text
                if is_today:
                    today_scale_found = True
                if is_tomorrow:
                    tomorrow_scale_found = True

                if (is_today and not today_periods_found) or (is_tomorrow and not tomorrow_periods_found):
                    target = today_results if is_today else tomorrow_results
                    for item in scale_hours_block.find_all("div", class_="scale_hours_el"):
                        if item.find("span", class_="hour_active"):
                            start, end = self._parse_item(item)
                            target.append(PowerOffPeriod(start, end, today=is_today))

        # An empty scale under "Немає даних" is not a day without outages: the site lost or has not
        # published the data (seen right after its downtime). Keep the day unknown so the cache stays.
        if today_no_data and not today_results:
            today_scale_found = False
        if tomorrow_no_data and not tomorrow_results:
            tomorrow_scale_found = False

        today_final: DayPeriods = (
            self.merge_periods(today_results) if (today_periods_found or today_scale_found) else None
        )
        tomorrow_final: DayPeriods = (
            self.merge_periods(tomorrow_results) if (tomorrow_periods_found or tomorrow_scale_found) else None
        )

        LOGGER.debug(
            "Parsed: today=%s, tomorrow=%s",
            "no data" if today_final is None else len(today_final),
            "no data" if tomorrow_final is None else len(tomorrow_final),
        )
        return today_final, tomorrow_final

    def _parse_periods_from_text_block(self, scale_info_block: Tag, today: bool) -> list[PowerOffPeriod]:
        """Parse periods from a specific scale_info_periods block."""
        periods: list[PowerOffPeriod] = []

        periods_items = scale_info_block.find("div", class_="periods_items")
        if not periods_items or not isinstance(periods_items, Tag):
            return periods

        # Parse each period from text like "З 12:00 до 14:30" ("from 12:00 to 14:30")
        # BeautifulSoup.get_text() strips HTML tags, so the time is just "12:00"
        period_spans = periods_items.find_all("span")
        for span in period_spans:
            if not isinstance(span, Tag):
                continue
            text = span.get_text()
            # Match "З HH:MM до HH:MM"; get_text() already removed the <b> tags
            match = re.search(r"З\s+(\d{1,2}:\d{2})\s+до\s+(\d{1,2}:\d{2})", text)
            if match:
                start_str = match.group(1)
                end_str = match.group(2)
                start = self._value_from_timestring(start_str)
                end = self._value_from_timestring(end_str)
                periods.append(PowerOffPeriod(start, end, today=today))

        return periods

    def _parse_item(self, item: BeautifulSoup) -> tuple[float, float]:
        start_hour = item.find("i", class_="hour_info_from")
        end_hour = item.find("i", class_="hour_info_to")
        if start_hour and end_hour:
            return self._value_from_timestring(start_hour.text), self._value_from_timestring(end_hour.text)
        raise ValueError(f"Time period not found in the input string: {item.text}")

    @staticmethod
    def _value_from_timestring(value: str) -> float:
        """Convert `HH:MM` to hour value with half-hour precision."""
        hour_str, minute_str = value.strip().split(":")
        hour = int(hour_str)
        minute = int(minute_str)
        return hour + minute / 60
