"""The bundled blueprints load in a real HA core and send the expected notifications."""

from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.poltava_poweroff.const import DOMAIN, POWEROFF_GROUP_CONF
from custom_components.poltava_poweroff.entities import PowerOffPeriod

BLUEPRINTS = Path(__file__).parent.parent / "blueprints" / "automation" / "poltava_poweroff"
SCRAPER = "custom_components.poltava_poweroff.sources.energy_ua.EnergyUaScrapper.get_power_off_periods"


def _install_blueprints(hass: HomeAssistant) -> None:
    target = Path(hass.config.path("blueprints", "automation", "poltava_poweroff"))
    target.mkdir(parents=True, exist_ok=True)
    for file in BLUEPRINTS.glob("*.yaml"):
        shutil.copy(file, target / file.name)


def _phone(hass: HomeAssistant) -> str:
    entry = MockConfigEntry(domain="mobile_app")
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("mobile_app", "phone")}, name="Test Phone"
    )
    return device.id


async def test_schedule_changed_blueprint_notifies(hass: HomeAssistant) -> None:
    _install_blueprints(hass)
    notify = async_mock_service(hass, "notify", "mobile_app_test_phone")
    phone = _phone(hass)

    entry = MockConfigEntry(domain=DOMAIN, data={POWEROFF_GROUP_CONF: "4-1"}, title="Poltava")
    entry.add_to_hass(hass)
    with patch(SCRAPER, AsyncMock(return_value=([PowerOffPeriod(8, 9.5, True)], None))):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "poltava_poweroff/schedule_changed.yaml",
                    "input": {"notify_devices": [phone]},
                }
            }
        },
    )
    await hass.async_block_till_done()
    assert notify == []

    # Tomorrow's schedule is published
    with patch(SCRAPER, AsyncMock(return_value=([PowerOffPeriod(8, 9.5, True)], [PowerOffPeriod(15, 17.5, False)]))):
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
    assert len(notify) == 1
    assert notify[0].data["title"] == "📅 Графік на завтра"
    assert notify[0].data["message"] == "Черга 4.1: 15:00–17:30 (2.5 год без світла)."

    # Today's schedule changes
    with patch(SCRAPER, AsyncMock(return_value=([PowerOffPeriod(8, 10, True)], [PowerOffPeriod(15, 17.5, False)]))):
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
    assert len(notify) == 2
    assert notify[1].data["title"] == "⚠️ Графік на сьогодні змінився"
    assert notify[1].data["message"] == "Черга 4.1: 08:00–10:00 (2 год без світла). Було: 08:00–09:30."


async def test_outage_warning_blueprint_fires_before_outage(hass: HomeAssistant, freezer) -> None:
    _install_blueprints(hass)
    notify = async_mock_service(hass, "notify", "mobile_app_test_phone")
    tts = async_mock_service(hass, "tts", "speak")
    phone = _phone(hass)
    now = dt_util.now().replace(second=0, microsecond=0)
    freezer.move_to(now)
    hass.states.async_set("sensor.next_off", (now + timedelta(minutes=30)).isoformat(), {"device_class": "timestamp"})

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "poltava_poweroff/outage_warning.yaml",
                    "input": {
                        "next_off_sensor": "sensor.next_off",
                        "minutes_before": 5,
                        "notify_devices": [phone],
                        "tts_entity": "tts.piper",
                        "media_player": "media_player.echo",
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    assert notify == []

    # The schedule moves the outage closer: 4 minutes from now
    off = now + timedelta(minutes=4)
    hass.states.async_set("sensor.next_off", off.isoformat(), {"device_class": "timestamp"})
    await hass.async_block_till_done()
    assert len(notify) == 1
    assert notify[0].data["message"] == f"Світло буде вимкнене через 5 хв (о {dt_util.as_local(off):%H:%M})."
    assert len(tts) == 1
    assert tts[0].data["media_player_entity_id"] == "media_player.echo"
