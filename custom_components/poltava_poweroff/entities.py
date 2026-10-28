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

        # Base date: today or tomorrow
        if self.today:
            base_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            base_date = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        start = base_date + timedelta(hours=self.start)
        end = base_date + timedelta(hours=self.end)

        # end < start means the period crosses midnight.
        # end == 0.0 means midnight at the end of the day (24:00),
        # so a day is added only when end < start (not <=, to avoid issues with end == start == 0).
        if end < start:
            end = end + timedelta(days=1)
        elif end == start and self.end == 0.0:
            # end == start == 0.0 would be 00:00–00:00, which makes no sense,
            # so treat it as a period ending at midnight (24:00).
            end = end + timedelta(days=1)

        return start, end
