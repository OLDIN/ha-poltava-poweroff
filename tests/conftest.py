"""Спільні фікстури тестів."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Дозволити HA вантажити custom_components/poltava_poweroff у тестах."""
    yield
