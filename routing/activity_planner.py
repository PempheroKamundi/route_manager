import datetime
from typing import Type

from hos_rules.rules import HOSInterstateRule
from routing.driver_state import DriverState

from .trip_segment_planner import (
    DutyStatus,
    RouteSegment,
    RouteSegmentsData,
    SegmentType,
)


class TripActivityPlannerMixin:

    def handle_pickup(self, *args, **kwargs) -> RouteSegmentsData:
        return self._manage_transport_activity(*args, **kwargs)

    def handle_drop_off(self, *args, **kwargs) -> RouteSegmentsData:
        """Handle drop-off activity with full HOS compliance."""
        return self._manage_transport_activity(*args, **kwargs)

    @staticmethod
    def _manage_transport_activity(
        current_time: datetime.datetime,
        driver_state: DriverState,
        hos_rule: Type[HOSInterstateRule],
    ) -> RouteSegmentsData:
        segments = []
        processing_time = current_time

        # Check for day changes
        driver_state.check_day_change(processing_time)

        # Check if 14-hour window limit would be exceeded
        window_exceeded = False
        if driver_state.current_on_duty_window_start is not None:
            elapsed_window_hours = (
                processing_time - driver_state.current_on_duty_window_start
            ).total_seconds() / 3600

            # If adding drop-off time would exceed window
            if (
                elapsed_window_hours + hos_rule.PICKUP_DROP_OFF_TIME.value
                > hos_rule.MAX_DUTY_HOURS.value
            ):
                window_exceeded = True

        # Check if 70-hour/8-day limit would be exceeded
        cycle_exceeded = (
            driver_state.total_duty_hours_last_8_days
            + hos_rule.PICKUP_DROP_OFF_TIME.value
            > hos_rule.MAX_CYCLE_HOURS.value
        )

        # If either limit would be exceeded, take required rest first
        if window_exceeded or cycle_exceeded:
            rest_end_time = processing_time + datetime.timedelta(
                hours=hos_rule.DAILY_REST_PERIOD_HOURS.value
            )

            segments.append(
                RouteSegment(
                    type=SegmentType.MANDATORY_REST_PERIOD,
                    start_time=processing_time,
                    end_time=rest_end_time,
                    duration_hours=hos_rule.DAILY_REST_PERIOD_HOURS.value,
                    distance_miles=0,
                    location="Rest Location",
                    status=DutyStatus.OFF_DUTY,
                )
            )

            processing_time = rest_end_time
            driver_state.take_10_hour_break()

            # Check for day changes after rest
            driver_state.check_day_change(processing_time)

        # Now we can proceed with the drop-off activity
        drop_off_end_time = processing_time + datetime.timedelta(
            hours=hos_rule.PICKUP_DROP_OFF_TIME.value
        )

        # Update driver state for this on-duty, not driving activity
        driver_state.add_on_duty_hours(hos_rule.PICKUP_DROP_OFF_TIME.value)

        # If we're starting a new duty period, initialize the window
        if driver_state.current_on_duty_window_start is None:
            driver_state.current_on_duty_window_start = processing_time

        segments.append(
            RouteSegment(
                type=SegmentType.DROP_OFF,
                start_time=processing_time,
                end_time=drop_off_end_time,
                duration_hours=hos_rule.PICKUP_DROP_OFF_TIME.value,
                distance_miles=0,
                location="Drop-off Location",
                status=DutyStatus.ON_DUTY_NOT_DRIVING,
            )
        )

        # Final check for day changes at end of activity
        driver_state.check_day_change(drop_off_end_time)
        return RouteSegmentsData(
            segments=segments, end_time=current_time, driver_state=driver_state
        )
