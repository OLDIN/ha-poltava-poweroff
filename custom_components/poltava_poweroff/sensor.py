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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Poltava PowerOff sensors."""
    LOGGER.debug("Setup new entry: %s", config_entry)
    coordinator: PoltavaPowerOffCoordinator = config_entry.runtime_data
    async_add_entities(PoltavaPowerOffSensor(coordinator, description) for description in SENSOR_TYPES)


class PoltavaPowerOffSensor(SensorEntity):
    def __init__(
        self,
        coordinator: PoltavaPowerOffCoordinator,
        entity_description: PoltavaPowerOffSensorDescription,
    ) -> None:
        """Initialize the sensor."""
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
        periods = []
        for period in self.coordinator.periods:
            if period.today:
                periods.append({"start": period.start, "end": period.end})

        return {
            "poweroff_periods": periods,
            "next_off": self.coordinator.get_next_off_time(),
            "next_on": self.coordinator.get_next_on_time(),
        }
