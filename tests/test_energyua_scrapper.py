from pathlib import Path
from unittest.mock import patch

import pytest
from poltava_poweroff.sources.energy_ua import EnergyUaScrapper
from poltava_poweroff.entities import PowerOffPeriod


def load_energyua_page(test_page: str) -> str:
    test_file = Path(__file__).parent / test_page

    with open(test_file, encoding="utf-8") as file:
        return file.read()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "group,test_page,expected_today,expected_tomorrow",
    [
        (
            "1.2",
            "energyua_12_page.html",
            [
                # Periods from scale_info_periods: 06:30-09:00, 12:30-15:00, 18:30-20:00
                PowerOffPeriod(6.5, 9.0, today=True),
                PowerOffPeriod(12.5, 15.0, today=True),
                PowerOffPeriod(18.5, 20.0, today=True),
            ],
            None,  # the "tomorrow" header exists, but there is no schedule yet
        ),
        (
            "1.1",
            "energyua_11_page.html",
            [
                PowerOffPeriod(6.0, 8.5, today=True),
                PowerOffPeriod(12.0, 14.5, today=True),
                PowerOffPeriod(18.0, 20.0, today=True),
            ],
            None,
        ),
        (
            "1.2",
            "energyua_12_nodata_page.html",
            None,  # "Немає даних" (no data) is not the same as "no outages"
            None,
        ),
        (
            "1.1",
            "energyua_11_nodata_empty_scale.html",
            None,  # an empty hourly scale under "Немає даних" (after the site's downtime): unknown, not "no outages"
            None,
        ),
        (
            "1.1",
            "energyua_2_days.html",
            [
                PowerOffPeriod(4, 7.5, today=True),
                PowerOffPeriod(10, 14.5, today=True),
                PowerOffPeriod(16, 20.0, today=True),
                PowerOffPeriod(22, 0.0, today=True),
            ],
            [
                PowerOffPeriod(0.0, 1.5, today=False),
                PowerOffPeriod(5.0, 9.5, today=False),
                PowerOffPeriod(11.0, 15.5, today=False),
                PowerOffPeriod(17.0, 21.5, today=False),
                PowerOffPeriod(23.0, 0.0, today=False),
            ],
        ),
    ],
)
async def test_energyua_scrapper(group, test_page, expected_today, expected_tomorrow) -> None:
    # Given a response from the EnergyUa website
    # Mock cloudscraper: it uses requests, not aiohttp
    html_content = load_energyua_page(test_page)

    # Mock response object
    mock_response = type(
        "MockResponse",
        (),
        {
            "text": html_content,
            "status_code": 200,
            "content": html_content.encode("utf-8"),
        },
    )()

    # Mock cloudscraper.create_scraper and its get method
    def mock_get(*args, **kwargs):
        return mock_response

    with patch("poltava_poweroff.sources.energy_ua.cloudscraper.create_scraper") as mock_create_scraper:
        mock_scraper = type(
            "MockScraper",
            (),
            {
                "get": mock_get,
            },
        )()
        mock_create_scraper.return_value = mock_scraper

        # When scrapper is called for power-off periods
        scrapper = EnergyUaScrapper(group)
        today_periods, tomorrow_periods = await scrapper.get_power_off_periods()

    # Then the power-off periods are extracted correctly
    assert today_periods == expected_today
    assert tomorrow_periods == expected_tomorrow


def _mock_scraper(get):
    return patch(
        "poltava_poweroff.sources.energy_ua.cloudscraper.create_scraper",
        return_value=type("MockScraper", (), {"get": staticmethod(get)})(),
    )


def _resp(text: str, status: int = 200):
    return type("MockResponse", (), {"text": text, "status_code": status})()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        _resp("<html>Bad gateway</html>", 502),
        _resp("", 200),
        _resp("<html><title>Just a moment...</title>Checking your browser</html>", 200),
        _resp("<html>Технічні роботи</html>", 503),
    ],
)
async def test_scrapper_raises_on_bad_page(response) -> None:
    """Site down / Cloudflare / maintenance -> an exception, not an empty schedule."""
    from poltava_poweroff.sources.energy_ua import ScraperError

    with _mock_scraper(lambda *a, **k: response), pytest.raises(ScraperError) as exc:
        await EnergyUaScrapper("1-1").get_power_off_periods()
    # Human-readable message (shown on the card): Ukrainian UI text, without the site URL
    assert "http://" not in str(exc.value)
    assert "https://" not in str(exc.value)
    assert str(exc.value).startswith(("Сайт відповів помилкою HTTP", "Сайт повернув сторінку без графіка"))


@pytest.mark.asyncio
async def test_scrapper_raises_on_network_error() -> None:
    from poltava_poweroff.sources.energy_ua import ScraperError

    def boom(*a, **k):
        raise ConnectionError("Connection reset by peer")

    with _mock_scraper(boom), pytest.raises(ScraperError, match="Не вдалося з'єднатися з energy-ua.info"):
        await EnergyUaScrapper("1-1").get_power_off_periods()


def test_published_day_without_outages_is_empty_list() -> None:
    """A day scale without active hours -> [] (no outages), not None."""
    html = (
        load_energyua_page("energyua_12_page.html")
        .replace("hour_active", "hour_x")
        .replace('class="scale_info_periods"', 'class="x"')
    )
    today, tomorrow = EnergyUaScrapper("1-2").parse_page(html)
    assert today == []
    assert tomorrow is None


@pytest.mark.parametrize(
    ("periods", "expected"),
    [
        ([PowerOffPeriod(22, 23, True), PowerOffPeriod(23, 0.0, True)], [PowerOffPeriod(22, 0.0, True)]),
        ([PowerOffPeriod(20, 22, True), PowerOffPeriod(22, 0.0, True)], [PowerOffPeriod(20, 0.0, True)]),
        (
            [PowerOffPeriod(0, 1, True), PowerOffPeriod(23, 0.0, True)],
            [PowerOffPeriod(0, 1, True), PowerOffPeriod(23, 0.0, True)],
        ),
        (
            [PowerOffPeriod(8, 9, True), PowerOffPeriod(9, 10, True), PowerOffPeriod(12, 13, True)],
            [PowerOffPeriod(8, 10, True), PowerOffPeriod(12, 13, True)],
        ),
    ],
)
def test_merge_periods_keeps_hour_before_midnight(periods, expected) -> None:
    """Hourly scale: 22–23 + 23–00 must become 22–00, not be cut to 22–23."""
    assert EnergyUaScrapper.merge_periods(periods) == expected
