"""
routing.route_planner
~~~~~~~~~~~~~

Main module that coordinates the routing plan to ensure compliance
with Hours of Service (HOS) regulations, taking into account current location,
pickup and drop-off points, while factoring in previously accumulated
duty cycle hours
"""

import asyncio
import datetime
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Any, List, Type

from hos_rules.rules import HOSInterstateRule, HOSRulesFactory, RuleType
from repository.async_.mixins import Location, RouteInformation
from repository.async_.osrm_repository import get_route_information

from .activity_planner import TripActivityPlannerMixin
from .trip_segment_planner import (
    DriverState,
    RouteSegment,
    RouteSegmentsData,
    SegmentType,
    TripSegmentPlannerMixin,
)
from .trip_summarizer import RoutePlan, TripSummaryMixin

RoutesInBetween = namedtuple(
    "RoutesInBetween", ["to_pickup_route", "to_drop_off_route"]
)


class AbstractRoutePlanner(ABC):
    """
    Abstract base class defining the template method pattern for route planning.

    This class implements the skeleton of the route planning algorithm while
    deferring specific implementation details to subclasses. It follows the
    template method design pattern to enforce a standard workflow while
    allowing customization of individual steps.

    Subclasses must implement all abstract methods to create a concrete
    route planner that can generate complete route plans.
    """

    async def plan_route_trip(self, start_time: datetime.datetime) -> RoutePlan:
        """
        Template method that defines the skeleton of the route planning algorithm.

        This method orchestrates the entire route planning process by calling
        the various steps in sequence, while managing state transitions between steps.

        Steps with @abstractmethod must be implemented by subclasses.

        Args:
            start_time (datetime.datetime): the start time of the route plan.

        Returns:
            RoutePlan: A complete route plan with all segments, timing information,
                       and summary statistics.
        """

        route_in_between_data = await self.get_routes_in_between()

        # Start time for the entire trip
        current_time = start_time

        # Initialize driver state
        driver_state = self._initialize_driver_state()

        # Step 1: Plan route to pickup
        pickup_info = self._plan_to_pickup(
            current_time, driver_state, route_in_between_data.to_pickup_route
        )
        segments = pickup_info.segments
        current_time = pickup_info.end_time
        driver_state = pickup_info.driver_state

        # Step 2: Handle pickup activity
        pickup_result = self._handle_pickup(
            current_time, driver_state, route_in_between_data.to_pickup_route
        )
        segments.append(pickup_result.segments)
        current_time = pickup_result.end_time
        driver_state = pickup_result.driver_state

        # Step 3: Plan route to drop_off
        drop_off_info = self._plan_to_drop_off(
            current_time, driver_state, route_in_between_data.to_drop_off_route
        )
        segments.extend(drop_off_info.segments)
        current_time = drop_off_info.end_time
        driver_state = drop_off_info.driver_state

        # Step 4: Handle drop_off activity
        drop_off_result = self._handle_drop_off(
            current_time, driver_state, route_in_between_data.to_drop_off_route
        )
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
        """
        Initialize the driver's current state based on Hours of Service (HOS) rules.

        Returns:
            DriverState: The initialized driver state object.
        """
        pass

    @abstractmethod
    def _plan_to_pickup(
        self,
        current_time: datetime.datetime,
        driver_state: DriverState,
        to_pickup_route: RouteInformation,
    ) -> RouteSegmentsData:
        """
        Plan segments from current location to pickup location.

        Args:
            current_time (datetime.datetime): The current time when planning starts.
            driver_state (DriverState): The current state of the driver.

        Returns:
            RouteSegmentsData: Contains the planned route segments, the expected end time,
                               and the updated driver state after reaching the pickup location.
        """
        pass

    @abstractmethod
    def _handle_pickup(
        self,
        current_time: datetime.datetime,
        driver_state: DriverState,
        pickup_route: RouteInformation,
    ) -> RouteSegmentsData:
        """
        Handle pickup activity at the pickup location.


        Args:
            current_time (datetime.datetime): The time when the driver arrives at
             the pickup location.
            driver_state (DriverState): The driver's state upon arrival at the pickup location.

        Returns:
            RouteSegmentsData: Contains the pickup activity as a route segment, the time when
                               pickup is completed, the updated driver state, and the pickup
                               location geometry.
        """
        pass

    @abstractmethod
    def _plan_to_drop_off(
        self,
        current_time: datetime.datetime,
        driver_state: DriverState,
        to_drop_off_route: RouteInformation,
    ) -> RouteSegmentsData:
        """
        Plan segments from pickup location to drop-off location.

        Args:
            current_time (datetime.datetime): The time when the driver departs
            from the pickup location.
            driver_state (DriverState): The driver's state after completing
            pickup activities.

        Returns:
            RouteSegmentsData: Contains the planned route segments, the expected
                                arrival time
                               at the drop-off location, and the updated driver state.
        """
        pass

    @abstractmethod
    def _handle_drop_off(
        self,
        current_time: datetime.datetime,
        driver_state: DriverState,
        drop_off_info: RouteInformation,
    ) -> RouteSegmentsData:
        """
        Handle drop-off activity at the drop-off location.

        Args:
            current_time (datetime.datetime): The time when the driver arrives
            at the drop-off location.
            driver_state (DriverState): The driver's state upon arrival at the drop-off location.

        Returns:
            RouteSegmentsData: Contains the drop-off activity as a route segment, the time when
                               drop-off is completed, the updated driver state, and
                               the drop-off location geometry.
        """
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
        """
        Calculate trip summary and create the final route plan.


        Args:
            segments (List[RouteSegment]): All route segments from the trip.
            start_time (datetime.datetime): The time when the trip started.
            end_time (datetime.datetime): The time when the trip ended.
            pickup_geometry (Any): Geometry data for the pickup location.
            drop_off_geometry (Any): Geometry data for the drop-off location.

        Returns:
            RoutePlan: A complete route plan containing all segments and summary information.
        """
        pass

    async def get_routes_in_between(self) -> RoutesInBetween:
        raise NotImplementedError


class StandardRoutePlanner(
    AbstractRoutePlanner,
    TripSegmentPlannerMixin,
    TripActivityPlannerMixin,
    TripSummaryMixin,
):
    """
    Concrete implementation of the route planner for standard Hours of Service (HOS) rules.

    This planner orchestrates the planning of a complete route from the current location
    to a pickup location and then to a drop-off location, following HOS regulations.

    Attributes:
        _current_location: The driver's current location.
        _hos_rule: The Hours of Service rule applicable for this route.
        _drop_off_location: The final destination where cargo will be delivered.
        _pickup_location: The location where cargo will be picked up.
        _current_cycle_used: The amount of cycle hours already used by the driver.
    """

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
    ) -> None:
        """
        Initialize a StandardRoutePlanner with the necessary location and HOS information.

        Args:
            current_location: The driver's current geographical location.
            pickup_location: The location where cargo will be picked up.
            drop_off_location: The final destination where cargo will be delivered.
            rule_type: The type of Hours of Service rule to apply for this route.
            current_cycle_used: The amount of cycle hours already used by the driver.
        """
        self._current_location = current_location
        self._pickup_location = pickup_location
        self._drop_off_location = drop_off_location
        self._hos_rule = self.__init_hos_rule(rule_type)
        self._current_cycle_used = current_cycle_used

    @staticmethod
    def __init_hos_rule(rule_type: RuleType) -> Type[HOSInterstateRule]:
        """
        Initialize the appropriate HOS rule based on the rule type.

        Args:
            rule_type: The type of Hours of Service rule to instantiate.

        Returns:
            A concrete HOSInterstateRule class based on the provided rule type.
        """
        return HOSRulesFactory.get_rule(rule_type)

    def _initialize_driver_state(self) -> DriverState:
        """
        Initialize the driver state with the last current cycle used.

        This method creates a new driver state and sets the duty hours
        for the last day of an 8-day cycle.

        Returns:
            A new DriverState object initialized with the current cycle hours used.
        """
        driver_state = DriverState()
        # since arrays start at zero, 7 is actually the eighth day here
        driver_state.duty_hours_last_8_days[7] = self._current_cycle_used

        return driver_state

    def _plan_to_pickup(
        self,
        current_time: datetime.datetime,
        driver_state: DriverState,
        to_pickup_route: RouteInformation,
    ) -> RouteSegmentsData:
        """
        Plan segments from the current location to the pickup location.

        This method calculates the driving segments required to reach the pickup location,
        considering HOS constraints and required rest periods.

        Args:
            current_time: The current date and time when planning starts.
            driver_state: The current state of the driver regarding HOS regulations.
            to_pickup_route: Route information from current location to pickup location.

        Returns:
            Detailed data about the route segments from current location to pickup.
        """
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
        self,
        current_time: datetime.datetime,
        driver_state: DriverState,
        pickup_info: RouteInformation,
    ) -> RouteSegmentsData:
        """
        Handle pickup activities at the pickup location.

        This method manages the time and driver state changes that occur during
        pickup activities, such as loading and paperwork.

        Args:
            current_time: The date and time when the driver arrives at pickup.
            driver_state: The current state of the driver regarding HOS regulations.
            pickup_info: Information about the pickup location and activities.

        Returns:
            Detailed data about the pickup activity segment.
        """
        return self.handle_pickup(
            current_time=current_time,
            driver_state=driver_state,
            hos_rule=self._hos_rule,
            data=pickup_info,
            segment_type=SegmentType.PICKUP,
        )

    def _plan_to_drop_off(
        self,
        current_time: datetime.datetime,
        driver_state: DriverState,
        to_drop_off_route: RouteInformation,
    ) -> RouteSegmentsData:
        """
        Plan segments from the pickup location to the drop-off location.

        This method calculates the driving segments required to reach the drop-off location,
        considering HOS constraints and required rest periods.

        Args:
            current_time: The date and time when the driver leaves the pickup location.
            driver_state: The current state of the driver regarding HOS regulations.
            to_drop_off_route: Route information from pickup to drop-off location.

        Returns:
            Detailed data about the route segments from pickup to drop-off.
        """
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
        self,
        current_time: datetime.datetime,
        driver_state: DriverState,
        drop_off_info: RouteInformation,
    ) -> RouteSegmentsData:
        """
        Handle drop-off activities at the destination.

        This method manages the time and driver state changes that occur during
        drop-off activities, such as unloading and paperwork.

        Args:
            current_time: The date and time when the driver arrives at drop-off.
            driver_state: The current state of the driver regarding HOS regulations.
            drop_off_info: Information about the drop-off location and activities.

        Returns:
            Detailed data about the drop-off activity segment.
        """
        return self.handle_drop_off(
            current_time=current_time,
            driver_state=driver_state,
            hos_rule=self._hos_rule,
            data=drop_off_info,
            segment_type=SegmentType.DROP_OFF,
        )

    def _calculate_trip_summary(
        self,
        segments: List[RouteSegment],
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        pickup_geometry: Any,
        drop_off_geometry: Any,
    ) -> RoutePlan:
        """
        Calculate trip summary and create the final route plan.

        This method aggregates all segments and calculates overall trip metrics
        to create a comprehensive route plan.

        Args:
            segments: List of all route segments in the trip.
            start_time: The date and time when the trip begins.
            end_time: The date and time when the trip ends.
            pickup_geometry: Geographical data for the pickup route.
            drop_off_geometry: Geographical data for the drop-off route.

        Returns:
            A complete route plan with all segments and summary information.
        """
        return self.calculate_trip_summary(
            segments=segments,
            start_time=start_time,
            end_time=end_time,
            to_pickup_geometry=pickup_geometry,
            to_drop_off_geometry=drop_off_geometry,
        )

    async def get_routes_in_between(self) -> RoutesInBetween:
        """
        Retrieve route information between current location, pickup, and drop-off.

        This asynchronous method fetches route information in parallel for both
        the current-to-pickup and pickup-to-drop-off segments.

        Returns:
            A RoutesInBetween object containing both route segments information.

        TODO:
            - Implement retry mechanism
            - Add caching mechanisms
        """

        pickup_route, drop_off_route = await asyncio.gather(
            get_route_information(self._current_location, self._pickup_location),
            get_route_information(self._pickup_location, self._drop_off_location),
        )

        return RoutesInBetween(
            to_pickup_route=pickup_route,
            to_drop_off_route=drop_off_route,
        )
