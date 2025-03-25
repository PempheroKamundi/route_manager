"""
routing.route_planner.base_route_planner
~~~~~~~~~~~~~

Core orchestration module for generating compliant routing plans that
adhere to Hours of Service (HOS) regulations. This module intelligently
manages route planning by considering the driver's current
position, required pickup and delivery locations, and the driver's
accumulated on-duty hours to prevent regulatory violations while optimizing
delivery efficiency.
"""

import datetime
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Any, List

from repository.async_.mixins import RouteInformation

from ..segment_planner.base_segment_planner import (
    DriverState,
    RouteSegment,
    RouteSegmentsData,
)
from ..trip_summarizer import RoutePlan

RoutesInBetween = namedtuple(
    "RoutesInBetween", ["to_pickup_route", "to_drop_off_route"]
)


class BaseAbstractRoutePlanner(ABC):
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
            pickup_geometry=route_in_between_data.to_pickup_route.geometry,
            drop_off_geometry=route_in_between_data.to_drop_off_route.geometry,
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
