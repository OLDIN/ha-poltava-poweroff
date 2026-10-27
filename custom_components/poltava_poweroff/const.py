"""Constants for the Poltava Power Offline integration."""

import os
from enum import StrEnum

DOMAIN = "poltava_poweroff"

POWEROFF_GROUP_CONF = "poweroff_group"

UPDATE_INTERVAL = 300  # 5 minutes - баланс між актуальністю даних та навантаженням на сайт

# Базовий URL сайту. Можна перевизначити через змінну оточення (для dev/e2e з mock-сервером).
BASE_URL = os.environ.get("POLTAVA_POWEROFF_BASE_URL", "https://energy-ua.info").rstrip("/")

# Кеш графіка на диску (.storage/poltava_poweroff.<entry_id>)
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}"

# Скільки днів назад тримати графік у кеші
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
    """'4-1' -> '4.1' (як показує сайт і картка)."""
    return str(group).replace("-", ".")
