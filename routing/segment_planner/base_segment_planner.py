import datetime
import logging
from abc import ABC, abstractmethod
from collections import namedtuple
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Type

from hos_rules.rules import HOSInterstateRule
from repository.async_.mixins import RouteGeometry

from ..driver_state import DriverState

logger = logging.getLogger(__name__)

RouteSegmentsData = namedtuple(
    "RouteSegmentsData", ["segments", "end_time", "driver_state", "geometry"]
)


class DutyStatus(Enum):
    """
    Enum representing the different duty statuses for a driver.

    Attributes:
        ON_DUTY_DRIVING: Driver is actively driving the vehicle.
        OFF_DUTY: Driver is not working and is on rest period.
        ON_DUTY_NOT_DRIVING: Driver is working but not driving
        (e.g., loading, unloading, refueling).
        SLEEPER_BETH : where you take the mandatory 10hr breah
    """

    ON_DUTY_DRIVING = "On Duty (Driving)"
    OFF_DUTY = "Off Duty"
    ON_DUTY_NOT_DRIVING = "On Duty (Not Driving)"
    SLEEPER_BETH = "sleeperBerth"


class SegmentType(Enum):
    """
    Enum representing the different types of segments in a driver's journey.

    Attributes:
        PICKUP: Driver is at a pickup location.
        DROP_OFF: Driver is at a drop-off location.
        DRIVE_TO_PICKUP: Driver is driving to a pickup location.
        DRIVE_TO_DROP_OFF: Driver is driving to a drop-off location.
        MANDATORY_DRIVING_BREAK: a required break after hours of driving.
        MANDATORY_REST_PERIOD: a required daily rest period.
        REFUELING: Vehicle refueling stop.
        REFUELING_WITH_BREAK: Refueling stop that also fulfills the
         mandatory driving break requirement.
    """

    PICKUP = "pickup"
    DROP_OFF = "drop_off"
    DRIVE_TO_PICKUP = "drive to pickup"
    DRIVE_TO_DROP_OFF = "drive to drop off"
    MANDATORY_DRIVING_BREAK = (
        "mandatory_driving_break"  # e.g Required 30-min break after 8hrs
    )
    MANDATORY_REST_PERIOD = "mandatory_rest_period"  # e.g Required 10-hr daily rest
    REFUELING = "refueling"
    # A one-hour refueling stop automatically fulfills the mandatory
    # driving break
    REFUELING_WITH_BREAK = "refueling_and_break"
    DRIVING_REST = "driving_rest"  # 34HR mandatory reset


@dataclass
class RouteSegment:
    """
    Represents a single segment of a driver's journey with associated timings and status.

    Attributes:
        type: The type of segment (pickup, driving, break, etc.).
        start_time: The time when this segment begins.
        end_time: The time when this segment ends.
        duration_hours: The duration of this segment in hours.
        distance_miles: The distance covered during this segment in miles.
        location: A description of the location for this segment.
        status: The duty status of the driver during this segment.
    """

    type: SegmentType
    start_time: datetime.datetime
    end_time: datetime.datetime
    duration_hours: float
    distance_miles: float
    location: str
    status: DutyStatus

    def to_dict(self) -> dict:
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


class BaseAbstractTripSegmentPlanner(ABC):
    """
    Abstract base class for trip segment planning using the Template Method pattern.

    This class defines the skeleton of the route planning algorithm,
    with specific steps deferred to subclasses.
    """

    def plan_route_segment(
        self,
        start_time: datetime.datetime,
        segment_type: SegmentType,
        total_trip_hours: float,
        total_trip_distance_miles: float,
        geometry: RouteGeometry,
        driver_state: DriverState,
        hos_rule: Type[HOSInterstateRule],
    ) -> RouteSegmentsData:
        """
        Template method that defines the skeleton of the route planning algorithm.

        Args:
            start_time: When this segment starts
            segment_type: Type of segment (e.g., "Drive to Pickup")
            total_trip_hours: Total driving time required for the planned route segment
            total_trip_distance_miles: Total distance to drive for the planned route segment
            geometry: OSRM route geometry (LineString)
            driver_state: Current driver state tracking HOS compliance
            hos_rule: Hours of Service rule to apply

        Returns:
            RouteSegmentsData: A named tuple containing the planned route segments and related data
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

            # Step 1: Initialize on-duty window and check day changes
            current_time = self.initialize_duty_window(
                driver_state, current_time, remaining_trip_hours
            )

            # Step 2: Handle required breaks and operational needs

            # Check if 34-hour reset is needed
            if self.check_34hr_reset_needed(driver_state):
                logger.info(
                    "34-hour reset needed: total duty hours in last 8 days ≥ 60"
                )
                current_time = self.add_34hr_reset(driver_state, current_time, segments)
                continue

            # Handle refueling (highest priority)
            segment_added, current_time = self.handle_refueling(
                driver_state, current_time, segments
            )
            if segment_added:
                continue

            # Check HOS limits
            needs_rest, rest_reason = self.check_hos_rest_needed(
                driver_state, current_time, hos_rule
            )

            if needs_rest:
                logger.info("Rest needed: %s", rest_reason)
                current_time = self.add_rest_period(
                    driver_state, current_time, segments, hos_rule
                )
                continue

            # TODO: remove add coding of 30 min name
            # Check if 30-minute break needed
            if driver_state.needs_30min_break:
                current_time = self.add_30min_break(
                    driver_state, current_time, segments, hos_rule
                )
                continue

            # Step 3: Create driving segment if hours are available
            segment_added, current_time, remaining_trip_hours, remaining_trip_miles = (
                self.create_driving_segment(
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
                current_time = self.add_rest_period(
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

    def check_34hr_reset_needed(self, driver_state: DriverState) -> bool:
        """
        Check if the driver needs a 34-hour reset based on the 60-hour/8-day rule.

        Args:
            driver_state: The current state of the driver including HOS compliance tracking.

        Returns:
            bool: True if a 34-hour reset is needed, False otherwise.
        """
        # Check if total duty hours in the last 8 days is greater than or equal to 60
        return driver_state.total_duty_hours_last_8_days >= 61

    @abstractmethod
    def add_34hr_reset(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        segments: List[RouteSegment],
    ) -> datetime.datetime:
        """
        Add a 34-hour reset period and update driver state.

        Args:
            driver_state: The current state of the driver including HOS compliance tracking.
            current_time: The current datetime being evaluated.
            segments: The list of route segments to append to.

        Returns:
            datetime.datetime: The updated current time after the 34-hour reset.
        """
        raise NotImplementedError("add_34hr_reset not implemented")

    @abstractmethod
    def initialize_duty_window(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        remaining_hours: float,
    ) -> datetime.datetime:
        """
        Initialize on-duty window if needed and check for day changes.

        Args:
            driver_state: The current state of the driver including HOS compliance tracking.
            current_time: The current datetime being evaluated.
            remaining_hours: The number of hours remaining in the planned trip.

        Returns:
            datetime.datetime: The updated current time after any necessary adjustments.
        """
        pass

    @abstractmethod
    def handle_refueling(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        segments: List[RouteSegment],
    ) -> Tuple[bool, datetime.datetime]:
        """
        Handle vehicle refueling if needed.

        Args:
            driver_state: The current state of the driver including HOS compliance tracking.
            current_time: The current datetime being evaluated.
            segments: The list of route segments to append to.

        Returns:
            Tuple[bool, datetime.datetime]: A tuple containing:
                - A boolean indicating whether a refueling segment was added.
                - The updated current time after any refueling.
        """
        pass

    @abstractmethod
    def check_hos_rest_needed(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        hos_rule: Type[HOSInterstateRule],
    ) -> Tuple[bool, str]:
        """
        Check if driver needs a mandatory rest period based on HOS rules.

        Args:
            driver_state: The current state of the driver including HOS compliance tracking.
            current_time: The current datetime being evaluated.
            hos_rule: The Hours of Service rule class to apply.

        Returns:
            Tuple[bool, str]: A tuple containing:
                - A boolean indicating whether a rest period is needed.
                - A string explaining the reason for rest if needed, empty string otherwise.
        """
        pass

    @abstractmethod
    def add_rest_period(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        segments: List[RouteSegment],
        hos_rule: Type[HOSInterstateRule],
    ) -> datetime.datetime:
        """
        Add a mandatory rest period and update driver state.

        Args:
            driver_state: The current state of the driver including HOS compliance tracking.
            current_time: The current datetime being evaluated.
            segments: The list of route segments to append to.
            hos_rule: The Hours of Service rule class to apply.

        Returns:
            datetime.datetime: The updated current time after the rest period.
        """
        pass

    @abstractmethod
    def add_30min_break(
        self,
        driver_state: DriverState,
        current_time: datetime.datetime,
        segments: List[RouteSegment],
        hos_rule: Type[HOSInterstateRule],
    ) -> datetime.datetime:
        """
        Add a 30-minute break and update driver state.

        Args:
            driver_state: The current state of the driver including HOS compliance tracking.
            current_time: The current datetime being evaluated.
            segments: The list of route segments to append to.
            hos_rule: The Hours of Service rule class to apply.

        Returns:
            datetime.datetime: The updated current time after the break.
        """
        pass

    @abstractmethod
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

        Args:
            driver_state: The current state of the driver including HOS compliance tracking.
            current_time: The current datetime being evaluated.
            remaining_trip_hours: The number of hours remaining in the planned trip.
            remaining_trip_miles: The distance in miles remaining in the planned trip.
            segments: The list of route segments to append to.
            segment_type: The type of segment to create.

        Returns:
            Tuple[bool, datetime.datetime, float, float]: A tuple containing:
                - A boolean indicating whether a segment was added.
                - The updated current time after any driving.
                - The updated remaining trip hours.
                - The updated remaining trip miles.
        """
        pass
