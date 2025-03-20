import datetime
from collections import namedtuple
from dataclasses import dataclass
from enum import Enum
from typing import Any, Type

from hos_rules.rules import HOSInterstateRule

from .driver_state import DriverState

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
    MAINTENANCE = "maintenance"  # cant drive, but can work period


@dataclass
class RouteSegment:
    type: SegmentType
    start_time: datetime.datetime
    end_time: datetime.datetime
    duration_hours: float
    distance_miles: float
    location: str
    status: DutyStatus


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
        Plan a route segment considering HOS regulations and.

        breaks.

        Args:
            start_time: When this segment starts
            segment_type: Type of segment (e.g., "Drive to Pickup")
            total_trip_hours: Total driving time required for the planned route segment
            total_trip_distance_miles: Total distance to drive for the planned route segment
            geometry: Route geometry for visualization
            driver_state: Current driver state tracking HOS compliance

        Returns:
            Dictionary with planned segments, end time, and updated driver state
        """
        segments = []
        current_time = start_time
        trip_hours = total_trip_hours
        trip_distance_miles = total_trip_distance_miles

        # Continue until the entire trip segment is planned
        while trip_hours > 0:
            # If no on-duty window has started yet, start one now
            if driver_state.current_on_duty_window_start is None and trip_hours > 0:
                driver_state.current_on_duty_window_start = current_time

            driver_state.check_day_change(current_time)

            # Check if driver needs a 10-hour rest period (reached 14-hour on-duty window or 11-hour driving limit)
            needs_rest = False
            cant_drive_but_can_work = False

            # Check 14-hour on-duty window limit
            if driver_state.current_on_duty_window_start is not None:
                on_duty_window_hours = (
                    current_time - driver_state.current_on_duty_window_start
                ).total_seconds() / 3600
                if on_duty_window_hours >= hos_rule.MAX_DUTY_HOURS.value:
                    needs_rest = True

            # Check 11-hour driving limit
            if (
                driver_state.current_day_driving_hours
                >= hos_rule.MAX_DRIVING_HOURS.value
            ):
                cant_drive_but_can_work = True

            # Check 70-hour/8-day limit
            if (
                driver_state.total_duty_hours_last_8_days
                >= hos_rule.MAX_CYCLE_HOURS.value
            ):
                needs_rest = True

            if needs_rest:

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
                continue

            if cant_drive_but_can_work:
                # Calculate remaining time in 14-hour duty window

                elapsed_window_hours = (
                    current_time - driver_state.current_on_duty_window_start
                ).total_seconds() / 3600

                remaining_window_hours = max(
                    0, hos_rule.MAX_DUTY_HOURS.value - elapsed_window_hours
                )
                work_end_time = current_time + datetime.timedelta(
                    hours=remaining_window_hours
                )

                segments.append(
                    RouteSegment(
                        type=SegmentType.MAINTENANCE,
                        start_time=current_time,
                        end_time=work_end_time,
                        duration_hours=remaining_window_hours,
                        distance_miles=0,
                        location="Rest Location",
                        status=DutyStatus.ON_DUTY_NOT_DRIVING,
                    )
                )

                driver_state.add_on_duty_hours(remaining_window_hours)
                current_time = work_end_time
                continue

            # Check if driver needs a 30-minute break after 8 hours of driving
            if driver_state.needs_30min_break:
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
                continue

                # Check if vehicle needs refueling
            if driver_state.needs_refueling:
                # Standard refueling time with jerry can is 15 minutes (0.25 hours)
                fueling_time = 0.25

                # Calculate remaining time in 14-hour duty window
                if driver_state.current_on_duty_window_start is not None:
                    elapsed_window_hours = (
                        current_time - driver_state.current_on_duty_window_start
                    ).total_seconds() / 3600
                    remaining_window_hours = (
                        hos_rule.MAX_DUTY_HOURS.value - elapsed_window_hours
                    )

                    # If less than 15 minutes remain, use whatever time is available
                    if remaining_window_hours < fueling_time:
                        fueling_time = max(0, remaining_window_hours)

                # Only add fueling segment if there's time available
                if fueling_time > 0:
                    refuel_end_time = current_time + datetime.timedelta(
                        hours=fueling_time
                    )

                    segments.append(
                        RouteSegment(
                            type=SegmentType.REFUELING,
                            start_time=current_time,
                            end_time=refuel_end_time,
                            duration_hours=fueling_time,
                            distance_miles=0,
                            location="Roadside",
                            status=DutyStatus.ON_DUTY_NOT_DRIVING,
                        )
                    )

                    current_time = refuel_end_time
                    driver_state.add_on_duty_hours(fueling_time)
                    driver_state.refuel()
                    continue
                else:
                    # No time left for refueling, need to rest first
                    needs_rest = True
                    continue

            # Calculate how many hours can be driven in this stretch
            available_hours = driver_state.available_driving_hours
            drivable_hours = min(available_hours, trip_hours)

            if drivable_hours <= 0:
                # Need a break - not enough driving hours available
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
                driver_state.take_10_hour_break()
                continue

            # Create a driving segment
            segment_end_time = current_time + datetime.timedelta(hours=drivable_hours)
            segment_distance = (drivable_hours / trip_hours) * trip_distance_miles

            segments.append(
                RouteSegment(
                    type=segment_type,
                    start_time=current_time,
                    end_time=segment_end_time,
                    duration_hours=drivable_hours,
                    distance_miles=segment_distance,
                    location="On Route",
                    status=DutyStatus.ON_DUTY_DRIVING,
                )
            )

            current_time = segment_end_time
            driver_state.add_driving_hours(drivable_hours)
            driver_state.add_miles(segment_distance)
            trip_hours -= drivable_hours
            trip_distance_miles -= segment_distance

            if trip_hours < 0.1:  # Less than 6 minutes
                # Round to zero to exit the loop or ensure minimum segment duration
                trip_hours = 0.0

        return RouteSegmentsData(
            segments=segments,
            end_time=current_time,
            driver_state=driver_state,
            geometry=geometry,
        )
