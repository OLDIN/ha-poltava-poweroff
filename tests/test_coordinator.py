"""Тести стійкості координатора: збої сайту, кеш на диску, перехід через північ."""

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

    # Сайт ліг
    coord.api.get_power_off_periods = AsyncMock(side_effect=ScraperError("HTTP 502"))
    await coord._async_update_data()  # не кидає — є кеш

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
    """Сайт відповів, але «Немає даних» (None) — відомий графік лишається."""
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, TOMORROW))
    await coord._async_update_data()
    coord.api.get_power_off_periods = AsyncMock(return_value=(None, None))
    await coord._async_update_data()
    assert len(coord.today_periods) == 2
    assert len(coord.tomorrow_periods) == 1
    assert not coord.is_stale


async def test_explicit_empty_day_clears_it(hass: HomeAssistant) -> None:
    """[] = сайт явно показує день без відключень → приймаємо."""
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

    # «Рестарт» — новий координатор, сайт лежить
    coord2 = PoltavaPowerOffCoordinator(hass, coord.config_entry)
    await coord2.async_load_cache()
    coord2.api.get_power_off_periods = AsyncMock(side_effect=ScraperError("down"))
    await coord2._async_update_data()
    assert [(p.start, p.end) for p in coord2.today_periods] == [(8, 9.5), (14, 16)]
    assert coord2.schedule_changed_at == coord.schedule_changed_at


async def test_midnight_rollover_without_site(hass: HomeAssistant, freezer) -> None:
    """Опівночі завтрашній графік стає сьогоднішнім, навіть якщо сайт недоступний."""
    freezer.move_to(dt_util.now().replace(hour=23, minute=50))
    coord = _make(hass)
    coord.api.get_power_off_periods = AsyncMock(return_value=(TODAY, TOMORROW))
    await coord._async_update_data()

    freezer.tick(timedelta(minutes=20))  # 00:10 наступного дня
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
    # ваша черга не змінилась
    assert [(p.start, p.end) for p in coord.today_periods] == [(8, 9.5), (14, 16)]

    # повторне перемикання на свіжу чергу — без запиту
    await coord.async_set_view_group("4-1")
    await coord.async_set_view_group("2-1")
    assert other.await_count == 1

    # фонове оновлення: ваша + обрана, інші — ні
    third = AsyncMock(return_value=([], []))
    coord._scraper("3-1").get_power_off_periods = third
    await coord._async_update_data()
    assert other.await_count == 2
    assert third.await_count == 0

    # кеш зберігає обидві черги та вибір
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
    await coord._async_update_data()  # не кидає
    assert not coord.is_stale
    assert coord.view.is_stale
