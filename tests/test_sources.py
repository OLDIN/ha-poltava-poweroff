"""poe.pl.ua parser, the fallback chain and the source registry."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from poltava_poweroff.sources.energy_ua import ScraperError
from poltava_poweroff.entities import PowerOffPeriod
from poltava_poweroff.sources.poe import PoeScrapper
from poltava_poweroff.sources import DEFAULT_SOURCE, SOURCES, get_source
from poltava_poweroff.sources.base import FallbackProvider
from poltava_poweroff.sources.energy_ua import EnergyUaScrapper

POE_PAGE = (Path(__file__).parent / "poe_gpv_2026-10-31.html").read_text(encoding="utf-8")


def _spans(periods: list[PowerOffPeriod] | None) -> list[tuple[float, float]] | None:
    return None if periods is None else [(p.start, p.end) for p in periods]


@pytest.mark.parametrize(
    ("group", "expected"),
    [
        ("1-1", [(6.0, 7.5), (12.0, 14.5), (18.0, 20.5)]),
        ("4-1", [(9.0, 11.0), (15.0, 17.5), (21.0, 22.5)]),
        ("5-2", [(10.5, 12.5), (16.5, 19.0), (22.5, 0.0)]),  # 24:00 is stored as 0.0
        ("6-1", [(6.0, 6.5), (11.0, 13.5), (17.0, 19.5), (23.0, 0.0)]),
    ],
)
def test_parses_the_periods_list(group: str, expected: list) -> None:
    assert _spans(PoeScrapper(group).parse(POE_PAGE, today=True)) == expected


@pytest.mark.parametrize("group", ["1-1", "2-2", "5-2", "6-1"])
def test_table_gives_the_same_periods_as_the_list(group: str) -> None:
    """Without the list the half-hour table is used; gpv-s3 (switching) counts as power on."""
    without_list = POE_PAGE.replace('class="gpv-periods"', 'class="x"')
    scrapper = PoeScrapper(group)
    assert _spans(scrapper.parse(without_list, today=True)) == _spans(scrapper.parse(POE_PAGE, today=True))


@pytest.mark.parametrize("cells", [0, 47, 49])
def test_table_row_with_wrong_number_of_cells_is_unknown(cells: int) -> None:
    """A truncated row must not read as "no outages" and wipe the cache."""
    row = '<tr><td class="gpv-q">1.1</td>' + '<td class="gpv-c gpv-s1"></td>' * cells + "</tr>"
    html = f'<table class="gpv-table"><tbody>{row}</tbody></table>'
    assert PoeScrapper("1-1").parse(html, today=True) is None


@pytest.mark.parametrize(
    "html",
    [
        "",  # the schedule for this date is not published yet
        "  \n ",
        "<div class='gpvinfodetail'>Графіки погодинних відключень не застосовуються</div>",  # unknown layout
        "<html><title>Just a moment...</title></html>",  # firewall page
    ],
)
def test_unknown_answer_is_none_not_no_outages(html: str) -> None:
    assert PoeScrapper("1-1").parse(html, today=False) is None


@pytest.mark.real_poe
async def test_fetches_today_and_tomorrow_with_the_site_request_format() -> None:
    calls: list[dict] = []

    def post(url, data, headers, timeout):
        calls.append(data)
        return SimpleNamespace(status_code=200, text=POE_PAGE if len(calls) == 1 else "")

    scrapper = PoeScrapper("1-1")
    scrapper.scraper = SimpleNamespace(post=post)
    today, tomorrow = await scrapper.get_power_off_periods()
    assert _spans(today) == [(6.0, 7.5), (12.0, 14.5), (18.0, 20.5)]
    assert tomorrow is None
    assert calls[0]["seldate"].startswith('{"date_in": "') and len(calls) == 2


@pytest.mark.real_poe
@pytest.mark.parametrize(
    ("post", "message"),
    [
        (lambda *a, **k: SimpleNamespace(status_code=522, text=""), "Сайт Полтаваобленерго відповів помилкою HTTP 522"),
        (lambda *a, **k: (_ for _ in ()).throw(ConnectionError("reset")), "Не вдалося з'єднатися з poe.pl.ua"),
    ],
)
async def test_site_errors_raise(post, message: str) -> None:
    scrapper = PoeScrapper("1-1")
    scrapper.scraper = SimpleNamespace(post=post)
    with pytest.raises(ScraperError, match=message):
        await scrapper.get_power_off_periods()


# ---------------------------------------------------------- FallbackProvider

TODAY = [PowerOffPeriod(6, 7.5, True)]
TOMORROW = [PowerOffPeriod(9, 11, False)]
UA_TODAY = [PowerOffPeriod(1, 2, True)]
UA_TOMORROW = [PowerOffPeriod(3, 4, False)]


def _source(poe, energyua) -> FallbackProvider:
    source = FallbackProvider([PoeScrapper("1-1"), EnergyUaScrapper("1-1")])
    source.poe, source.energyua = source.providers  # type: ignore[attr-defined]
    source.poe.get_power_off_periods = AsyncMock(**poe)
    source.energyua.get_power_off_periods = AsyncMock(**energyua)
    return source


async def test_official_schedule_wins_and_energyua_is_not_asked() -> None:
    source = _source({"return_value": (TODAY, None)}, {"return_value": (UA_TODAY, UA_TOMORROW)})
    assert await source.get_power_off_periods() == (TODAY, None)
    source.energyua.get_power_off_periods.assert_not_called()
    assert source.last_source == "poe.pl.ua"


async def test_energyua_is_used_when_poe_is_down() -> None:
    source = _source({"side_effect": ScraperError("HTTP 522")}, {"return_value": (UA_TODAY, UA_TOMORROW)})
    assert await source.get_power_off_periods() == (UA_TODAY, UA_TOMORROW)
    assert source.last_source == "energy-ua.info"


async def test_energyua_fills_today_when_poe_has_no_schedule_yet() -> None:
    source = _source({"return_value": (None, TOMORROW)}, {"return_value": (UA_TODAY, None)})
    assert await source.get_power_off_periods() == (UA_TODAY, TOMORROW)


async def test_poe_without_today_and_energyua_down_is_unknown_not_an_error() -> None:
    source = _source({"return_value": (None, None)}, {"side_effect": ScraperError("HTTP 522")})
    assert await source.get_power_off_periods() == (None, None)


async def test_both_down_raises_one_readable_error() -> None:
    source = _source({"side_effect": ScraperError("poe down")}, {"side_effect": ScraperError("ua down")})
    with pytest.raises(ScraperError, match="ні з poe.pl.ua, ні з energy-ua.info"):
        await source.get_power_off_periods()


async def test_validate_accepts_either_source() -> None:
    poe, energyua = PoeScrapper("1-1"), EnergyUaScrapper("1-1")
    source = FallbackProvider([poe, energyua])
    with patch.object(poe, "validate", AsyncMock(return_value=False)), patch.object(
        energyua, "validate", AsyncMock(return_value=True)
    ):
        assert await source.validate()


# ---------------------------------------------------------------- registry


def test_registry_has_the_poltava_sources_with_12_queues() -> None:
    assert DEFAULT_SOURCE == "poltava"
    assert set(SOURCES) == {"poltava", "poltava_poe", "poltava_energy_ua"}
    for source in SOURCES.values():
        assert source.queues[0] == "1-1" and source.queues[-1] == "6-2" and len(source.queues) == 12


def test_default_source_asks_poe_first_then_energyua() -> None:
    provider = SOURCES["poltava"].create("4-1")
    assert isinstance(provider, FallbackProvider)
    assert [p.site for p in provider.providers] == ["poe.pl.ua", "energy-ua.info"]
    assert isinstance(SOURCES["poltava_poe"].create("4-1"), PoeScrapper)
    assert isinstance(SOURCES["poltava_energy_ua"].create("4-1"), EnergyUaScrapper)


def test_unknown_source_falls_back_to_default() -> None:
    assert get_source(None).id == "poltava"
    assert get_source("removed_city").id == "poltava"


def test_every_source_has_a_name_in_every_translation() -> None:
    import json

    base = Path(__file__).parent.parent / "custom_components" / "poltava_poweroff"
    for file in ["strings.json", "translations/en.json", "translations/uk.json"]:
        options = json.loads((base / file).read_text(encoding="utf-8"))["selector"]["source"]["options"]
        assert set(options) == set(SOURCES), file
