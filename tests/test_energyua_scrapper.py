from pathlib import Path
from unittest.mock import patch

import pytest

from poltava_poweroff.energyua_scrapper import EnergyUaScrapper
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
                # Періоди з scale_info_periods: 06:30-09:00, 12:30-15:00, 18:30-20:00
                PowerOffPeriod(6.5, 9.0, today=True),
                PowerOffPeriod(12.5, 15.0, today=True),
                PowerOffPeriod(18.5, 20.0, today=True),
            ],
            [],
        ),
        (
            "1.1",
            "energyua_11_page.html",
            [
                PowerOffPeriod(6.0, 8.5, today=True),
                PowerOffPeriod(12.0, 14.5, today=True),
                PowerOffPeriod(18.0, 20.0, today=True),
            ],
            [],
        ),
        (
            "1.2",
            "energyua_12_nodata_page.html",
            [],
            [],
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
    # Мокаємо cloudscraper, оскільки він використовує requests, а не aiohttp
    html_content = load_energyua_page(test_page)

    # Створюємо mock response об'єкт
    mock_response = type(
        "MockResponse",
        (),
        {
            "text": html_content,
            "status_code": 200,
            "content": html_content.encode("utf-8"),
        },
    )()

    # Мокаємо cloudscraper.create_scraper та метод get
    def mock_get(*args, **kwargs):
        return mock_response

    with patch("poltava_poweroff.energyua_scrapper.cloudscraper.create_scraper") as mock_create_scraper:
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
    assert today_periods is not None
    assert tomorrow_periods is not None
    assert len(today_periods) == len(expected_today)
    assert len(tomorrow_periods) == len(expected_tomorrow)
    assert today_periods == expected_today
    assert tomorrow_periods == expected_tomorrow
