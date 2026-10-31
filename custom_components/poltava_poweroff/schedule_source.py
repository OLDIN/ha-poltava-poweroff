"""Where the schedule comes from: the official poe.pl.ua first, energy-ua.info as a fallback.

energy-ua.info copies the schedule from Poltavaoblenergo and sometimes loses it (after its own
downtime it showed "Немає даних" for a day that had outages), so the official site is asked first.
energy-ua.info is asked when poe.pl.ua is unreachable or has no schedule for today.
A day stays None when neither source has it: the coordinator then keeps the cached schedule.
"""

from __future__ import annotations

import logging

from .energyua_scrapper import DayPeriods, EnergyUaScrapper, ScraperError
from .poe_scrapper import PoeScrapper

LOGGER = logging.getLogger(__name__)


class ScheduleSource:
    """Schedule of one sub-queue from poe.pl.ua with energy-ua.info as a fallback."""

    def __init__(self, group: str) -> None:
        self.group = group
        self.poe = PoeScrapper(group)
        self.energyua = EnergyUaScrapper(group)  # type: ignore[arg-type]
        self.last_source: str | None = None  # "poe.pl.ua", "energy-ua.info" or both, for logs

    async def get_power_off_periods(self) -> tuple[DayPeriods, DayPeriods]:
        poe_error: ScraperError | None = None
        poe_today: DayPeriods = None
        poe_tomorrow: DayPeriods = None
        try:
            poe_today, poe_tomorrow = await self.poe.get_power_off_periods()
        except ScraperError as err:
            poe_error = err
            LOGGER.debug("poe.pl.ua failed for %s: %s", self.group, err)

        if poe_today is not None:
            # The official schedule for today is there; tomorrow appears there first as well
            self.last_source = "poe.pl.ua"
            return poe_today, poe_tomorrow

        try:
            ua_today, ua_tomorrow = await self.energyua.get_power_off_periods()
        except ScraperError as err:
            if poe_error is None:
                # poe.pl.ua answered (no schedule for today yet), energy-ua.info is down: nothing new
                LOGGER.debug("energy-ua.info failed for %s: %s", self.group, err)
                self.last_source = "poe.pl.ua"
                return poe_today, poe_tomorrow
            LOGGER.debug("Both sources failed for %s: poe.pl.ua: %s; energy-ua.info: %s", self.group, poe_error, err)
            # Shown on the card (Ukrainian UI text): which sites failed; details are in the debug log
            raise ScraperError(f"Не вдалося отримати графік ні з poe.pl.ua, ні з energy-ua.info ({err})") from err

        self.last_source = "energy-ua.info" if poe_error else "poe.pl.ua+energy-ua.info"
        return ua_today, poe_tomorrow if poe_tomorrow is not None else ua_tomorrow

    async def validate(self) -> bool:
        """At least one source answers."""
        return await self.poe.validate() or await self.energyua.validate()
