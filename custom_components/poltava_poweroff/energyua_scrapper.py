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

REQUEST_TIMEOUT = 30  # секунд

# Маркери, за якими розпізнаємо «справжню» сторінку графіка energy-ua.
# Якщо жодного немає (Cloudflare-челендж, сторінка техробіт, порожня відповідь) —
# це помилка, а не «відключень немає».
_PAGE_MARKERS = ("Графік відключень", "Періоди відключень", "ch_day_title", "scale_info_periods")


class ScraperError(Exception):
    """Сайт недоступний або повернув неочікувану сторінку."""


DayPeriods = list[PowerOffPeriod] | None  # None = на сайті немає даних за цей день


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
        except Exception:
            return False

    @staticmethod
    def merge_periods(periods: list[PowerOffPeriod]) -> list[PowerOffPeriod]:
        if not periods:
            return []

        periods.sort(key=lambda x: x.start)

        merged_periods = [periods[0]]
        for current in periods[1:]:
            last = merged_periods[-1]
            if current.start <= last.end:
                last.end = max(last.end, current.end)
                continue
            merged_periods.append(current)

        return merged_periods

    async def _fetch_page(self) -> str:
        scraper = await self._get_scraper()
        # Додаємо заголовки для запобігання кешування
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        url = URL.format(self.group)
        try:
            response = await asyncio.to_thread(scraper.get, url, headers=headers, timeout=REQUEST_TIMEOUT)
        except Exception as err:  # мережа, DNS, таймаут, cloudscraper-челендж
            raise ScraperError(f"Request to {url} failed: {err}") from err

        status = getattr(response, "status_code", None)
        if status != 200:
            raise ScraperError(f"{url} returned HTTP {status}")

        content = response.text or ""
        if not any(marker in content for marker in _PAGE_MARKERS):
            raise ScraperError(f"{url} returned unexpected page ({len(content)} bytes)")
        return content

    async def get_power_off_periods(self) -> tuple[DayPeriods, DayPeriods]:
        """Get power off periods from the website.

        Returns:
            Tuple of (today_periods, tomorrow_periods). Кожен елемент:
              * list — сайт дав графік на цей день (порожній list = відключень немає);
              * None — сайт не має даних на цей день (ще не опубліковано / «Немає даних»).

        Raises:
            ScraperError: сайт недоступний або сторінка не схожа на графік.
        """
        content = await self._fetch_page()
        return self.parse_page(content)

    def parse_page(self, content: str) -> tuple[DayPeriods, DayPeriods]:
        """Розпарсити HTML сторінки черги."""
        soup = BeautifulSoup(content, "html.parser")
        today_results: list[PowerOffPeriod] = []
        tomorrow_results: list[PowerOffPeriod] = []

        # Спочатку шукаємо блоки scale_info_periods для сьогодні та завтра
        all_scale_info_periods = soup.find_all("div", class_="scale_info_periods")
        today_periods_found = False
        tomorrow_periods_found = False

        for scale_info_block in all_scale_info_periods:
            if not isinstance(scale_info_block, Tag):
                continue

            title = scale_info_block.find("h4", class_="scale_info_title")
            if not isinstance(title, Tag):
                continue

            title_text = title.get_text().strip().lower()
            if "сьогодні" in title_text or "сегодня" in title_text:
                periods = self._parse_periods_from_text_block(scale_info_block, today=True)
                if periods:
                    today_results.extend(periods)
                    today_periods_found = True
            elif "завтра" in title_text:
                periods = self._parse_periods_from_text_block(scale_info_block, today=False)
                if periods:
                    tomorrow_results.extend(periods)
                    tomorrow_periods_found = True

        # Чи є на сторінці погодинна шкала для дня (означає, що графік на день опубліковано,
        # навіть якщо в ньому немає жодного відключення).
        today_scale_found = False
        tomorrow_scale_found = False

        if not today_periods_found or not tomorrow_periods_found:
            all_day_titles = soup.find_all("h4", class_="ch_day_title")
            LOGGER.debug("Знайдено %d заголовків ch_day_title", len(all_day_titles))
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
                        break  # дійшли до наступного дня — шкали для цього дня немає

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

        today_final: DayPeriods = (
            self.merge_periods(today_results) if (today_periods_found or today_scale_found) else None
        )
        tomorrow_final: DayPeriods = (
            self.merge_periods(tomorrow_results) if (tomorrow_periods_found or tomorrow_scale_found) else None
        )

        LOGGER.debug(
            "Парсинг завершено: сьогодні=%s, завтра=%s",
            "немає даних" if today_final is None else len(today_final),
            "немає даних" if tomorrow_final is None else len(tomorrow_final),
        )
        return today_final, tomorrow_final

    def _parse_periods_from_text_block(self, scale_info_block: Tag, today: bool) -> list[PowerOffPeriod]:
        """Parse periods from a specific scale_info_periods block."""
        periods: list[PowerOffPeriod] = []

        periods_items = scale_info_block.find("div", class_="periods_items")
        if not periods_items or not isinstance(periods_items, Tag):
            return periods

        # Парсимо кожен період з тексту типу "З 12:00 до 14:30"
        # BeautifulSoup.get_text() автоматично видаляє HTML теги, тому час буде просто "12:00"
        period_spans = periods_items.find_all("span")
        for span in period_spans:
            if not isinstance(span, Tag):
                continue
            text = span.get_text()
            # Шукаємо патерн "З HH:MM до HH:MM"
            # get_text() вже видалив <b> теги, тому шукаємо просто "З 12:00 до 14:30"
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
