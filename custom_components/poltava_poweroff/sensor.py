import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import STATE_OFF, STATE_ON
from .coordinator import PoltavaPowerOffCoordinator

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PoltavaPowerOffSensorDescription(SensorEntityDescription):
    """Poltava PowerOff entity description."""

    val_func: Callable[[PoltavaPowerOffCoordinator], Any]


SENSOR_TYPES: tuple[PoltavaPowerOffSensorDescription, ...] = (
    PoltavaPowerOffSensorDescription(
        key="electricity",
        icon="mdi:transmission-tower",
        device_class=SensorDeviceClass.ENUM,
        name="Power state",
        options=[STATE_ON, STATE_OFF],
        val_func=lambda coordinator: coordinator.current_state,
    ),
    PoltavaPowerOffSensorDescription(
        key="next_poweroff",
        icon="mdi:calendar-remove",
        device_class=SensorDeviceClass.TIMESTAMP,
        name="Next power off",
        val_func=lambda coordinator: coordinator.next_poweroff,
    ),
    PoltavaPowerOffSensorDescription(
        key="next_poweron",
        icon="mdi:calendar-check",
        device_class=SensorDeviceClass.TIMESTAMP,
        name="Next power on",
        val_func=lambda coordinator: coordinator.next_poweron,
    ),
    PoltavaPowerOffSensorDescription(
        key="schedule_updated",
        icon="mdi:calendar-sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        name="Schedule updated",
        val_func=lambda coordinator: coordinator.schedule_changed_at,
    ),
    PoltavaPowerOffSensorDescription(
        key="last_fetch",
        icon="mdi:cloud-check-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Schedule last fetch",
        val_func=lambda coordinator: coordinator.last_success_at,
    ),
)

# Нові сенсори-мітки часу не дублюють великі атрибути (менше записів у recorder).
# Старі три сенсори лишають атрибути як були — на них можуть посилатися дашборди/автоматизації.
NO_ATTRIBUTES_KEYS = {"schedule_updated", "last_fetch"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Poltava PowerOff sensors."""
    LOGGER.debug("Setup new entry: %s", config_entry)
    coordinator: PoltavaPowerOffCoordinator = config_entry.runtime_data
    async_add_entities(PoltavaPowerOffSensor(coordinator, description) for description in SENSOR_TYPES)


class PoltavaPowerOffSensor(CoordinatorEntity[PoltavaPowerOffCoordinator], SensorEntity):
    coordinator: PoltavaPowerOffCoordinator

    def __init__(
        self,
        coordinator: PoltavaPowerOffCoordinator,
        entity_description: PoltavaPowerOffSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{coordinator.group}-{self.entity_description.key}"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.entity_description.val_func(self.coordinator)  # type: ignore

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.entity_description.key in NO_ATTRIBUTES_KEYS:
            return None
        attrs = self.coordinator.queue_attributes(self.coordinator.home)

        # poweroff_periods — для старих карток: сьогоднішні, а коли вони всі минули — завтрашні
        now_dt = dt_util.now()
        has_future_today = any(
            period.to_datetime_period(now_dt.tzinfo)[1] > now_dt for period in self.coordinator.today_periods
        )
        active = attrs["poweroff_periods_today"]
        if not has_future_today and attrs["poweroff_periods_tomorrow"]:
            active = attrs["poweroff_periods_tomorrow"]
        return {"poweroff_periods": active, **attrs}
