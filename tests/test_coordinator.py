"""Coordinator resilience tests: site failures, on-disk cache, midnight rollover."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util
from poltava_poweroff.const import DOMAIN, POWEROFF_GROUP_CONF, STORAGE_KEY
from poltava_poweroff.coordinator import PoltavaPowerOffCoordinator
from poltava_poweroff.energyua_scrapper import ScraperError
from poltava_poweroff.entities import PowerOffPeriod
from pytest_homeassistant_custom_component.common import MockConfigEntry

TODAY = [PowerOffPeriod(8, 9.5, True), PowerOffPeriod(14, 16, True)]
TOMORROW = [PowerOffPeriod(9, 11, False)]


def _make(hass: HomeAssistant, entry_id: str = "e1") -> PoltavaPowerOffCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, data={POWEROFF_GROUP_CONF: "4-1"}, entry_id=entry_id)
    entry.add_to_hass(hass)
    return PoltavaPowerOffCoordinator(hass, entry)


async def test_failure_keeps_previous_schedule(hass: HomeAssistant) -> None:
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, TOMORROW))
    await coord._async_update_data()
    changed_at = coord.schedule_changed_at
    assert [(p.start, p.end) for p in coord.today_periods] == [(8, 9.5), (14, 16)]

    # The site goes down
    coord.api.get_power_off_periods = AsyncMock(side_effect=ScraperError("HTTP 502"))
    await coord._async_update_data()  # doesn't raise: there is a cache

    assert [(p.start, p.end) for p in coord.today_periods] == [(8, 9.5), (14, 16)]
    assert [(p.start, p.end) for p in coord.tomorrow_periods] == [(9, 11)]
    assert coord.is_stale
    assert "502" in coord.last_error
    assert coord.schedule_changed_at == changed_at


async def test_failure_without_cache_raises(hass: HomeAssistant) -> None:
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(side_effect=ScraperError("down"))
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


async def test_no_data_day_does_not_wipe_known_day(hass: HomeAssistant) -> None:
    """The site answered "Немає даних" (None): the known schedule is kept."""
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, TOMORROW))
    await coord._async_update_data()
    coord.api.get_power_off_periods = AsyncMock(return_value=(None, None))
    await coord._async_update_data()
    assert len(coord.today_periods) == 2
    assert len(coord.tomorrow_periods) == 1
    assert not coord.is_stale


async def test_explicit_empty_day_clears_it(hass: HomeAssistant) -> None:
    """[] means the site explicitly shows a day without outages: accept it."""
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, TOMORROW))
    await coord._async_update_data()
    coord.api.get_power_off_periods = AsyncMock(return_value=([], TOMORROW))
    await coord._async_update_data()
    assert coord.today_periods == []
    assert coord.today_known


async def test_changed_at_only_moves_when_schedule_changes(hass: HomeAssistant, freezer) -> None:
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, TOMORROW))
    await coord._async_update_data()
    first = coord.schedule_changed_at

    freezer.tick(timedelta(minutes=5))
    await coord._async_update_data()
    assert coord.schedule_changed_at == first
    assert coord.last_success_at > first

    freezer.tick(timedelta(minutes=5))
    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, [PowerOffPeriod(9, 12, False)]))
    await coord._async_update_data()
    assert coord.schedule_changed_at > first


async def test_cache_survives_restart(hass: HomeAssistant, hass_storage) -> None:
    coord = _make(hass, "restart")
    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, TOMORROW))
    await coord._async_update_data()
    assert f"{STORAGE_KEY}.restart" in hass_storage

    # "Restart": a new coordinator while the site is down
    coord2 = PoltavaPowerOffCoordinator(hass, coord.config_entry)
    await coord2.async_load_cache()
    coord2.api.get_power_off_periods = AsyncMock(side_effect=ScraperError("down"))
    await coord2._async_update_data()
    assert [(p.start, p.end) for p in coord2.today_periods] == [(8, 9.5), (14, 16)]
    assert coord2.schedule_changed_at == coord.schedule_changed_at


async def test_midnight_rollover_without_site(hass: HomeAssistant, freezer) -> None:
    """At midnight tomorrow's schedule becomes today's, even if the site is unreachable."""
    freezer.move_to(dt_util.now().replace(hour=23, minute=50))
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, TOMORROW))
    await coord._async_update_data()

    freezer.tick(timedelta(minutes=20))  # 00:10 the next day
    coord.api.get_power_off_periods = AsyncMock(side_effect=ScraperError("down"))
    await coord._async_update_data()
    assert [(p.start, p.end) for p in coord.today_periods] == [(9, 11)]
    assert coord.tomorrow_periods == []
    assert not coord.tomorrow_known


async def test_view_queue_fetched_on_switch_and_in_background(hass: HomeAssistant, hass_storage) -> None:
    coord = _make(hass, "view")
    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, TOMORROW))
    await coord._async_update_data()

    other = AsyncMock(return_value=([PowerOffPeriod(1, 2, True)], None))
    coord._scraper("2-1").get_power_off_periods = other
    await coord.async_set_view_group("2-1")
    assert other.await_count == 1
    assert [(p.start, p.end) for p in coord.view.today_periods] == [(1, 2)]
    # the home queue is unchanged
    assert [(p.start, p.end) for p in coord.today_periods] == [(8, 9.5), (14, 16)]

    # switching back to a fresh queue does not fetch again
    await coord.async_set_view_group("4-1")
    await coord.async_set_view_group("2-1")
    assert other.await_count == 1

    # background update: home + selected queue only
    third = AsyncMock(return_value=([], []))
    coord._scraper("3-1").get_power_off_periods = third
    await coord._async_update_data()
    assert other.await_count == 2
    assert third.await_count == 0

    # the cache keeps both queues and the selection
    saved = hass_storage[f"{STORAGE_KEY}.view"]["data"]
    assert set(saved["groups"]) == {"4-1", "2-1"}
    assert saved["view_group"] == "2-1"


async def test_view_queue_failure_does_not_break_home(hass: HomeAssistant) -> None:
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, TOMORROW))
    coord._scraper("5-2").get_power_off_periods = AsyncMock(side_effect=ScraperError("down"))
    await coord.async_set_view_group("5-2")
    assert coord.view.is_stale
    assert not coord.view.loading
    await coord._async_update_data()  # doesn't raise
    assert not coord.is_stale
    assert coord.view.is_stale


# ---------------------------------------------------------------- across midnight


async def _at(hass, freezer, when):
    await hass.config.async_set_time_zone("Europe/Kyiv")
    freezer.move_to(when)


async def test_outage_across_midnight_next_on_is_after_midnight(hass: HomeAssistant, freezer) -> None:
    """21:00–24:00 today + 00:00–02:00 tomorrow is one outage; power returns at 02:00."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    kyiv = ZoneInfo("Europe/Kyiv")
    await _at(hass, freezer, datetime(2026, 10, 28, 22, 0, tzinfo=kyiv))
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(
        return_value=([PowerOffPeriod(21, 0.0, True)], [PowerOffPeriod(0, 2, False), PowerOffPeriod(9, 11, False)])
    )
    await coord._async_update_data()
    assert coord.current_state == "Power OFF"
    assert coord.next_poweron == datetime(2026, 10, 29, 2, 0, tzinfo=kyiv)
    assert coord.next_poweroff == datetime(2026, 10, 29, 9, 0, tzinfo=kyiv)
    event = coord.get_current_or_next_event()
    assert (event.start, event.end) == (
        datetime(2026, 10, 28, 21, 0, tzinfo=kyiv),
        datetime(2026, 10, 29, 2, 0, tzinfo=kyiv),
    )


async def test_after_midnight_outage_started_yesterday(hass: HomeAssistant, freezer) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    kyiv = ZoneInfo("Europe/Kyiv")
    await _at(hass, freezer, datetime(2026, 10, 28, 23, 0, tzinfo=kyiv))
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(
        return_value=([PowerOffPeriod(21, 0.0, True)], [PowerOffPeriod(0, 2, False)])
    )
    await coord._async_update_data()
    freezer.move_to(datetime(2026, 10, 29, 0, 30, tzinfo=kyiv))  # the site is not queried anymore
    assert coord.current_state == "Power OFF"
    assert coord.next_poweron == datetime(2026, 10, 29, 2, 0, tzinfo=kyiv)


async def test_calendar_returns_event_covering_whole_window(hass: HomeAssistant, freezer) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    kyiv = ZoneInfo("Europe/Kyiv")
    await _at(hass, freezer, datetime(2026, 10, 28, 8, 0, tzinfo=kyiv))
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(return_value=([PowerOffPeriod(9, 12, True)], None))
    await coord._async_update_data()
    window = datetime(2026, 10, 28, 10, 0, tzinfo=kyiv)
    assert len(coord.get_events_between(window, window + timedelta(hours=1))) == 1
    # before it starts, the calendar shows the upcoming outage
    assert coord.get_current_or_next_event().start == datetime(2026, 10, 28, 9, 0, tzinfo=kyiv)
    assert coord.get_event_at(dt_util.now()) is None


async def test_dst_day_times_are_wall_clock(hass: HomeAssistant, freezer) -> None:
    """25.10.2026 is a DST transition day: 05:00 stays 05:00 Kyiv time."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    kyiv = ZoneInfo("Europe/Kyiv")
    await _at(hass, freezer, datetime(2026, 10, 25, 1, 0, tzinfo=kyiv))
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(return_value=([PowerOffPeriod(5, 7, True)], None))
    await coord._async_update_data()
    start = coord.next_poweroff
    assert (start.hour, start.utcoffset()) == (5, timedelta(hours=2))


def test_schedule_changes_reports_published_and_changed_days() -> None:
    from datetime import date

    from poltava_poweroff.coordinator import schedule_changes

    today = date(2026, 10, 30)
    before = {"2026-10-29": [(1.0, 2.0)], "2026-10-30": [(8.0, 9.5)]}
    after = {
        "2026-10-29": [(5.0, 6.0)],  # the past: never reported
        "2026-10-30": [(8.0, 10.0), (21.0, 0.0)],
        "2026-10-31": [],
    }
    changes = schedule_changes(before, after, today, "4.1")
    assert [(c["event_type"], c["day"]) for c in changes] == [("changed", "today"), ("published", "tomorrow")]
    today_change = changes[0]
    assert today_change["periods"] == [{"start": "08:00", "end": "10:00"}, {"start": "21:00", "end": "24:00"}]
    assert today_change["periods_text"] == "08:00–10:00, 21:00–24:00"
    assert today_change["previous_periods_text"] == "08:00–09:30"
    assert today_change["outage_hours"] == 5
    assert today_change["queue"] == "4.1"
    assert changes[1]["periods"] == [] and changes[1]["periods_text"] == ""


def test_schedule_changes_silent_on_first_fetch() -> None:
    from datetime import date

    from poltava_poweroff.coordinator import schedule_changes

    assert schedule_changes({}, {"2026-10-30": [(8.0, 9.0)]}, date(2026, 10, 30), "4.1") == []


async def test_schedule_change_is_dispatched_for_home_queue_only(hass: HomeAssistant) -> None:
    from homeassistant.helpers.dispatcher import async_dispatcher_connect
    from poltava_poweroff.const import signal_schedule_changed

    coord = _make(hass)
    received: list = []
    async_dispatcher_connect(hass, signal_schedule_changed("e1"), received.extend)

    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, TOMORROW))
    await coord._async_update_data()
    await hass.async_block_till_done()
    assert received == []  # first fetch

    await coord._async_update_data()
    await hass.async_block_till_done()
    assert received == []  # same schedule

    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, [PowerOffPeriod(9, 12, False)]))
    await coord._async_update_data()
    await hass.async_block_till_done()
    assert [(c["event_type"], c["day"], c["periods_text"]) for c in received] == [
        ("changed", "tomorrow", "09:00–12:00")
    ]

    # The view queue changes on its own: no event for it
    received.clear()
    coord._scraper("2-1").get_power_off_periods = AsyncMock(return_value=([PowerOffPeriod(1, 2, True)], []))
    await coord.async_set_view_group("2-1")
    await hass.async_block_till_done()
    coord._scraper("2-1").get_power_off_periods = AsyncMock(return_value=([PowerOffPeriod(3, 4, True)], []))
    await coord._async_update_data()
    await hass.async_block_till_done()
    assert received == []
