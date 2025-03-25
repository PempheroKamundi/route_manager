"""
routing.segment_planner.usa_inter_segment_planner
~~~~~~~~~~~~~

Specialized implementation of trip segment planning for interstate transportation in the
United States. This module handles the detailed planning of individual journey segments,
including driving periods, mandatory rest cycles, 30-minute breaks, and refueling stops,
all while ensuring strict compliance with Federal Motor Carrier Safety Administration (FMCSA)
Hours of Service (HOS) regulations for interstate commerce.
"""

import datetime
import logging
from typing import List, Tuple, Type

from hos_rules.rules import HOSInterstateRule

from ..driver_state import DriverState
from .base_segment_planner import (
    BaseAbstractTripSegmentPlanner,
    DutyStatus,
    RouteSegment,
    SegmentType,
)

logger = logging.getLogger(__name__)

# Constants for time durations
REFUELING_HOURS = 1.0
MINIMUM_SEGMENT_HOURS = 0.1  # 6 minutes


class USAInterTripSegmentPlanner(BaseAbstractTripSegmentPlanner):
    """
    Standard United States of America implementation of the BaseAbstractTripSegmentPlanner.

    This class provides concrete implementations of all abstract methods
    defined in the TripSegmentPlanner base class.
    """

    def initialize_duty_window(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        remaining_hours: float,
    ) -> datetime.datetime:
        """
        Initialize on-duty window if needed and check for day changes.
        """
        # If no on-duty window has started yet, start one now
        if driver_state.current_on_duty_window_start is None and remaining_hours > 0:
            driver_state.current_on_duty_window_start = current_time
            logger.info("Starting new on-duty window at time=%s", current_time)

        # Check for day changes
        driver_state.check_day_change(current_time)
        logger.debug("After day change check: %s", driver_state)

        return current_time

    def handle_refueling(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        segments: List[RouteSegment],
    ) -> Tuple[bool, datetime.datetime]:
        """
        Handle vehicle refueling if needed.
        """
        if not driver_state.needs_refueling:
            return False, current_time

        logger.info("Vehicle needs refueling at time=%s", current_time)

        # Add refuel time
        refuel_end_time = current_time + datetime.timedelta(hours=REFUELING_HOURS)

        # Check if driver also needs a 30-minute break
        needs_break = driver_state.needs_30min_break

        if needs_break:
            logger.info(
                "Driver also needs 30-min break, satisfying it during refueling"
            )
            segments.append(
                RouteSegment(
                    type=SegmentType.REFUELING_WITH_BREAK,
                    start_time=current_time,
                    end_time=refuel_end_time,
                    duration_hours=REFUELING_HOURS,
                    distance_miles=0,
                    location="Refueling for 1 hour, 30 min break included",
                    status=DutyStatus.ON_DUTY_NOT_DRIVING,
                )
            )

            # Mark break as taken
            driver_state.add_30_min_break_by_refueling()
        else:
            # Regular refueling segment
            segments.append(
                RouteSegment(
                    type=SegmentType.REFUELING,
                    start_time=current_time,
                    end_time=refuel_end_time,
                    duration_hours=REFUELING_HOURS,
                    distance_miles=0,
                    location="Refueling",
                    status=DutyStatus.ON_DUTY_NOT_DRIVING,
                )
            )

        # Update driver state
        current_time = refuel_end_time
        driver_state.add_on_duty_hours(
            REFUELING_HOURS
        )  # Still counts as on-duty for HOS
        driver_state.refuel()
        logger.debug("After refueling: %s", driver_state)

        return True, current_time

    def check_hos_rest_needed(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        hos_rule: Type[HOSInterstateRule],
    ) -> Tuple[bool, str]:
        """
        Check if driver needs a mandatory rest period based on HOS rules.
        """
        # Check 14-hour on-duty window limit
        if driver_state.current_on_duty_window_start is not None:
            on_duty_window_hours = (
                current_time - driver_state.current_on_duty_window_start
            ).total_seconds() / 3600
            logger.debug("Current on-duty window: %.2f hours", on_duty_window_hours)

            if on_duty_window_hours >= hos_rule.MAX_DUTY_HOURS.value:
                return (
                    True,
                    f"14-hour on-duty window reached ({on_duty_window_hours:.2f} hours)",
                )

        # Check 11-hour driving limit (logged but doesn't force rest)
        if driver_state.current_day_driving_hours >= hos_rule.MAX_DRIVING_HOURS.value:
            logger.info(
                "11-hour driving limit reached (%.2f hours). Cannot drive but can work.",
                driver_state.current_day_driving_hours,
            )

        # Check 70-hour/8-day limit
        if driver_state.total_duty_hours_last_8_days >= hos_rule.MAX_CYCLE_HOURS.value:
            return (
                True,
                f"70-hour/8-day limit reached ({driver_state.total_duty_hours_last_8_days:.2f} hours)",
            )

        return False, ""

    def add_rest_period(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        segments: List[RouteSegment],
        hos_rule: Type[HOSInterstateRule],
    ) -> datetime.datetime:
        """
        Add a mandatory rest period and update driver state.
        """
        logger.info("Adding mandatory rest period at time=%s", current_time)

        # Add a 10-hour rest period
        rest_end_time = current_time + datetime.timedelta(
            hours=hos_rule.DAILY_REST_PERIOD_HOURS.value
        )

        segments.append(
            RouteSegment(
                type=SegmentType.MANDATORY_REST_PERIOD,
                start_time=current_time,
                end_time=rest_end_time,
                duration_hours=hos_rule.DAILY_REST_PERIOD_HOURS.value,
                distance_miles=0,
                location="10 hr rest period",
                status=DutyStatus.SLEEPER_BETH,
            )
        )

        current_time = rest_end_time
        # Reset driver state after 10-hour break
        driver_state.take_10_hour_break()
        logger.debug("After 10-hour break: %s", driver_state)

        return current_time

    def add_30min_break(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        segments: List[RouteSegment],
        hos_rule: Type[HOSInterstateRule],
    ) -> datetime.datetime:
        """
        Add a 30-minute break and update driver state.
        """
        logger.info("Driver needs 30-minute break at time=%s", current_time)

        break_end_time = current_time + datetime.timedelta(
            hours=hos_rule.SHORT_BREAK_PERIOD_MINUTES.value
        )  # 30 minutes

        segments.append(
            RouteSegment(
                type=SegmentType.MANDATORY_DRIVING_BREAK,
                start_time=current_time,
                end_time=break_end_time,
                duration_hours=hos_rule.SHORT_BREAK_PERIOD_MINUTES.value,
                distance_miles=0,
                location="30 min break",
                status=DutyStatus.OFF_DUTY,
            )
        )

        current_time = break_end_time
        driver_state.add_30_min_break()
        logger.debug("After 30-minute break: %s", driver_state)

        return current_time

    def create_driving_segment(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        remaining_trip_hours: float,
        remaining_trip_miles: float,
        segments: List[RouteSegment],
        segment_type: SegmentType,
    ) -> Tuple[bool, datetime.datetime, float, float]:
        """
        Create a driving segment if hours are available.
        """
        # Calculate how many hours can be driven in this stretch
        available_driving_hours = driver_state.available_driving_hours
        # TODO : this should be moved into the HOS rules and not hard coded
        hours_until_break_needed = 8.0 - driver_state.accumulative_driving_hours
        if hours_until_break_needed < available_driving_hours:
            available_driving_hours = max(0, hours_until_break_needed)

        max_driving_hours = min(available_driving_hours, remaining_trip_hours)

        logger.debug(
            "Available driving hours: %.2f, Drivable hours this stretch: %.2f",
            available_driving_hours,
            max_driving_hours,
        )

        if max_driving_hours <= 0:
            # Not enough driving hours available
            return False, current_time, remaining_trip_hours, remaining_trip_miles

        segment_distance = (
            max_driving_hours / remaining_trip_hours
        ) * remaining_trip_miles

        # Create a driving segment
        logger.info(
            "Creating driving segment for %.2f hours, %.2f miles",
            max_driving_hours,
            segment_distance,
        )

        segment_end_time = current_time + datetime.timedelta(hours=max_driving_hours)

        segments.append(
            RouteSegment(
                type=segment_type,
                start_time=current_time,
                end_time=segment_end_time,
                duration_hours=max_driving_hours,
                distance_miles=segment_distance,
                location="On Route to destination",
                status=DutyStatus.ON_DUTY_DRIVING,
            )
        )

        # Update time, driver state, and remaining trip values
        current_time = segment_end_time
        driver_state.add_driving_hours(max_driving_hours)
        driver_state.add_miles(segment_distance)
        remaining_trip_hours -= max_driving_hours
        remaining_trip_miles -= segment_distance

        logger.debug(
            "After driving segment: remaining_hours=%.2f, remaining_miles=%.2f",
            remaining_trip_hours,
            remaining_trip_miles,
        )
        logger.debug("Updated driver state: %s", driver_state)

        # Round small remaining hours to zero
        if remaining_trip_hours < MINIMUM_SEGMENT_HOURS:
            logger.debug(
                "Rounding remaining trip hours (%.2f) to zero", remaining_trip_hours
            )
            remaining_trip_hours = 0.0

        return True, current_time, remaining_trip_hours, remaining_trip_miles

    def add_34hr_reset(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        segments: List[RouteSegment],
    ) -> datetime.datetime:
        # TODO : should not be hard coded
        reset_duration_hours = 34.0
        start_time = current_time
        end_time = start_time + datetime.timedelta(hours=reset_duration_hours)

        logger.info(
            "Adding 34-hour reset from %s to %s",
            start_time.isoformat(),
            end_time.isoformat(),
        )

        # Create the 34-hour reset segment
        reset_segment = RouteSegment(
            type=SegmentType.DRIVING_REST,
            start_time=start_time,
            end_time=end_time,
            duration_hours=reset_duration_hours,
            distance_miles=0.0,
            location="34-Hour Reset",
            status=DutyStatus.OFF_DUTY,
        )

        segments.append(reset_segment)

        driver_state.reset_duty_hours_after_34hr_reset()

        return end_time
