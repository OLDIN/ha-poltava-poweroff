"""Provides classes for scraping power off periods from the Energy UA website."""

from __future__ import annotations

import asyncio
import re

import cloudscraper  # type: ignore[import-untyped]
from bs4 import BeautifulSoup, Tag

from .const import PowerOffGroup
from .entities import PowerOffPeriod

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
            response = await asyncio.to_thread(scraper.get, URL.format(self.group))
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

    async def get_power_off_periods(self) -> list[PowerOffPeriod]:
        """Get power off periods from the website."""
        scraper = await self._get_scraper()
        response = await asyncio.to_thread(scraper.get, URL.format(self.group))
        content = response.text
        soup = BeautifulSoup(content, "html.parser")
        results = []

        # Спочатку парсимо точні періоди з текстового опису (якщо є)
        periods_text = self._parse_periods_from_text(soup, today=True)
        if periods_text:
            results.extend(periods_text)
        else:
            # Fallback до старого методу парсингу з scale_hours
            scale_hours = soup.find_all("div", class_="scale_hours")
            if len(scale_hours) > 0:
                scale_hours_el = scale_hours[0].find_all("div", class_="scale_hours_el")
                for item in scale_hours_el:
                    if item.find("span", class_="hour_active"):
                        start, end = self._parse_item(item)
                        results.append(PowerOffPeriod(start, end, today=True))

        results = self.merge_periods(results)

        # Парсимо періоди на завтра
        tomorrow_periods = self._parse_periods_from_text(soup, today=False)
        if tomorrow_periods:
            results += self.merge_periods(tomorrow_periods)
        else:
            # Fallback до старого методу
            scale_hours = soup.find_all("div", class_="scale_hours")
            if len(scale_hours) > 1:
                tomorrow_results = []
                scale_hours_el_tomorrow = scale_hours[1].find_all("div", class_="scale_hours_el")
                for item in scale_hours_el_tomorrow:
                    if item.find("span", class_="hour_active"):
                        start, end = self._parse_item(item)
                        tomorrow_results.append(PowerOffPeriod(start, end, today=False))
                results += self.merge_periods(tomorrow_results)

        return results

    def _parse_periods_from_text(self, soup: BeautifulSoup, today: bool) -> list[PowerOffPeriod]:
        """Parse periods from text description (more accurate than HTML structure)."""
        periods: list[PowerOffPeriod] = []
        # Шукаємо блок з періодами відключень
        scale_info_periods = soup.find("div", class_="scale_info_periods")
        if not scale_info_periods or not isinstance(scale_info_periods, Tag):
            return periods

        periods_items = scale_info_periods.find("div", class_="periods_items")
        if not periods_items or not isinstance(periods_items, Tag):
            return periods

        # Парсимо кожен період з тексту типу "З 12:00 до 14:30"
        period_spans = periods_items.find_all("span")
        for span in period_spans:
            if not isinstance(span, Tag):
                continue
            text = span.get_text()
            # Шукаємо патерн "З HH:MM до HH:MM"
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
