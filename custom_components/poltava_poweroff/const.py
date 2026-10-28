"""Constants for the Poltava Power Offline integration."""

import os
from enum import StrEnum

DOMAIN = "poltava_poweroff"

POWEROFF_GROUP_CONF = "poweroff_group"

UPDATE_INTERVAL = 300  # 5 minutes: balance between freshness and load on the site

# Site base URL. Can be overridden via an environment variable (dev/e2e against a mock server).
BASE_URL = os.environ.get("POLTAVA_POWEROFF_BASE_URL", "https://energy-ua.info").rstrip("/")

# On-disk schedule cache (.storage/poltava_poweroff.<entry_id>)
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}"

# How many past days to keep in the cache
CACHE_KEEP_DAYS = 2

STATE_ON = "Power ON"
STATE_OFF = "Power OFF"


class PowerOffGroup(StrEnum):
    """PowerOff groups in Poltava oblast."""

    OneOne = "1-1"
    OneTwo = "1-2"
    TwoOne = "2-1"
    TwoTwo = "2-2"
    ThreeOne = "3-1"
    ThreeTwo = "3-2"
    FourOne = "4-1"
    FourTwo = "4-2"
    FiveOne = "5-1"
    FiveTwo = "5-2"
    SixOne = "6-1"
    SixTwo = "6-2"


def group_display(group: str) -> str:
    """'4-1' -> '4.1' (as shown by the site and the card)."""
    return str(group).replace("-", ".")
