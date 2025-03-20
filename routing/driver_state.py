import datetime
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DriverState:
    # Rolling window for 70-hour/8-day rule
    duty_hours_last_8_days: List[float] = field(default_factory=lambda: [0.0] * 8)
    # Current day's accumulated hours
    current_day_driving_hours: float = 0.0
    current_day_on_duty_hours: float = 0.0
    # Current 14-hour window
    current_on_duty_window_start: Optional[datetime.datetime] = None
    # Track accumulative driving hours (for 8-hour limit)
    accumulative_driving_hours: float = 0.0
    # Track miles since last refueling
    miles_since_refueling: float = 0.0
    # Marks if 30-min break has been taken after 8 hrs
    has_taken_30min_break: bool = False  # Changed from True to correct initial state
    current_off_duty_hours: float = 0.0  # Fixed typo from current_of_duty_hours
    # Add field to track day changes
    last_day_check: Optional[datetime.date] = None

    def add_driving_hours(self, hours: float) -> None:
        """Add driving hours to both driving and on-duty counters"""
        self.current_day_driving_hours += hours
        self.current_day_on_duty_hours += hours
        self.accumulative_driving_hours += hours
        # Add to the rolling 8-day window
        self.duty_hours_last_8_days[0] += hours

    def add_on_duty_hours(self, hours: float) -> None:
        """Add on-duty (not driving) hours"""
        self.current_day_on_duty_hours += hours
        # Add to the rolling 8-day window
        self.duty_hours_last_8_days[0] += hours

    def add_30_min_break(self) -> None:
        """Take 30 minute break and reset the 8-hour driving counter"""
        self.has_taken_30min_break = True
        self.accumulative_driving_hours = (
            0.0  # Reset the counter to start tracking next 8hr period
        )
        self.current_off_duty_hours += 0.5  # 30 minutes

    def start_new_day(self) -> None:
        """Shift the 8-day window and reset daily counters"""
        self.duty_hours_last_8_days.pop()
        self.duty_hours_last_8_days.insert(0, 0.0)
        self.current_day_driving_hours = 0.0
        self.current_day_on_duty_hours = 0.0

    def take_10_hour_break(self) -> None:
        """Reset on-duty window after 10-hour break"""
        self.current_on_duty_window_start = None
        self.current_day_driving_hours = 0.0
        self.current_day_on_duty_hours = 0.0
        self.accumulative_driving_hours = 0.0
        self.has_taken_30min_break = (
            True  # A fresh 10-hour break satisfies the 30-min break requirement
        )
        self.current_off_duty_hours = 0.0

    def check_day_change(self, current_time: datetime.datetime) -> None:
        """Check if a day has changed and update the state accordingly"""
        if self.last_day_check is None:
            self.last_day_check = current_time.date()
            return

        if current_time.date() > self.last_day_check:
            self.start_new_day()
            self.last_day_check = current_time.date()

    def add_miles(self, miles: float) -> None:
        """Add miles to the trip counter"""
        self.miles_since_refueling += miles

    def refuel(self) -> None:
        """Reset the miles since refueling"""
        self.miles_since_refueling = 0.0

    @property
    def total_duty_hours_last_8_days(self) -> float:
        """Calculate total on-duty hours in the last 8 days"""
        return sum(self.duty_hours_last_8_days)

    @property
    def available_driving_hours(self) -> float:
        """Calculate available driving hours based on all limitations"""
        # 70-hour/8-day limit
        cycle_limit = 70.0 - self.total_duty_hours_last_8_days

        # 11-hour driving limit
        driving_limit = 11.0 - self.current_day_driving_hours

        # 14-hour on-duty window limit (if window has started)
        on_duty_window_limit = float("inf")
        if self.current_on_duty_window_start is not None:
            elapsed = (
                datetime.datetime.now(datetime.timezone.utc)
                - self.current_on_duty_window_start
            ).total_seconds() / 3600
            # TODO : need to see what this returns
            on_duty_window_limit = max(0, 14.0 - elapsed)

        return min(cycle_limit, driving_limit, on_duty_window_limit)

    @property
    def needs_30min_break(self) -> bool:
        """Check if driver needs a 30-minute break"""
        return self.accumulative_driving_hours >= 8.0 and not self.has_taken_30min_break

    @property
    def needs_refueling(self) -> bool:
        """Check if vehicle needs refueling"""
        return self.miles_since_refueling >= 1000.0
