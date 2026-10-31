"""Shared test fixtures."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

# The integration is imported under two names in the tests (pytest.ini pythonpath and the package)
_POE_MODULES = ("poltava_poweroff.sources.poe", "custom_components.poltava_poweroff.sources.poe")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let HA load custom_components/poltava_poweroff in tests."""
    yield


@pytest.fixture(autouse=True)
def poe_offline(request):
    """No network in tests: poe.pl.ua "fails", so the existing tests exercise the energy-ua fallback.

    Tests of poe.pl.ua itself use @pytest.mark.real_poe and mock the HTTP layer instead.
    """
    if request.node.get_closest_marker("real_poe"):
        yield
        return
    import importlib

    with ExitStack() as stack:
        for module in _POE_MODULES:
            try:
                poe = importlib.import_module(module)
            except ImportError:
                continue
            # Each import name has its own ScraperError class: raise the one that module catches
            error = poe.ScraperError("offline")
            stack.enter_context(patch(f"{module}.PoeScrapper.get_power_off_periods", AsyncMock(side_effect=error)))
            stack.enter_context(patch(f"{module}.PoeScrapper.validate", AsyncMock(return_value=False)))
        yield
