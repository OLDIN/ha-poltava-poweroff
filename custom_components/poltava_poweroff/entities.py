"""Module for power off period entities."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util


@dataclass
class PowerOffPeriod:
    """Power off period in hours from midnight."""

    start: float
    end: float
    today: bool

    def to_datetime_period(self, tz_info) -> tuple[datetime, datetime]:
        """Convert to datetime period."""
        now = dt_util.now()

        # Визначаємо базову дату
        if self.today:
            base_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            base_date = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        start = base_date + timedelta(hours=self.start)
        end = base_date + timedelta(hours=self.end)

        # Якщо end менший за start, це означає що період йде через північ
        if end <= start:
            end = end + timedelta(days=1)

        return start, end
