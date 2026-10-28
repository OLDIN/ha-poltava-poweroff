"""The Poltava Power Offline integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import PoltavaPowerOffCoordinator

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SELECT, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)

# Configured from the UI only (config entries); there is no YAML configuration
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_REFRESH = "refresh"
SERVICE_SCHEMA: vol.Schema = vol.Schema({})

CARD_URL_BASE = "/local/poltava_poweroff"
CARD_FILE = "poweroff-timeline-card.js"


def _integration_version() -> str:
    try:
        return json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))["version"]
    except Exception:  # noqa: BLE001
        return "0"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the component."""
    from homeassistant.components.http import StaticPathConfig

    www_path = str(Path(__file__).parent / "www")
    try:
        await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL_BASE, www_path, False)])
        version = await hass.async_add_executor_job(_integration_version)
        await _async_register_card_resource(hass, f"{CARD_URL_BASE}/{CARD_FILE}?v={version}")
    except Exception:
        _LOGGER.debug("Card static path / resource registration skipped", exc_info=True)

    async def async_handle_refresh(call: ServiceCall) -> None:
        """Handle refresh service call."""
        _LOGGER.info("Manual refresh requested via service")
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator: PoltavaPowerOffCoordinator | None = getattr(entry, "runtime_data", None)
            if coordinator is not None:
                await coordinator.async_refresh()  # no debounce: this is a manual call

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, async_handle_refresh, schema=SERVICE_SCHEMA)

    return True


async def _async_register_card_resource(hass: HomeAssistant, url: str) -> None:
    """Register the card as a Lovelace resource (storage mode) with ?v=<version>.

    If the resource was added manually, only its ?v= is updated so browsers don't keep an old card.
    """
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None) if lovelace else None
    if resources is None or not hasattr(resources, "async_create_item"):
        return  # resources in YAML mode: leave them alone
    if not resources.loaded:
        await resources.async_load()
        resources.loaded = True
    for item in resources.async_items():
        existing = item.get("url", "")
        if f"poltava_poweroff/{CARD_FILE}" in existing:
            if existing != url:
                await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
            return
    await resources.async_create_item({"res_type": "module", "url": url})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Poltava Power Offline from a config entry."""

    coordinator = PoltavaPowerOffCoordinator(hass, entry)
    # Load the cached schedule first: if the site is down right now we start from cache, not from nothing
    await coordinator.async_load_cache()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
