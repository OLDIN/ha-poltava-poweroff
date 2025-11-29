"""The Poltava Power Offline integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .coordinator import PoltavaPowerOffCoordinator

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)

# Схема для service
SERVICE_REFRESH = "refresh"
SERVICE_SCHEMA: vol.Schema = vol.Schema({})  # Порожня схема, service не потребує параметрів


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the component."""
    # Реєструємо статичний шлях для custom card (async версія)
    from homeassistant.components.http import StaticPathConfig
    import os

    # Використовуємо абсолютний шлях до www директорії
    integration_dir = os.path.dirname(os.path.dirname(__file__))
    www_path = os.path.join(integration_dir, "poltava_poweroff", "www")
    await hass.http.async_register_static_paths([StaticPathConfig("/local/poltava_poweroff", www_path, False)])

    _LOGGER.info(
        "Custom card available at: /local/poltava_poweroff/poweroff-timeline-card.js\n"
        "Add it manually: Settings → Dashboards → Resources → Add Resource"
    )

    # Реєструємо service для ручного оновлення
    async def async_handle_refresh(call: ServiceCall) -> None:
        """Handle refresh service call."""
        _LOGGER.info("Manual refresh requested via service")
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator: PoltavaPowerOffCoordinator = entry.runtime_data
            await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, async_handle_refresh, schema=SERVICE_SCHEMA)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Poltava Power Offline from a config entry."""

    coordinator = PoltavaPowerOffCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
