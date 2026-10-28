"""Select "view queue": which queue the card shows.

It does not affect sensors, the calendar or automations: they always follow the configured queue.
The choice survives restarts (RestoreEntity). Attributes use the same format as
sensor.power_state, plus home_queue and loading; the card reads them directly.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import PowerOffGroup, group_display
from .coordinator import PoltavaPowerOffCoordinator

LOGGER = logging.getLogger(__name__)

OPTIONS = [group_display(g.value) for g in PowerOffGroup]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the view-queue select."""
    coordinator: PoltavaPowerOffCoordinator = config_entry.runtime_data
    async_add_entities([PoltavaViewQueueSelect(coordinator)])


class PoltavaViewQueueSelect(CoordinatorEntity[PoltavaPowerOffCoordinator], SelectEntity, RestoreEntity):
    """Which queue the card shows."""

    _attr_icon = "mdi:format-list-numbered"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = OPTIONS
    _attr_name = "Poweroff view queue"

    def __init__(self, coordinator: PoltavaPowerOffCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-view_queue"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in OPTIONS:
            group = last.state.replace(".", "-")
            if group != self.coordinator.view_group:
                # The cache is already loaded; fresh data is fetched in the background without blocking HA startup
                self.hass.async_create_task(self.coordinator.async_set_view_group(group))

    @property
    def current_option(self) -> str:
        return group_display(self.coordinator.view_group)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_view_group(option.replace(".", "-"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        view = self.coordinator.view
        return {
            **self.coordinator.queue_attributes(view),
            "home_queue": self.coordinator.queue_display,
            "loading": view.loading,
        }
