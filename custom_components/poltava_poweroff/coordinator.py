"""Provides the PoltavaPowerOffCoordinator class for polling power off periods.

Key ideas:
  * the schedule is stored by **absolute date** (not "today/tomorrow") and cached on disk:
    site down -> keep showing the last good schedule; HA restart -> schedule from cache;
    at midnight "tomorrow" becomes "today" by itself;
  * the configured ("home") queue drives sensors, the calendar and automations and is always polled;
  * the "view" queue (select entity) is for the card only; in the background only the home queue
    and the last selected one are polled, others come from cache or are fetched on switch.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CACHE_KEEP_DAYS,
    DOMAIN,
    POWEROFF_GROUP_CONF,
    STATE_OFF,
    STATE_ON,
    STORAGE_KEY,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
    PowerOffGroup,
    group_display,
)
from .energyua_scrapper import EnergyUaScrapper
from .entities import PowerOffPeriod

LOGGER = logging.getLogger(__name__)

TIMEFRAME_TO_CHECK = timedelta(hours=24)

Schedule = dict[str, list[tuple[float, float]]]  # "YYYY-MM-DD" -> [(start, end), ...]


@dataclass
class QueueState:
    """Schedule of one queue plus freshness metadata."""

    group: str
    schedule: Schedule = field(default_factory=dict)
    changed_at: datetime | None = None  # when the schedule last CHANGED
    success_at: datetime | None = None  # last successful response from the site
    attempt_at: datetime | None = None  # last attempt, successful or not
    error: str | None = None
    failures: int = 0
    loading: bool = False

    # -- dates
    @staticmethod
    def _today() -> date:
        return dt_util.now().date()

    def periods_for(self, day: date, today_flag: bool) -> list[PowerOffPeriod]:
        return [PowerOffPeriod(s, e, today=today_flag) for s, e in self.schedule.get(day.isoformat(), [])]

    @property
    def today_periods(self) -> list[PowerOffPeriod]:
        return self.periods_for(self._today(), True)

    @property
    def tomorrow_periods(self) -> list[PowerOffPeriod]:
        return self.periods_for(self._today() + timedelta(days=1), False)

    @property
    def today_known(self) -> bool:
        return self._today().isoformat() in self.schedule

    @property
    def tomorrow_known(self) -> bool:
        return (self._today() + timedelta(days=1)).isoformat() in self.schedule

    @property
    def has_cached_data(self) -> bool:
        return self.today_known or self.tomorrow_known

    @property
    def is_stale(self) -> bool:
        return self.error is not None

    # -- updates
    def apply(self, today: list[PowerOffPeriod] | None, tomorrow: list[PowerOffPeriod] | None, now: datetime) -> bool:
        """Apply a site response. None for a day means "no data": keep what we already know."""
        self.attempt_at = now
        self.success_at = now
        self.error = None
        self.failures = 0
        d0 = now.date()
        new = dict(self.schedule)
        if today is not None:
            new[d0.isoformat()] = _to_tuples(today)
        if tomorrow is not None:
            new[(d0 + timedelta(days=1)).isoformat()] = _to_tuples(tomorrow)
        changed = new != self.schedule
        if changed:
            self.schedule = new
            self.changed_at = now
        self.prune()
        return changed

    def fail(self, err: Exception, now: datetime) -> None:
        self.attempt_at = now
        self.failures += 1
        self.error = str(err) or err.__class__.__name__

    def prune(self) -> None:
        keep_from = (self._today() - timedelta(days=CACHE_KEEP_DAYS)).isoformat()
        self.schedule = {day: p for day, p in self.schedule.items() if day >= keep_from}

    def is_fresh(self, max_age: timedelta) -> bool:
        return self.success_at is not None and dt_util.now() - self.success_at < max_age

    # -- (de)serialization for Store
    def to_json(self) -> dict[str, Any]:
        return {
            "schedule": {day: [list(p) for p in periods] for day, periods in self.schedule.items()},
            "schedule_changed_at": _iso(self.changed_at),
            "last_success_at": _iso(self.success_at),
        }

    @classmethod
    def from_json(cls, group: str, raw: dict[str, Any]) -> QueueState:
        state = cls(
            group=group,
            schedule={
                day: [(float(s), float(e)) for s, e in periods] for day, periods in (raw.get("schedule") or {}).items()
            },
            changed_at=_parse_dt(raw.get("schedule_changed_at")),
            success_at=_parse_dt(raw.get("last_success_at")),
        )
        state.prune()
        return state


class PoltavaPowerOffCoordinator(DataUpdateCoordinator):
    """Coordinates the polling of power off periods."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.hass = hass
        self.config_entry = config_entry
        self.group: PowerOffGroup = config_entry.data[POWEROFF_GROUP_CONF]
        self.view_group: str = str(self.group)
        self.queues: dict[str, QueueState] = {str(self.group): QueueState(str(self.group))}
        self._scrapers: dict[str, EnergyUaScrapper] = {str(self.group): EnergyUaScrapper(self.group)}
        self._locks: dict[str, asyncio.Lock] = {}
        self._store: Store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{config_entry.entry_id}")

    # ------------------------------------------------------------- accessors

    @property
    def api(self) -> EnergyUaScrapper:
        """Scraper of the home queue (backwards compatibility; tests patch this one)."""
        return self._scrapers[str(self.group)]

    def _scraper(self, group: str) -> EnergyUaScrapper:
        if group not in self._scrapers:
            self._scrapers[group] = EnergyUaScrapper(group)  # type: ignore[arg-type]
        return self._scrapers[group]

    def queue_state(self, group: str) -> QueueState:
        if group not in self.queues:
            self.queues[group] = QueueState(group)
        return self.queues[group]

    @property
    def home(self) -> QueueState:
        return self.queue_state(str(self.group))

    @property
    def view(self) -> QueueState:
        return self.queue_state(self.view_group)

    # Home queue properties, used by sensors, the calendar and tests
    @property
    def schedule(self) -> Schedule:
        return self.home.schedule

    @property
    def schedule_changed_at(self) -> datetime | None:
        return self.home.changed_at

    @property
    def last_success_at(self) -> datetime | None:
        return self.home.success_at

    @property
    def last_attempt_at(self) -> datetime | None:
        return self.home.attempt_at

    @property
    def last_error(self) -> str | None:
        return self.home.error

    @property
    def consecutive_failures(self) -> int:
        return self.home.failures

    @property
    def has_cached_data(self) -> bool:
        return self.home.has_cached_data

    @property
    def today_periods(self) -> list[PowerOffPeriod]:
        return self.home.today_periods

    @property
    def tomorrow_periods(self) -> list[PowerOffPeriod]:
        return self.home.tomorrow_periods

    @property
    def periods(self) -> list[PowerOffPeriod]:
        """All periods for today + tomorrow."""
        return self.today_periods + self.tomorrow_periods

    @property
    def today_known(self) -> bool:
        return self.home.today_known

    @property
    def tomorrow_known(self) -> bool:
        return self.home.tomorrow_known

    @property
    def is_stale(self) -> bool:
        return self.home.is_stale

    @property
    def queue_display(self) -> str:
        return group_display(self.group)

    # ------------------------------------------------------------------ cache

    async def async_load_cache(self) -> None:
        """Load schedules from disk (called before the first request)."""
        try:
            raw = await self._store.async_load()
        except Exception:
            LOGGER.exception("Cannot load cached schedule, starting empty")
            return
        if not raw:
            return
        if "groups" in raw:
            for group, data in raw["groups"].items():
                self.queues[group] = QueueState.from_json(group, data)
            self.view_group = raw.get("view_group") or self.view_group
        elif raw.get("group"):  # 0.3.0-dev format: a single schedule
            self.queues[raw["group"]] = QueueState.from_json(raw["group"], raw)
        LOGGER.debug("Loaded cached schedules: %s", {g: q.schedule for g, q in self.queues.items()})

    def _cache_payload(self) -> dict[str, Any]:
        return {
            "home_group": str(self.group),
            "view_group": self.view_group,
            "groups": {g: q.to_json() for g, q in self.queues.items() if q.schedule},
        }

    async def _async_save(self) -> None:
        try:
            await self._store.async_save(self._cache_payload())
        except Exception:
            LOGGER.exception("Cannot save schedule cache")

    # ----------------------------------------------------------------- fetch

    async def _fetch_queue(self, group: str) -> QueueState:
        """Fetch a queue from the site. Errors are recorded on the queue state and re-raised."""
        state = self.queue_state(group)
        lock = self._locks.setdefault(group, asyncio.Lock())
        async with lock:
            now = dt_util.now()
            try:
                today, tomorrow = await self._scraper(group).get_power_off_periods()
            except Exception as err:
                state.fail(err, now)
                raise
            if state.apply(today, tomorrow, now):
                LOGGER.info("Schedule for queue %s changed: %s", group, state.schedule)
        return state

    async def _async_update_data(self) -> dict:
        """Fetch power off periods from scrapper. Never wipes known data on failure."""
        home = str(self.group)
        try:
            await self._fetch_queue(home)
        except Exception as err:
            if self.home.has_cached_data:
                # The site is down: keep the last good schedule and mark it as stale.
                LOGGER.warning(
                    "energy-ua is unavailable (%s, attempt %d). Showing the cached schedule from %s",
                    self.home.error,
                    self.home.failures,
                    self.home.success_at,
                )
            else:
                LOGGER.error("Cannot obtain power offs periods for group %s: %s", home, self.home.error)
                raise UpdateFailed(f"Power offs not polled: {self.home.error}") from err

        if self.view_group != home:
            try:
                await self._fetch_queue(self.view_group)
            except Exception:  # noqa: BLE001 - the view queue is not critical
                LOGGER.debug("Cannot refresh view queue %s: %s", self.view_group, self.view.error)

        await self._async_save()
        return {"home": home, "view": self.view_group}

    async def async_set_view_group(self, group: str, fetch: bool = True) -> None:
        """Switch the view queue (called by the select entity)."""
        self.view_group = group
        state = self.view
        if fetch and not state.is_fresh(timedelta(seconds=UPDATE_INTERVAL)):
            state.loading = True
            self.async_update_listeners()
            try:
                await self._fetch_queue(group)
            except Exception:  # noqa: BLE001
                LOGGER.warning("Cannot load the schedule for queue %s: %s", group, state.error)
            finally:
                state.loading = False
        await self._async_save()
        self.async_update_listeners()

    # ------------------------------------------------------- attributes

    def queue_attributes(self, state: QueueState) -> dict[str, Any]:
        """Card attributes; the same format for the home queue and the view queue."""
        return {
            "poweroff_periods_today": [{"start": p.start, "end": p.end} for p in state.today_periods],
            "poweroff_periods_tomorrow": [{"start": p.start, "end": p.end} for p in state.tomorrow_periods],
            "next_off": _iso(self._next_change(state, on=False)),
            "next_on": _iso(self._next_change(state, on=True)),
            "queue": group_display(state.group),
            "today_known": state.today_known,
            "tomorrow_known": state.tomorrow_known,
            "schedule_changed_at": _iso(state.changed_at),
            "last_success_at": _iso(state.success_at),
            "last_attempt_at": _iso(state.attempt_at),
            "data_stale": state.is_stale,
            "last_error": state.error,
        }

    # --------------------------------------------------------- next on / off

    @staticmethod
    def intervals(state: QueueState) -> list[tuple[datetime, datetime]]:
        """Outages as absolute intervals for yesterday/today/tomorrow, merged across midnight.

        "today 21:00–24:00" + "tomorrow 00:00–02:00" -> one interval 21:00–02:00, so power
        returns at 02:00, not 00:00. Times are counted from local midnight, which is also
        correct on DST transition days.
        """
        today = dt_util.now().date()
        raw: list[tuple[datetime, datetime]] = []
        for day in (today - timedelta(days=1), today, today + timedelta(days=1)):
            midnight = dt_util.start_of_local_day(day)
            for start_h, end_h in state.schedule.get(day.isoformat(), []):
                if float(end_h) == 0.0 or float(end_h) < float(start_h):
                    end_h = 24.0  # end of the day
                raw.append((midnight + timedelta(hours=float(start_h)), midnight + timedelta(hours=float(end_h))))
        raw.sort()
        merged: list[tuple[datetime, datetime]] = []
        for start_dt, end_dt in raw:
            if merged and start_dt <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end_dt))
            else:
                merged.append((start_dt, end_dt))
        return merged

    def _next_change(self, state: QueueState, on: bool) -> datetime | None:
        """Next power on (on=True) or power off for a queue."""
        now = dt_util.now()
        for start, end in self.intervals(state):
            if end <= now:
                continue
            if on:
                return end  # end of the current or the next outage
            if start > now:
                return start  # start of the next one (skip the outage in progress)
        return None

    @property
    def next_poweroff(self) -> datetime | None:
        """Get the next poweroff time."""
        return self._next_change(self.home, on=False)

    @property
    def next_poweron(self) -> datetime | None:
        """Get next connectivity time."""
        return self._next_change(self.home, on=True)

    @property
    def current_state(self) -> str:
        """Get the current state."""
        return STATE_OFF if self.get_event_at(dt_util.now()) else STATE_ON

    def get_event_at(self, at: datetime) -> CalendarEvent | None:
        """The outage in progress at `at` (end exclusive)."""
        for start, end in self.intervals(self.home):
            if start <= at < end:
                return self._get_calendar_event(start, end)
        return None

    def get_current_or_next_event(self) -> CalendarEvent | None:
        """The current or next upcoming outage (what HA expects from CalendarEntity.event)."""
        now = dt_util.now()
        for start, end in self.intervals(self.home):
            if end > now:
                return self._get_calendar_event(start, end)
        return None

    def get_events_between(self, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        """All outages overlapping the window, including ones that cover it entirely."""
        return [
            self._get_calendar_event(start, end)
            for start, end in self.intervals(self.home)
            if start < end_date and end > start_date
        ]

    def _get_calendar_event(self, start: datetime, end: datetime) -> CalendarEvent:
        return CalendarEvent(start=start, end=end, summary=STATE_OFF)

    def get_next_off_time(self) -> str | None:
        """Get the next poweroff time as string."""
        return _iso(self.next_poweroff)

    def get_next_on_time(self) -> str | None:
        """Get next connectivity time as string."""
        return _iso(self.next_poweron)


def _to_tuples(periods: list[PowerOffPeriod]) -> list[tuple[float, float]]:
    return [(float(p.start), float(p.end)) for p in periods]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    return dt_util.parse_datetime(str(value))
