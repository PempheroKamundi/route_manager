import datetime
import logging
from collections import namedtuple
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Tuple, Type

from hos_rules.rules import HOSInterstateRule

from .driver_state import DriverState

logger = logging.getLogger(__name__)

# Constants for time durations
REFUELING_HOURS = 1.0
MINIMUM_SEGMENT_HOURS = 0.1  # 6 minutes

RouteSegmentsData = namedtuple(
    "RouteSegmentsData", ["segments", "end_time", "driver_state", "geometry"]
)


class DutyStatus(Enum):
    ON_DUTY_DRIVING = "On Duty (Driving)"
    OFF_DUTY = "Off Duty"
    ON_DUTY_NOT_DRIVING = "On Duty (Not Driving)"


class SegmentType(Enum):
    PICKUP = "pickup"
    DROP_OFF = "drop_off"
    DRIVE_TO_PICKUP = "drive to pickup"
    DRIVE_TO_DROP_OFF = "drive to drop off"
    MANDATORY_DRIVING_BREAK = (
        "mandatory_driving_break"  # Required 30-min break after 8hrs
    )
    MANDATORY_REST_PERIOD = "mandatory_rest_period"  # Required 10-hr daily rest
    REFUELING = "refueling"


@dataclass
class RouteSegment:
    type: SegmentType
    start_time: datetime.datetime
    end_time: datetime.datetime
    duration_hours: float
    distance_miles: float
    location: str
    status: DutyStatus

    def to_dict(self):
        """
        Serializes the RouteSegment object to a dictionary.

        Returns:
            dict: Dictionary representation of the RouteSegment with serialized datetime objects
                  and enum values converted to strings.
        """
        return {
            "type": self.type.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_hours": self.duration_hours,
            "distance_miles": self.distance_miles,
            "location": self.location,
            "status": self.status.value,
        }

    def __repr__(self):
        return (
            f"RouteSegment(type={self.type.value},"
            f" start={self.start_time.strftime('%Y-%m-%d %H:%M')}, "
            f"end={self.end_time.strftime('%Y-%m-%d %H:%M')},"
            f" duration={self.duration_hours:.2f} hrs, "
            f"distance={self.distance_miles:.2f} mi, "
            f"status={self.status.value})"
        )


class TripSegmentPlannerMixin:
    @staticmethod
    def plan_route_segment(
        start_time: datetime.datetime,
        segment_type: SegmentType,
        total_trip_hours: float,
        total_trip_distance_miles: float,
        geometry: Any,
        driver_state: DriverState,
        hos_rule: Type[HOSInterstateRule],
    ) -> RouteSegmentsData:
        """
        Plan a route segment considering HOS regulations and breaks.

        Args:
            start_time: When this segment starts
            segment_type: Type of segment (e.g., "Drive to Pickup")
            total_trip_hours: Total driving time required for the planned route segment
            total_trip_distance_miles: Total distance to drive for the planned route segment
            geometry: Route geometry for visualization
            driver_state: Current driver state tracking HOS compliance
            hos_rule: Hours of Service rule to apply

        Returns:
            Dictionary with planned segments, end time, and updated driver state
        """
        logger.info(
            "Starting route segment planning: type=%s, hours=%.2f, miles=%.2f",
            segment_type,
            total_trip_hours,
            total_trip_distance_miles,
        )
        logger.debug("Initial driver state: %s", driver_state)

        segments: List[RouteSegment] = []
        current_time = start_time
        remaining_trip_hours = total_trip_hours
        remaining_trip_miles = total_trip_distance_miles

        logger.info(
            "Planning route from time=%s with remaining hours=%.2f",
            current_time,
            remaining_trip_hours,
        )

        # Continue until the entire trip segment is planned
        while remaining_trip_hours > 0:
            logger.debug(
                "Trip planning iteration: remaining_hours=%.2f, current_time=%s",
                remaining_trip_hours,
                current_time,
            )

            # ---------------------------------------------------------
            # Step 1: Initialize on-duty window and check day changes
            # ---------------------------------------------------------
            current_time = TripSegmentPlannerMixin._initialize_duty_window(
                driver_state, current_time, remaining_trip_hours
            )

            # ---------------------------------------------------------
            # Step 2: Handle required breaks and operational needs
            # ---------------------------------------------------------

            # Handle refueling (highest priority - can be done even after 14-hr window)
            segment_added, current_time = TripSegmentPlannerMixin._handle_refueling(
                driver_state, current_time, segments
            )
            if segment_added:
                continue

            # Check HOS limits (14-hour window, 70-hour/8-day)
            needs_rest, rest_reason = TripSegmentPlannerMixin._check_hos_rest_needed(
                driver_state, current_time, hos_rule
            )

            if needs_rest:
                logger.info("Rest needed : %s", rest_reason)
                current_time = TripSegmentPlannerMixin._add_rest_period(
                    driver_state, current_time, segments, hos_rule
                )
                continue

            # Check if 30-minute break needed
            if driver_state.needs_30min_break:
                current_time = TripSegmentPlannerMixin._add_30min_break(
                    driver_state, current_time, segments, hos_rule
                )
                continue

            # ---------------------------------------------------------
            # Step 3: Create driving segment if hours are available
            # ---------------------------------------------------------
            segment_added, current_time, remaining_trip_hours, remaining_trip_miles = (
                TripSegmentPlannerMixin._create_driving_segment(
                    driver_state,
                    current_time,
                    remaining_trip_hours,
                    remaining_trip_miles,
                    segments,
                    segment_type,
                )
            )

            # If segment wasn't added (no hours available), force rest period
            if not segment_added:
                logger.info("No driving hours available, adding rest period")
                current_time = TripSegmentPlannerMixin._add_rest_period(
                    driver_state, current_time, segments, hos_rule
                )

        logger.info(
            "Route segment planning completed: %d segments created", len(segments)
        )
        logger.debug("Final driver state: %s", driver_state)

        return RouteSegmentsData(
            segments=segments,
            end_time=current_time,
            driver_state=driver_state,
            geometry=geometry,
        )

    @staticmethod
    def _initialize_duty_window(
        driver_state: DriverState,
        current_time: datetime.datetime,
        remaining_hours: float,
    ) -> datetime.datetime:
        """Initialize on-duty window if needed and check for day changes"""
        # If no on-duty window has started yet, start one now
        if driver_state.current_on_duty_window_start is None and remaining_hours > 0:
            driver_state.current_on_duty_window_start = current_time
            logger.info("Starting new on-duty window at time=%s", current_time)

        # Check for day changes
        driver_state.check_day_change(current_time)
        logger.debug("After day change check: %s", driver_state)

        return current_time

    @staticmethod
    def _handle_refueling(
        driver_state: DriverState,
        current_time: datetime.datetime,
        segments: List[RouteSegment],
    ) -> Tuple[bool, datetime.datetime]:
        """Handle vehicle refueling if needed"""
        if not driver_state.needs_refueling:
            return False, current_time

        logger.info("Vehicle needs refueling at time=%s", current_time)

        # Add refuel time
        refuel_end_time = current_time + datetime.timedelta(hours=REFUELING_HOURS)

        segments.append(
            RouteSegment(
                type=SegmentType.REFUELING,
                start_time=current_time,
                end_time=refuel_end_time,
                duration_hours=REFUELING_HOURS,
                distance_miles=0,
                location="Roadside",
                status=DutyStatus.ON_DUTY_NOT_DRIVING,
            )
        )

        # Update driver state
        current_time = refuel_end_time
        driver_state.add_on_duty_hours(REFUELING_HOURS)
        driver_state.refuel()
        logger.debug("After refueling: %s", driver_state)

        return True, current_time

    @staticmethod
    def _check_hos_rest_needed(
        driver_state: DriverState,
        current_time: datetime.datetime,
        hos_rule: Type[HOSInterstateRule],
    ) -> Tuple[bool, str]:
        """Check if driver needs a mandatory rest period based on HOS rules"""
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

    @staticmethod
    def _add_rest_period(
        driver_state: DriverState,
        current_time: datetime.datetime,
        segments: List[RouteSegment],
        hos_rule: Type[HOSInterstateRule],
    ) -> datetime.datetime:
        """Add a mandatory rest period and update driver state"""
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
                location="Rest Location",
                status=DutyStatus.OFF_DUTY,
            )
        )

        current_time = rest_end_time
        # Reset driver state after 10-hour break
        driver_state.take_10_hour_break()
        logger.debug("After 10-hour break: %s", driver_state)

        return current_time

    @staticmethod
    def _add_30min_break(
        driver_state: DriverState,
        current_time: datetime.datetime,
        segments: List[RouteSegment],
        hos_rule: Type[HOSInterstateRule],
    ) -> datetime.datetime:
        """Add a 30-minute break and update driver state"""
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
                location="Break Location",
                status=DutyStatus.OFF_DUTY,
            )
        )

        current_time = break_end_time
        driver_state.add_30_min_break()
        logger.debug("After 30-minute break: %s", driver_state)

        return current_time

    @staticmethod
    def _create_driving_segment(
        driver_state: DriverState,
        current_time: datetime.datetime,
        remaining_trip_hours: float,
        remaining_trip_miles: float,
        segments: List[RouteSegment],
        segment_type: SegmentType,
    ) -> Tuple[bool, datetime.datetime, float, float]:
        """Create a driving segment if hours are available"""
        # Calculate how many hours can be driven in this stretch
        available_driving_hours = driver_state.available_driving_hours
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

        # Create a driving segment
        logger.info(
            "Creating driving segment for %.2f hours, %.2f miles",
            max_driving_hours,
            (max_driving_hours / remaining_trip_hours) * remaining_trip_miles,
        )

        segment_end_time = current_time + datetime.timedelta(hours=max_driving_hours)
        segment_distance = (
            max_driving_hours / remaining_trip_hours
        ) * remaining_trip_miles

        segments.append(
            RouteSegment(
                type=segment_type,
                start_time=current_time,
                end_time=segment_end_time,
                duration_hours=max_driving_hours,
                distance_miles=segment_distance,
                location="On Route",
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
