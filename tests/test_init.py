"""Integration test: a real HA core sets up the integration; the site goes down after the first fetch."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.poltava_poweroff.const import DOMAIN, POWEROFF_GROUP_CONF
from custom_components.poltava_poweroff.sources.energy_ua import ScraperError
from custom_components.poltava_poweroff.entities import PowerOffPeriod

SCRAPER = "custom_components.poltava_poweroff.sources.energy_ua.EnergyUaScrapper.get_power_off_periods"


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
    # the old attributes on next_power_on are still there (dashboards rely on them)
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
    # the sensor still follows the home queue
    assert hass.states.get("sensor.power_state").attributes["poweroff_periods_today"] == [{"start": 8.0, "end": 9.5}]


async def test_config_flow_source_then_queue_and_duplicate(hass: HomeAssistant) -> None:
    from homeassistant.data_entry_flow import FlowResultType

    validate = "custom_components.poltava_poweroff.sources.energy_ua.EnergyUaScrapper.validate"
    with patch(validate, AsyncMock(return_value=True)), patch(SCRAPER, AsyncMock(return_value=([], []))):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"source": "poltava"})
        assert result["step_id"] == "queue"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {POWEROFF_GROUP_CONF: "4-1"})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Poltava Power Offline 4.1"
        assert result["data"] == {"source": "poltava", POWEROFF_GROUP_CONF: "4-1"}
        assert result["result"].unique_id == "poltava:4-1"
        await hass.async_block_till_done()

        # The same queue from the same source again: refused
        again = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        again = await hass.config_entries.flow.async_configure(again["flow_id"], {"source": "poltava"})
        again = await hass.config_entries.flow.async_configure(again["flow_id"], {POWEROFF_GROUP_CONF: "4-1"})
        assert again["type"] is FlowResultType.ABORT
        assert again["reason"] == "already_configured"

        # The same queue number from another source is another entry
        other = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        other = await hass.config_entries.flow.async_configure(other["flow_id"], {"source": "poltava_energy_ua"})
        other = await hass.config_entries.flow.async_configure(other["flow_id"], {POWEROFF_GROUP_CONF: "4-1"})
        assert other["type"] is FlowResultType.CREATE_ENTRY
        assert other["title"] == "Poltava (energy-ua.info) 4.1"


async def test_config_flow_reports_unreachable_source(hass: HomeAssistant) -> None:
    validate = "custom_components.poltava_poweroff.sources.energy_ua.EnergyUaScrapper.validate"
    with patch(validate, AsyncMock(return_value=False)):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"source": "poltava"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {POWEROFF_GROUP_CONF: "4-1"})
    assert result["step_id"] == "queue"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_version_1_entry_is_migrated_to_the_default_source(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={POWEROFF_GROUP_CONF: "4-1"}, unique_id="4-1", version=1)
    entry.add_to_hass(hass)
    with patch(SCRAPER, AsyncMock(return_value=([PowerOffPeriod(8, 9.5, True)], None))):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.version == 2
    assert entry.data == {POWEROFF_GROUP_CONF: "4-1", "source": "poltava"}
    assert entry.unique_id == "poltava:4-1"
    assert hass.states.get("sensor.power_state").attributes["queue"] == "4.1"


async def test_reconfigure_changes_the_source_and_keeps_the_entities(hass: HomeAssistant) -> None:
    from homeassistant.data_entry_flow import FlowResultType
    from homeassistant.helpers import entity_registry as er

    entry = MockConfigEntry(
        domain=DOMAIN, data={"source": "poltava", POWEROFF_GROUP_CONF: "4-1"}, unique_id="poltava:4-1", version=2
    )
    entry.add_to_hass(hass)
    validate = "custom_components.poltava_poweroff.sources.energy_ua.EnergyUaScrapper.validate"
    with patch(SCRAPER, AsyncMock(return_value=([PowerOffPeriod(8, 9.5, True)], None))), patch(
        validate, AsyncMock(return_value=True)
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entities_before = {e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}

        result = await entry.start_reconfigure_flow(hass)
        assert result["step_id"] == "reconfigure"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"source": "poltava_energy_ua"})
        assert result["step_id"] == "reconfigure_queue"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {POWEROFF_GROUP_CONF: "2-1"})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert entry.data == {"source": "poltava_energy_ua", POWEROFF_GROUP_CONF: "2-1"}
    assert entry.unique_id == "poltava_energy_ua:2-1"
    assert entry.title == "Poltava (energy-ua.info) 2.1"
    # The same entities (entity ids, history, automations), now following queue 2.1: no "_2" duplicates
    entities_after = {e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
    assert entities_after == entities_before
    assert er.async_get(hass).async_get("sensor.power_state").unique_id.endswith("-2-1-electricity")
    state = hass.states.get("sensor.power_state")
    assert state.attributes.get("queue") == "2.1", (state, entry.state)


async def test_schedule_changed_event_entity(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={POWEROFF_GROUP_CONF: "4-1"}, title="Poltava")
    entry.add_to_hass(hass)
    with patch(SCRAPER, AsyncMock(return_value=([PowerOffPeriod(8, 9.5, True)], None))):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("event.poweroff_schedule_changed")
    assert state is not None
    assert state.state == "unknown"  # nothing fired on the first fetch
    assert state.attributes["event_types"] == ["published", "changed"]

    with patch(SCRAPER, AsyncMock(return_value=([PowerOffPeriod(8, 9.5, True)], [PowerOffPeriod(15, 17.5, False)]))):
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("event.poweroff_schedule_changed")
    assert state.state not in ("unknown", "unavailable")
    assert state.attributes["event_type"] == "published"
    assert state.attributes["day"] == "tomorrow"
    assert state.attributes["periods_text"] == "15:00–17:30"
    assert state.attributes["queue"] == "4.1"


async def test_official_schedule_used_when_energyua_has_no_data(hass: HomeAssistant) -> None:
    """2026-10-31: energy-ua.info showed "Немає даних" for a day with outages; poe.pl.ua had them."""
    poe = "custom_components.poltava_poweroff.sources.poe.PoeScrapper.get_power_off_periods"
    entry = MockConfigEntry(domain=DOMAIN, data={POWEROFF_GROUP_CONF: "1-1"}, title="Poltava")
    entry.add_to_hass(hass)
    official = ([PowerOffPeriod(6, 7.5, True), PowerOffPeriod(18, 20.5, True)], None)
    with patch(poe, AsyncMock(return_value=official)), patch(SCRAPER, AsyncMock(return_value=(None, None))):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.power_state")
    assert state.attributes["poweroff_periods_today"] == [{"start": 6.0, "end": 7.5}, {"start": 18.0, "end": 20.5}]
    assert state.attributes["data_stale"] is False

    # Later poe.pl.ua is down and energy-ua.info still has no data: the known schedule stays
    with patch(poe, AsyncMock(side_effect=_poe_error())), patch(SCRAPER, AsyncMock(return_value=(None, None))):
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
    state = hass.states.get("sensor.power_state")
    assert state.attributes["poweroff_periods_today"] == [{"start": 6.0, "end": 7.5}, {"start": 18.0, "end": 20.5}]


def _poe_error():
    from custom_components.poltava_poweroff.sources.energy_ua import ScraperError as PackageScraperError

    return PackageScraperError("HTTP 522")
