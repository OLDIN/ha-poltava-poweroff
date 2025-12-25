"""Provides the implementation of the Poltava PowerOff calendar."""

import datetime
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEntityDescription, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import PoltavaPowerOffCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Poltava outages calendar platform."""
    LOGGER.debug("Setup new entry: %s", config_entry)
    coordinator: PoltavaPowerOffCoordinator = config_entry.runtime_data
    async_add_entities([PoltavaPowerOffCalendar(coordinator)])


class PoltavaPowerOffCalendar(CoordinatorEntity[PoltavaPowerOffCoordinator], CalendarEntity):
    """Implementation of calendar entity."""

    coordinator: PoltavaPowerOffCoordinator

    def __init__(
        self,
        coordinator: PoltavaPowerOffCoordinator,
    ) -> None:
        """Initialize the PoltavaPowerOffCoordinator entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entity_description = CalendarEntityDescription(
            key="calendar",
            name="Poltava PowerOff Calendar",
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{coordinator.group}-{self.entity_description.key}"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event or None."""
        now = dt_util.now()
        LOGGER.debug("Getting current event for %s", now)
        return self.coordinator.get_event_at(now)

    async def async_get_events(
        self,
        hass: HomeAssistant,  # noqa: ARG002
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        LOGGER.debug('Getting all events between "%s" -> "%s"', start_date, end_date)
        return self.coordinator.get_events_between(start_date, end_date)
