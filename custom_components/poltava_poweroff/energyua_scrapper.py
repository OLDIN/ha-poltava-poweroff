"""Provides classes for scraping power off periods from the Energy UA website."""

from __future__ import annotations

import asyncio
import logging
import re

import cloudscraper  # type: ignore[import-untyped]
from bs4 import BeautifulSoup, Tag

from .const import PowerOffGroup
from .entities import PowerOffPeriod

LOGGER = logging.getLogger(__name__)

URL = "https://energy-ua.info/cherga/{}"


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
            response = await asyncio.to_thread(scraper.get, URL.format(self.group), headers=headers)
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

    async def get_power_off_periods(self) -> tuple[list[PowerOffPeriod], list[PowerOffPeriod]]:
        """Get power off periods from the website.

        Returns:
            Tuple of (today_periods, tomorrow_periods)
        """
        scraper = await self._get_scraper()
        # Додаємо заголовки для запобігання кешування
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        response = await asyncio.to_thread(scraper.get, URL.format(self.group), headers=headers)
        content = response.text
        soup = BeautifulSoup(content, "html.parser")
        today_results: list[PowerOffPeriod] = []
        tomorrow_results: list[PowerOffPeriod] = []

        # Спочатку шукаємо блоки scale_info_periods для сьогодні
        all_scale_info_periods = soup.find_all("div", class_="scale_info_periods")
        today_periods_found = False

        for scale_info_block in all_scale_info_periods:
            if not isinstance(scale_info_block, Tag):
                continue

            # Перевіряємо заголовок
            title = scale_info_block.find("h4", class_="scale_info_title")
            if not isinstance(title, Tag):
                continue

            title_text = title.get_text().strip().lower()
            # Парсимо блоки для сьогодні
            if "сьогодні" in title_text or "сегодня" in title_text:
                periods = self._parse_periods_from_text_block(scale_info_block, today=True)
                if periods:
                    today_results.extend(periods)
                    today_periods_found = True
            # Парсимо блоки для завтра
            elif "завтра" in title_text or "завтра" in title_text:
                periods = self._parse_periods_from_text_block(scale_info_block, today=False)
                if periods:
                    tomorrow_results.extend(periods)

        # Якщо не знайшли періоди для сьогодні через scale_info_periods, використовуємо fallback
        if not today_periods_found:
            LOGGER.debug("Не знайдено періодів через scale_info_periods, використовуємо fallback з scale_hours")
            # Знаходимо всі заголовки ch_day_title та відповідні блоки scale_hours
            all_day_titles = soup.find_all("h4", class_="ch_day_title")
            LOGGER.debug("Знайдено %d заголовків ch_day_title", len(all_day_titles))
            for day_title in all_day_titles:
                if not isinstance(day_title, Tag):
                    continue
                title_text = day_title.get_text().strip().lower()
                LOGGER.debug("Перевіряємо заголовок: %s", title_text)
                # Шукаємо наступний блок scale_hours після цього заголовка
                scale_hours_block = None
                for sibling in day_title.next_siblings:
                    if isinstance(sibling, Tag) and "scale_hours" in sibling.get("class", []):
                        scale_hours_block = sibling
                        break

                if scale_hours_block:
                    if "сьогодні" in title_text:
                        LOGGER.debug("Знайдено блок scale_hours для сьогодні")
                        scale_hours_el = scale_hours_block.find_all("div", class_="scale_hours_el")
                        for item in scale_hours_el:
                            if item.find("span", class_="hour_active"):
                                start, end = self._parse_item(item)
                                period = PowerOffPeriod(start, end, today=True)
                                today_results.append(period)
                                LOGGER.debug("Додано сьогоднішній період: %s-%s", start, end)
                    elif "завтра" in title_text:
                        LOGGER.debug("Знайдено блок scale_hours для завтра")
                        scale_hours_el = scale_hours_block.find_all("div", class_="scale_hours_el")
                        for item in scale_hours_el:
                            if item.find("span", class_="hour_active"):
                                start, end = self._parse_item(item)
                                period = PowerOffPeriod(start, end, today=False)
                                tomorrow_results.append(period)
                                LOGGER.debug("Додано завтрашній період: %s-%s", start, end)

        # Об'єднуємо періоди окремо
        today_results = self.merge_periods(today_results)
        tomorrow_results = self.merge_periods(tomorrow_results)

        # Логуємо результат для діагностики
        LOGGER.debug(
            "Парсинг завершено: %d сьогоднішніх, %d завтрашніх періодів", len(today_results), len(tomorrow_results)
        )
        for period in today_results:
            LOGGER.debug("Сьогоднішній період: %s-%s", period.start, period.end)
        for period in tomorrow_results:
            LOGGER.debug("Завтрашній період: %s-%s", period.start, period.end)

        return today_results, tomorrow_results

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
