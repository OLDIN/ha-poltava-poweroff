"""Provides the PoltavaPowerOffCoordinator class for polling power off periods."""

from datetime import datetime, timedelta
import logging

from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, POWEROFF_GROUP_CONF, UPDATE_INTERVAL, PowerOffGroup, STATE_ON, STATE_OFF
from .energyua_scrapper import EnergyUaScrapper
from .entities import PowerOffPeriod

LOGGER = logging.getLogger(__name__)

TIMEFRAME_TO_CHECK = timedelta(hours=24)


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
        self.api = EnergyUaScrapper(self.group)
        self.periods: list[PowerOffPeriod] = []  # Для сумісності з calendar - всі періоди
        self.today_periods: list[PowerOffPeriod] = []
        self.tomorrow_periods: list[PowerOffPeriod] = []

    async def _async_update_data(self) -> dict:
        """Fetch power off periods from scrapper."""
        try:
            LOGGER.debug("Starting _async_update_data for group %s", self.group)
            await self._fetch_periods()
            LOGGER.debug("After _fetch_periods, periods count: %d", len(self.periods))
            return {}  # noqa: TRY300
        except Exception as err:
            LOGGER.exception("Cannot obtain power offs periods for group %s", self.group)
            msg = f"Power offs not polled: {err}"
            raise UpdateFailed(msg) from err

    async def _fetch_periods(self) -> None:
        LOGGER.debug("Calling api.get_power_off_periods() for group %s", self.group)
        today_periods, tomorrow_periods = await self.api.get_power_off_periods()
        self.today_periods = today_periods
        self.tomorrow_periods = tomorrow_periods
        # Для calendar - об'єднуємо всі періоди
        self.periods = today_periods + tomorrow_periods
        LOGGER.debug(
            "Fetched %d today periods, %d tomorrow periods", len(self.today_periods), len(self.tomorrow_periods)
        )

    def _get_next_power_change_dt(self, on: bool, use_tomorrow_if_no_today: bool = True) -> datetime | None:
        """Get the next power on/off.

        Args:
            on: True for power on, False for power off
            use_tomorrow_if_no_today: If True and no today events found, check tomorrow
        """
        now = dt_util.now()
        # Спочатку шукаємо в сьогоднішніх періодах
        today_events = []
        for period in self.today_periods:
            start, end = period.to_datetime_period(now.tzinfo)
            if start > now or end > now:
                today_events.append(self._get_calendar_event(start, end))

        if today_events:
            if on:
                dts = sorted(event.end for event in today_events)
            else:
                dts = sorted(event.start for event in today_events)
            LOGGER.debug("Next dts from today: %s", dts)
            for dt in dts:
                if dt > now:
                    return dt  # type: ignore

        # Якщо сьогодні немає більше подій і дозволено, шукаємо в завтрашніх
        if use_tomorrow_if_no_today and self.tomorrow_periods:
            tomorrow_events = []
            for period in self.tomorrow_periods:
                start, end = period.to_datetime_period(now.tzinfo)
                tomorrow_events.append(self._get_calendar_event(start, end))

            if tomorrow_events:
                if on:
                    dts = sorted(event.end for event in tomorrow_events)
                else:
                    dts = sorted(event.start for event in tomorrow_events)
                LOGGER.debug("Next dts from tomorrow: %s", dts)
                if dts:
                    return dts[0]  # type: ignore

        return None

    @property
    def next_poweroff(self) -> datetime | None:
        """Get the next poweroff time."""
        dt = self._get_next_power_change_dt(on=False)
        LOGGER.debug("Next poweroff: %s", dt)
        return dt

    @property
    def next_poweron(self) -> datetime | None:
        """Get next connectivity time."""
        dt = self._get_next_power_change_dt(on=True)
        LOGGER.debug("Next powerof: %s", dt)
        return dt

    @property
    def current_state(self) -> str:
        """Get the current state."""
        now = dt_util.now()
        event = self.get_event_at(now)
        return STATE_OFF if event else STATE_ON

    def get_event_at(self, at: datetime) -> CalendarEvent | None:
        """Get the current event."""
        # Спочатку перевіряємо сьогоднішні періоди
        for period in self.today_periods:
            start, end = period.to_datetime_period(at.tzinfo)
            # Використовуємо start <= at < end, щоб коли at == end, подія вже не активна
            # Це важливо для періодів, що закінчуються в 12:00 (опівночі або опівдня)
            if start <= at < end:
                return self._get_calendar_event(start, end)
        return None

    def get_events_between(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Get all events."""
        events = []
        for period in self.periods:
            start, end = period.to_datetime_period(start_date.tzinfo)
            if start_date <= start <= end_date or start_date <= end <= end_date:
                events.append(self._get_calendar_event(start, end))
        return events

    def _get_calendar_event(self, start: datetime, end: datetime) -> CalendarEvent:
        return CalendarEvent(
            start=start,
            end=end,
            summary=STATE_OFF,
        )

    def get_next_off_time(self) -> str | None:
        """Get the next poweroff time as string."""
        dt = self.next_poweroff
        return dt.isoformat() if dt else None

    def get_next_on_time(self) -> str | None:
        """Get next connectivity time as string."""
        dt = self.next_poweron
        return dt.isoformat() if dt else None
