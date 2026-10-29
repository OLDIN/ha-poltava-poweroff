"""Event "schedule changed": fires when the home queue schedule changes.

Event types:
  * ``published`` — a day that was unknown got a schedule (usually tomorrow's in the evening);
  * ``changed`` — the outages of an already known day changed.

Attributes of the last event: queue, date (YYYY-MM-DD), day (today/tomorrow/later),
periods / previous_periods ([{"start": "HH:MM", "end": "HH:MM"}]), periods_text /
previous_periods_text ("09:00–11:00, 15:00–17:30"; empty when there are no outages)
and outage_hours. Nothing fires on the very first fetch after installation.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import EVENT_SCHEDULE_CHANGED, EVENT_SCHEDULE_PUBLISHED, signal_schedule_changed
from .coordinator import PoltavaPowerOffCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the schedule-changed event entity."""
    coordinator: PoltavaPowerOffCoordinator = config_entry.runtime_data
    async_add_entities([PoltavaScheduleChangedEvent(coordinator)])


class PoltavaScheduleChangedEvent(EventEntity):
    """Fires once per changed day of the home queue schedule."""

    _attr_icon = "mdi:calendar-alert"
    _attr_name = "Poweroff schedule changed"
    _attr_translation_key = "schedule_changed"
    _attr_event_types = [EVENT_SCHEDULE_PUBLISHED, EVENT_SCHEDULE_CHANGED]

    def __init__(self, coordinator: PoltavaPowerOffCoordinator) -> None:
        self._entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{self._entry_id}-schedule_changed"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal_schedule_changed(self._entry_id), self._handle_changes)
        )

    @callback
    def _handle_changes(self, changes: list[dict[str, Any]]) -> None:
        for change in changes:
            data = dict(change)
            self._trigger_event(data.pop("event_type"), data)
            self.async_write_ha_state()
