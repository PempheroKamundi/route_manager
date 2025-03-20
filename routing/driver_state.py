import datetime
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DriverState:
    """Tracks and manages the state of a commercial driver according to Hours
    of Service (HOS) regulations.

    This class handles various aspects of driver compliance with federal regulations including:
    - 70-hour/8-day rule (maximum on-duty time in an 8-day period)
    - 11-hour driving limit (maximum daily driving time)
    - 14-hour on-duty window (maximum daily on-duty period)
    - 30-minute break requirement after 8 hours of driving
    - 10-hour off-duty break requirements
    - Vehicle refueling tracking

    Attributes:
        duty_hours_last_8_days: List of daily on-duty hours for the past 8 days
        current_day_driving_hours: Hours spent driving on the current day
        current_day_on_duty_hours: Total on-duty hours for the current day
        current_on_duty_window_start: Timestamp when the current 14-hour window began
        accumulative_driving_hours: Consecutive driving hours since last 30-min break
        miles_since_refueling: Miles driven since last refueling
        has_taken_30min_break: Whether the required 30-min break has been taken after
            8 hours of driving
        current_off_duty_hours: Hours spent off-duty in the current period
        last_day_check: Date of the last day change check
    """

    duty_hours_last_8_days: List[float] = field(default_factory=lambda: [0.0] * 8)
    current_day_driving_hours: float = 0.0
    current_day_on_duty_hours: float = 0.0
    current_on_duty_window_start: Optional[datetime.datetime] = None
    accumulative_driving_hours: float = 0.0
    miles_since_refueling: float = 0.0
    has_taken_30min_break: bool = False
    current_off_duty_hours: float = 0.0
    last_day_check: Optional[datetime.date] = None

    def add_driving_hours(self, hours: float) -> None:
        """
        Add driving hours to all relevant counters.

        This method updates both driving and on-duty counters since driving time
        is also considered on-duty time.

        Args:
            hours: Number of driving hours to add
        """
        self.current_day_driving_hours += hours
        self.current_day_on_duty_hours += hours
        self.accumulative_driving_hours += hours
        self.duty_hours_last_8_days[0] += hours

    def add_on_duty_hours(self, hours: float) -> None:
        """
        Add on-duty (not driving) hours to relevant counters.

        This updates on-duty counters but not driving counters.

        Args:
            hours: Number of on-duty (not driving) hours to add
        """
        self.current_day_on_duty_hours += hours
        self.duty_hours_last_8_days[0] += hours

    def add_30_min_break(self) -> None:
        """
        Record a 30-minute break and reset the 8-hour driving counter.

        This satisfies the requirement for a 30-minute break after
        8 consecutive hours of driving.
        """
        if self.accumulative_driving_hours >= 8.0:
            self.has_taken_30min_break = True
            self.current_off_duty_hours += 0.5  # 30 minutes

        # self.accumulative_driving_hours = (
        #  0.0  # Reset the counter to start tracking next 8hr period

    # )

    def start_new_day(self) -> None:
        """
        Start a new day by shifting the 8-day window and resetting daily counters.

        This maintains the rolling 8-day window for the 70-hour rule by removing
        the oldest day and adding a new day with zero hours.
        """
        self.duty_hours_last_8_days.pop()
        self.duty_hours_last_8_days.insert(0, 0.0)
        self.current_day_driving_hours = 0.0
        self.current_day_on_duty_hours = 0.0
        self.accumulative_driving_hours = 0.0

    def take_10_hour_break(self) -> None:
        """
        Reset driver state after a 10-hour break.

        After a 10-hour break, the driver can start a fresh 14-hour on-duty window,
        and various counters are reset according to HOS regulations.
        """
        self.current_on_duty_window_start = None
        self.current_day_driving_hours = 0.0
        self.current_day_on_duty_hours = 0.0
        self.accumulative_driving_hours = 0.0
        self.has_taken_30min_break = (
            True  # A fresh 10-hour break satisfies the 30-min break requirement
        )
        self.current_off_duty_hours = 0.0

    def check_day_change(self, current_time: datetime.datetime) -> None:
        """
        Check if the date has changed and update the state accordingly.

        Args:
            current_time: Current datetime to check against the last check
        """
        if self.last_day_check is None:
            self.last_day_check = current_time.date()
            return

        if current_time.date() > self.last_day_check:
            self.start_new_day()
            self.last_day_check = current_time.date()

    def add_miles(self, miles: float) -> None:
        """
        Add miles to the trip counter since last refueling.

        Args:
            miles: Number of miles to add
        """
        self.miles_since_refueling += miles

    def refuel(self) -> None:
        """Record a refueling event by resetting the miles counter."""
        self.miles_since_refueling = 0.0

    @property
    def total_duty_hours_last_8_days(self) -> float:
        """
        Calculate total on-duty hours in the last 8 days.

        Returns:
            Sum of on-duty hours over the past 8 days
        """
        return sum(self.duty_hours_last_8_days)

    @property
    def available_driving_hours(self) -> float:
        """
        Calculate available driving hours based on all applicable limitations.

        This considers:
        - 70-hour/8-day limit
        - 11-hour driving limit
        - 14-hour on-duty window limit

        Returns:
            The minimum of all limits, representing available driving hours
        """
        # 70-hour/8-day limit
        cycle_limit: float = 70.0 - self.total_duty_hours_last_8_days

        # 11-hour driving limit
        driving_limit: float = 11.0 - self.current_day_driving_hours

        # 14-hour on-duty window limit (if window has started)
        on_duty_window_limit: float = float("inf")
        if self.current_on_duty_window_start is not None:
            # Get current time with timezone information
            now = datetime.datetime.now(datetime.timezone.utc)

            # Ensure window start time has timezone information
            start_time = self.current_on_duty_window_start
            if start_time.tzinfo is None:
                # If naive, assume it's UTC
                start_time = start_time.replace(tzinfo=datetime.timezone.utc)

            elapsed: float = (now - start_time).total_seconds() / 3600
            on_duty_window_limit = max(0, 14.0 - elapsed)

        return min(cycle_limit, driving_limit, on_duty_window_limit)

    @property
    def needs_30min_break(self) -> bool:
        """
        Check if driver needs a 30-minute break based on accumulated driving hours.

        Returns:
            True if driver has driven 8+ hours without a break, False otherwise
        """
        return self.accumulative_driving_hours >= 8.0 and not self.has_taken_30min_break

    @property
    def needs_refueling(self) -> bool:
        """
        Check if vehicle needs refueling based on miles driven.

        Returns:
            True if vehicle has gone 1000+ miles since last refueling, False otherwise
        """
        return self.miles_since_refueling >= 1000.0
