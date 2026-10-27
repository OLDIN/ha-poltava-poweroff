"""Інтеграційний тест: справжнє HA-ядро піднімає інтеграцію, сайт лежить після першого запиту."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.poltava_poweroff.const import DOMAIN, POWEROFF_GROUP_CONF
from custom_components.poltava_poweroff.energyua_scrapper import ScraperError
from custom_components.poltava_poweroff.entities import PowerOffPeriod

SCRAPER = "custom_components.poltava_poweroff.energyua_scrapper.EnergyUaScrapper.get_power_off_periods"


async def test_setup_and_outage_keeps_sensors(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={POWEROFF_GROUP_CONF: "4-1"}, title="Poltava")
    entry.add_to_hass(hass)

    ok = AsyncMock(return_value=([PowerOffPeriod(8, 9.5, True)], [PowerOffPeriod(9, 11, False)]))
    with patch(SCRAPER, ok):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get("sensor.power_state")
    assert state is not None
    assert state.attributes["queue"] == "4.1"
    assert state.attributes["poweroff_periods_tomorrow"] == [{"start": 9.0, "end": 11.0}]
    assert state.attributes["data_stale"] is False
    assert hass.states.get("sensor.schedule_updated").state not in ("unknown", "unavailable")
    # старі атрибути на next_power_on лишились (на них посилається дашборд)
    assert "next_on" in hass.states.get("sensor.next_power_on").attributes

    with patch(SCRAPER, AsyncMock(side_effect=ScraperError("HTTP 502"))):
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("sensor.power_state")
    assert state.state != "unavailable"
    assert state.attributes["poweroff_periods_tomorrow"] == [{"start": 9.0, "end": 11.0}]
    assert state.attributes["data_stale"] is True
    assert "502" in state.attributes["last_error"]


async def test_view_queue_select(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={POWEROFF_GROUP_CONF: "4-1"}, title="Poltava")
    entry.add_to_hass(hass)
    home = AsyncMock(return_value=([PowerOffPeriod(8, 9.5, True)], []))
    with patch(SCRAPER, home):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("select.poweroff_view_queue")
        assert state.state == "4.1"
        assert state.attributes["home_queue"] == "4.1"
        assert state.attributes["poweroff_periods_today"] == [{"start": 8.0, "end": 9.5}]

        home.return_value = ([PowerOffPeriod(1, 3, True)], None)
        await hass.services.async_call(
            "select", "select_option", {"entity_id": "select.poweroff_view_queue", "option": "2.1"}, blocking=True
        )
        await hass.async_block_till_done()

    state = hass.states.get("select.poweroff_view_queue")
    assert state.state == "2.1"
    assert state.attributes["queue"] == "2.1"
    assert state.attributes["poweroff_periods_today"] == [{"start": 1.0, "end": 3.0}]
    assert state.attributes["loading"] is False
    # сенсор лишився по вашій черзі
    assert hass.states.get("sensor.power_state").attributes["poweroff_periods_today"] == [{"start": 8.0, "end": 9.5}]


async def test_config_flow_dropdown_and_duplicate(hass: HomeAssistant) -> None:
    from homeassistant.data_entry_flow import FlowResultType

    validate = "custom_components.poltava_poweroff.energyua_scrapper.EnergyUaScrapper.validate"
    with patch(validate, AsyncMock(return_value=True)), patch(SCRAPER, AsyncMock(return_value=([], []))):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {POWEROFF_GROUP_CONF: "4-1"})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Poltava Power Offline 4.1"
        await hass.async_block_till_done()

        again = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        again = await hass.config_entries.flow.async_configure(again["flow_id"], {POWEROFF_GROUP_CONF: "4-1"})
        assert again["type"] is FlowResultType.ABORT
        assert again["reason"] == "already_configured"
