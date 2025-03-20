import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Type

from hos_rules.rules import HOSInterstateRule, HOSRulesFactory, RuleType
from repository.mixins import Location, RouteInformation

from .activity_planner import TripActivityPlannerMixin
from .trip_segment_planner import (
    DriverState,
    RouteSegment,
    RouteSegmentsData,
    SegmentType,
    TripSegmentPlannerMixin,
)
from .trip_summarizer import TripSummaryMixin


@dataclass
class RoutePlan:
    segments: List[RouteSegment]
    total_distance_miles: float
    total_duration_hours: float
    start_time: datetime.datetime
    end_time: datetime.datetime
    route_geometry: Any


class AbstractRoutePlanner(ABC):
    """Abstract base class defining the template method pattern for route planning."""

    def plan_route_trip(self) -> RoutePlan:
        """
        Template method that defines the skeleton of the route planning algorithm.
        Steps with @abstractmethod must be implemented by subclasses.
        """
        # Start time for the entire trip
        start_time = datetime.datetime.now(datetime.timezone.utc)
        current_time = start_time

        # Initialize driver state
        driver_state = self._initialize_driver_state()

        # Step 1: Plan route to pickup
        pickup_info = self._plan_to_pickup(current_time, driver_state)
        segments = pickup_info.segments
        current_time = pickup_info.end_time
        driver_state = pickup_info.driver_state

        # Step 2: Handle pickup activity
        pickup_result = self._handle_pickup(current_time, driver_state)
        segments.append(pickup_result.segments)
        current_time = pickup_result.end_time
        driver_state = pickup_result.driver_state

        # Step 3: Plan route to drop_off
        drop_off_info = self._plan_to_drop_off(current_time, driver_state)
        segments.extend(drop_off_info.segments)
        current_time = drop_off_info.end_time
        driver_state = drop_off_info.driver_state

        # Step 4: Handle drop_off activity
        drop_off_result = self._handle_drop_off(current_time, driver_state)
        segments.append(drop_off_result.segments)
        end_time = drop_off_result.end_time

        # Step 5: Calculate trip summary
        return self._calculate_trip_summary(
            segments=segments,
            start_time=start_time,
            end_time=end_time,
            pickup_geometry=pickup_result.geometry,
            drop_off_geometry=drop_off_result.geometry,
        )

    @abstractmethod
    def _initialize_driver_state(self) -> DriverState:
        """Initialize the driver's current state based on HOS rules."""
        pass

    @abstractmethod
    def _plan_to_pickup(
        self, current_time: datetime.datetime, driver_state: DriverState
    ) -> RouteSegmentsData:
        """Plan segments from current location to pickup."""
        pass

    @abstractmethod
    def _handle_pickup(
        self, current_time: datetime.datetime, driver_state: DriverState
    ) -> RouteSegmentsData:
        """Handle pickup activity."""
        pass

    @abstractmethod
    def _plan_to_drop_off(
        self, current_time: datetime.datetime, driver_state: DriverState
    ) -> RouteSegmentsData:
        """Plan segments from pickup to drop_off."""
        pass

    @abstractmethod
    def _handle_drop_off(
        self, current_time: datetime.datetime, driver_state: DriverState
    ) -> RouteSegmentsData:
        """Handle drop_off activity."""
        pass

    @abstractmethod
    def _calculate_trip_summary(
        self,
        segments: List[RouteSegment],
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        pickup_geometry: Any,
        drop_off_geometry: Any,
    ) -> RoutePlan:
        """Calculate trip summary and create final route plan."""
        pass


class StandardRoutePlanner(
    AbstractRoutePlanner,
    TripSegmentPlannerMixin,
    TripActivityPlannerMixin,
    TripSummaryMixin,
):
    """Concrete implementation of the route planner for standard HOS rules."""

    __slots__ = (
        "_current_location",
        "_hos_rule",
        "_drop_off_location",
        "_pickup_location",
        "_current_cycle_used",
    )

    def __init__(
        self,
        current_location: Location,
        pickup_location: Location,
        drop_off_location: Location,
        rule_type: RuleType,
        current_cycle_used: float,
    ):
        self._current_location = current_location
        self._pickup_location = pickup_location
        self._drop_off_location = drop_off_location
        self._hos_rule = self.__init_hos_rule(rule_type)
        self._current_cycle_used = current_cycle_used

    @staticmethod
    def __init_hos_rule(rule_type: RuleType) -> Type[HOSInterstateRule]:
        return HOSRulesFactory.get_rule(rule_type)

    def _initialize_driver_state(self) -> DriverState:
        """Initialize the driver state with the last current cycle used"""
        driver_state = DriverState()
        driver_state.duty_hours_last_8_days[7] = self._current_cycle_used

        return driver_state

    def _plan_to_pickup(
        self, current_time: datetime.datetime, driver_state: DriverState
    ) -> RouteSegmentsData:
        """Plan segments from current location to pickup."""
        to_pickup_route = self._get_route_between(
            self._current_location, self._pickup_location
        )

        return self.plan_route_segment(
            start_time=current_time,
            segment_type=SegmentType.DRIVE_TO_PICKUP,
            total_trip_hours=to_pickup_route.duration_hours,
            total_trip_distance_miles=to_pickup_route.distance_miles,
            geometry=to_pickup_route.geometry,
            driver_state=driver_state,
            hos_rule=self._hos_rule,
        )

    def _handle_pickup(
        self, current_time: datetime.datetime, driver_state: DriverState
    ) -> RouteSegmentsData:

        return self.handle_pickup(
            current_time=current_time,
            driver_state=driver_state,
            hos_rule=self._hos_rule,
        )

    def _plan_to_drop_off(
        self, current_time: datetime.datetime, driver_state: DriverState
    ) -> RouteSegmentsData:
        """Plan segments from pickup to drop_off."""
        to_drop_off_route = self._get_route_between(
            self._pickup_location, self._drop_off_location
        )

        return self.plan_route_segment(
            start_time=current_time,
            segment_type=SegmentType.DRIVE_TO_DROP_OFF,
            total_trip_hours=to_drop_off_route.duration_hours,
            total_trip_distance_miles=to_drop_off_route.distance_miles,
            geometry=to_drop_off_route.geometry,
            driver_state=driver_state,
            hos_rule=self._hos_rule,
        )

    def _handle_drop_off(
        self, current_time: datetime.datetime, driver_state: DriverState
    ) -> RouteSegmentsData:
        return self.handle_drop_off(
            current_time=current_time,
            driver_state=driver_state,
            hos_rule=self._hos_rule,
        )

    def _calculate_trip_summary(
        self,
        segments: List[RouteSegment],
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        pickup_geometry,
        drop_off_geometry,
    ) -> RoutePlan:
        """Calculate trip summary and create final route plan."""
        return self.calculate_trip_summary(
            segments=segments,
            start_time=start_time,
            end_time=end_time,
            to_pickup_geometry=pickup_geometry,
            to_drop_off_geometry=drop_off_geometry,
        )

    def _get_route_between(
        self, origin: Location, destination: Location
    ) -> RouteInformation:
        """
        Get the route information between two locations.

        Args:
            origin: Starting location
            destination: Ending location

        Returns:
            Dictionary containing route details (duration, distance, geometry)
        """
        # This would typically call a routing service API
        # Implementation is placeholder and would be replaced with actual routing logic

        return RouteInformation(
            duration_hours=5.0, distance_miles=300.0, geometry="", steps=[]
        )
