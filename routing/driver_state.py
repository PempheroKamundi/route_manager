"""
routing.driver_state
~~~~~~~~~~

Keeps track of the driver`s state, ensuring compliance of HOS
Rules
"""

import datetime
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


#####################################################################
# TODO : need to make this class more generic
# instead of it having concrete implementations like add 30 min break
# because if the requirement is now 40 min, it will create problems all
# through out the code base
####################################################################
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
    - 34-hour restart for resetting the 60/70-hour limits (8-day rule)

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
        logger.info(f"Adding {hours:.2f} driving hours")
        self.current_day_driving_hours += hours
        self.current_day_on_duty_hours += hours
        self.accumulative_driving_hours += hours
        self.duty_hours_last_8_days[0] += hours
        logger.debug(
            f"Updated driving hours: current_day={self.current_day_driving_hours:.2f}, "
            f"accumulative={self.accumulative_driving_hours:.2f}"
        )

    def add_on_duty_hours(self, hours: float) -> None:
        """
        Add on-duty (not driving) hours to relevant counters.

        This updates on-duty counters but not driving counters.

        Args:
            hours: Number of on-duty (not driving) hours to add
        """
        logger.info(f"Adding {hours:.2f} on-duty (non-driving) hours")
        self.current_day_on_duty_hours += hours
        self.duty_hours_last_8_days[0] += hours
        logger.debug(
            f"Updated on-duty hours: current_day={self.current_day_on_duty_hours:.2f}"
        )

    def add_30_min_break(self) -> None:
        """
        Record a 30-minute break and reset the 8-hour driving counter.

        This satisfies the requirement for a 30-minute break after
        8 consecutive hours of driving.
        """
        logger.info("Adding 30-minute break")
        if self.accumulative_driving_hours >= 8.0:
            logger.info("30-minute break taken after 8+ hours of driving")
            self.current_off_duty_hours += 0.5  # 30 minutes
            self.accumulative_driving_hours = 0.0
        else:
            logger.debug(
                f"Break taken with only {self.accumulative_driving_hours:.2f} hours of accumulated driving"
            )

    def add_30_min_break_by_refueling(self) -> None:
        logger.info("Adding 30-minute break due to refueling")
        self.accumulative_driving_hours = 0.0

    def start_new_day(self) -> None:
        """
        Start a new day by shifting the 8-day window for the 70-hour rule only.

        This maintains the rolling 8-day window by removing the oldest day
        and adding a new day with zero hours.
        """
        logger.info("Starting new day, shifting 8-day duty hour window")
        oldest_hours = self.duty_hours_last_8_days.pop()
        logger.debug(f"Removed oldest day with {oldest_hours:.2f} hours")
        self.duty_hours_last_8_days.insert(0, 0.0)
        logger.debug(f"Updated 8-day window: {self.duty_hours_last_8_days}")

    def take_10_hour_break(self) -> None:
        """
        Reset driver state after a 10-hour break.

        After a 10-hour break, the driver can start a fresh 14-hour on-duty window,
        and various counters are reset according to HOS regulations.
        """
        logger.info("Taking 10-hour break, resetting driver state")
        self.current_on_duty_window_start = None
        self.current_day_driving_hours = 0.0
        self.current_day_on_duty_hours = 0.0
        self.accumulative_driving_hours = 0.0
        self.current_off_duty_hours = 0.0
        logger.debug("Reset on-duty window and driving counters")

    def reset_duty_hours_after_34hr_reset(self) -> None:
        """
        Reset driver state after a 34-hour restart period.

        After a 34-hour continuous off-duty period, the driver's 60/70-hour
        8-day duty cycle is reset. This allows the driver to start fresh with
        a full 60/70-hour allowance, regardless of how many hours were worked
        in the previous 7/8 days.
        """
        logger.info("Applying 34-hour restart, resetting 8-day duty cycle")

        # Reset the 8-day duty hour counters (all days set to zero)
        self.duty_hours_last_8_days = [0.0] * 8

        # Also reset the current day counters and on-duty window
        self.current_on_duty_window_start = None
        self.current_day_driving_hours = 0.0
        self.current_day_on_duty_hours = 0.0
        self.accumulative_driving_hours = 0.0
        self.current_off_duty_hours = 0.0

        logger.debug(
            "Reset 8-day duty cycle and all driver counters after 34-hour restart"
        )

    def check_day_change(self, current_time: datetime.datetime) -> None:
        """
        Check if the date has changed and update the state accordingly.

        Args:
            current_time: Current datetime to check against the last check
        """
        logger.debug(
            f"Checking for day change. Current time: {current_time}, Last check: {self.last_day_check}"
        )

        if self.last_day_check is None:
            logger.info("First day check, initializing last_day_check")
            self.last_day_check = current_time.date()
            return

        if current_time.date() > self.last_day_check:
            logger.info(
                f"Day changed from {self.last_day_check} to {current_time.date()}"
            )
            self.start_new_day()
            self.last_day_check = current_time.date()

    def add_miles(self, miles: float) -> None:
        """
        Add miles to the trip counter since last refueling.

        Args:
            miles: Number of miles to add
        """
        logger.info(f"Adding {miles:.2f} miles")
        self.miles_since_refueling += miles
        logger.debug(f"Updated miles since refueling: {self.miles_since_refueling:.2f}")

    def refuel(self) -> None:
        """Record a refueling event by resetting the miles counter."""
        logger.info(f"Refueling after {self.miles_since_refueling:.2f} miles")
        self.miles_since_refueling = 0.0

    @property
    def total_duty_hours_last_8_days(self) -> float:
        """
        Calculate total on-duty hours in the last 8 days.

        Returns:
            Sum of on-duty hours over the past 8 days
        """
        total = sum(self.duty_hours_last_8_days)
        logger.debug(f"Total duty hours in last 8 days: {total:.2f}")
        return total

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
        logger.debug("Calculating available driving hours")

        # 70-hour/8-day limit
        cycle_limit: float = 70.0 - self.total_duty_hours_last_8_days
        logger.debug(f"70-hour/8-day limit: {cycle_limit:.2f} hours remaining")

        # 11-hour driving limit
        driving_limit: float = 11.0 - self.current_day_driving_hours
        logger.debug(f"11-hour driving limit: {driving_limit:.2f} hours remaining")

        # 14-hour on-duty window limit (if window has started)
        on_duty_window_limit: float = float("inf")
        if self.current_on_duty_window_start is not None:
            # Get the driver's timezone from the start time
            start_time = self.current_on_duty_window_start
            driver_timezone = start_time.tzinfo

            # Make sure we have a timezone-aware start time
            if driver_timezone is None:
                logger.warning(
                    "Start time had no timezone information, defaulting to UTC"
                )
                driver_timezone = datetime.timezone.utc
                start_time = start_time.replace(tzinfo=driver_timezone)

            # Get current time in driver's timezone
            now = datetime.datetime.now(driver_timezone)

            elapsed: float = (now - start_time).total_seconds() / 3600
            on_duty_window_limit = max(0, 14.0 - elapsed)
            logger.debug(
                f"14-hour on-duty window: {on_duty_window_limit:.2f} hours remaining (elapsed: {elapsed:.2f}h)"
            )

        available_hours = min(cycle_limit, driving_limit, on_duty_window_limit)
        logger.info(f"Available driving hours: {available_hours:.2f}")
        return available_hours

    @property
    def needs_30min_break(self) -> bool:
        """
        Check if driver needs a 30-minute break based on accumulated driving hours.

        Returns:
            True if driver has driven 8+ hours without a break, False otherwise
        """
        needs_break = self.accumulative_driving_hours >= 8.0
        logger.debug(
            f"Needs 30-min break: {needs_break} (accumulative driving: {self.accumulative_driving_hours:.2f}h)"
        )
        return needs_break

    @property
    def needs_refueling(self) -> bool:
        """
        Check if vehicle needs refueling based on miles driven.

        Returns:
            True if vehicle has gone 1000+ miles since last refueling, False otherwise
        """
        needs_fuel = self.miles_since_refueling >= 1000.0
        logger.debug(
            f"Needs refueling: {needs_fuel} (miles since last refuel: {self.miles_since_refueling:.2f})"
        )
        return needs_fuel

    def __repr__(self):
        repr_str = (
            f"{type(self).__name__}(duty_hours_8days={self.duty_hours_last_8_days}, "
            f"driving_hours={self.current_day_driving_hours:.2f}, "
            f"on_duty_hours={self.current_day_on_duty_hours:.2f}, "
            f"window_start={self.current_on_duty_window_start}, "
            f"accum_driving={self.accumulative_driving_hours:.2f}, "
            f"miles_since_fuel={self.miles_since_refueling:.2f},"
            f"off_duty_hours={self.current_off_duty_hours:.2f}, "
            f"last_day_check={self.last_day_check})"
        )
        logger.debug(f"DriverState representation: {repr_str}")
        return repr_str
