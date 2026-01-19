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

        # Якщо end менший або рівний start, це означає що період йде через північ
        # Але якщо end == 0.0 (опівночі), це означає кінець доби (24:00)
        # Тому додаємо день тільки якщо end < start (не <=, щоб уникнути проблем з end == start == 0)
        if end < start:
            end = end + timedelta(days=1)
        elif end == start and self.end == 0.0:
            # Якщо end == start == 0.0, це означає період з 00:00 до 00:00 (опівночі до опівночі)
            # Але це не має сенсу, тому це має бути помилка в даних
            # Або це означає період, що закінчується в опівночі (24:00)
            end = end + timedelta(days=1)

        return start, end
