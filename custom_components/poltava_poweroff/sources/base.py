"""Building blocks for schedule sources.

A source ("provider") fetches the outage schedule of one queue from one site. It needs only:

    class MyProvider:
        site = "example.com"                       # shown in errors and logs
        def __init__(self, queue: str) -> None: ...
        async def get_power_off_periods(self) -> tuple[DayPeriods, DayPeriods]: ...  # (today, tomorrow)
        async def validate(self) -> bool: ...      # the site answers (used by the config flow)

Rules every provider follows:
  * a list for a day = the site has a schedule for it ([] = no outages that day);
  * None for a day = the site has no data for it (not published, "no data"): the cached schedule stays;
  * ScraperError (with a short Ukrainian message, it is shown on the card) = the site is unreachable or
    returned something that is not a schedule. Never return [] for an error page.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

from ..entities import PowerOffPeriod

LOGGER = logging.getLogger(__name__)

DayPeriods = list[PowerOffPeriod] | None  # None = the site has no data for that day


class ScraperError(Exception):
    """The site is unreachable or returned an unexpected page.

    The message is shown on the card as is, so it is written in Ukrainian (UI text).
    """


class ScheduleProvider(Protocol):
    """What the coordinator needs from a source."""

    site: str

    async def get_power_off_periods(self) -> tuple[DayPeriods, DayPeriods]:
        ...

    async def validate(self) -> bool:
        ...


def merge_periods(periods: list[PowerOffPeriod]) -> list[PowerOffPeriod]:
    """Sort and merge adjacent/overlapping periods. An end of 0.0 means 24:00 (midnight at the end of the day)."""
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


class FallbackProvider:
    """Several providers for the same queue, asked in order.

    The first provider that has today's schedule wins; tomorrow is taken from the first provider asked
    that has it. Later providers are asked only when the earlier ones failed or had no schedule for today.
    """

    def __init__(self, providers: Sequence[ScheduleProvider]) -> None:
        self.providers = list(providers)
        self.site = " / ".join(p.site for p in self.providers)
        self.last_source: str | None = None  # which site gave today's schedule, for logs

    async def get_power_off_periods(self) -> tuple[DayPeriods, DayPeriods]:
        errors: list[tuple[str, ScraperError]] = []
        answered = False
        tomorrow: DayPeriods = None
        for provider in self.providers:
            try:
                today, day_after = await provider.get_power_off_periods()
            except ScraperError as err:
                LOGGER.debug("%s failed: %s", provider.site, err)
                errors.append((provider.site, err))
                continue
            answered = True
            if tomorrow is None:
                tomorrow = day_after
            if today is not None:
                self.last_source = provider.site
                return today, tomorrow
        if answered:
            # Some site answered but nobody has today's schedule: unknown, the cache stays
            self.last_source = None
            return None, tomorrow
        sites = ", ні з ".join(site for site, _ in errors)
        # Shown on the card (Ukrainian UI text); the last site's error says what went wrong
        raise ScraperError(f"Не вдалося отримати графік ні з {sites} ({errors[-1][1]})") from errors[-1][1]

    async def validate(self) -> bool:
        """At least one source answers."""
        for provider in self.providers:
            if await provider.validate():
                return True
        return False
