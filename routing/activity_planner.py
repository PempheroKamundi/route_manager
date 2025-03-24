"""
routing.activity_planner.usa_trip_activity_planner
~~~~~~~~~~~~~

Mixin class that provides specialized handling for non-driving activities (pickup and delivery).
"""

import datetime
import logging
from typing import Type

from hos_rules.rules import HOSInterstateRule
from repository.async_.mixins import RouteInformation
from routing.segment_planner.base_segment_planner import (
    DutyStatus,
    RouteSegment,
    RouteSegmentsData,
    SegmentType,
)

from .driver_state import DriverState


class USATripActivityPlannerMixin:

    def handle_pickup(self, *args, **kwargs) -> RouteSegmentsData:
        logging.info("Starting pickup handling")
        return self._manage_transport_activity(*args, **kwargs)

    def handle_drop_off(self, *args, **kwargs) -> RouteSegmentsData:
        """Handle drop-off activity with full HOS compliance."""
        logging.info("Starting drop-off handling")
        return self._manage_transport_activity(*args, **kwargs)

    @staticmethod
    def _manage_transport_activity(
        current_time: datetime.datetime,
        driver_state: DriverState,
        hos_rule: Type[HOSInterstateRule],
        data: RouteInformation,
        segment_type: SegmentType,
    ) -> RouteSegmentsData:
        segments = []
        processing_time = current_time

        logging.info(
            "Managing transport activity at %s. Driver state: total_duty_hours_last_8_days=%s",
            current_time,
            driver_state.total_duty_hours_last_8_days,
        )

        # Check for day changes
        driver_state.check_day_change(processing_time)
        logging.debug("Checked for day change at time %s", processing_time)

        # Since this is a non-driving activity (pickup/drop-off), it can be performed
        # even if the driver has reached the 70-hour limit.
        # No need to check cycle limits for non-driving activities.

        # Now we can proceed with the drop-off/pickup activity
        activity_end_time = processing_time + datetime.timedelta(
            hours=hos_rule.PICKUP_DROP_OFF_TIME.value
        )

        logging.info(
            "Processing transport activity from %s to %s (%s hours)",
            processing_time,
            activity_end_time,
            hos_rule.PICKUP_DROP_OFF_TIME.value,
        )

        # Update driver state for this on-duty, not driving activity
        driver_state.add_on_duty_hours(hos_rule.PICKUP_DROP_OFF_TIME.value)
        logging.info(
            "Added %s on-duty hours to driver state",
            hos_rule.PICKUP_DROP_OFF_TIME.value,
        )

        # If we're starting a new duty period, initialize the window
        if driver_state.current_on_duty_window_start is None:
            driver_state.current_on_duty_window_start = processing_time
            logging.info("Started new on-duty window at %s", processing_time)
        else:
            logging.debug(
                "Continuing existing on-duty window that started at %s",
                driver_state.current_on_duty_window_start,
            )

        segments.append(
            RouteSegment(
                type=segment_type,
                start_time=processing_time,
                end_time=activity_end_time,
                duration_hours=hos_rule.PICKUP_DROP_OFF_TIME.value,
                distance_miles=0,
                location="Activity",
                status=DutyStatus.ON_DUTY_NOT_DRIVING,
            )
        )

        # Final check for day changes at end of activity
        driver_state.check_day_change(activity_end_time)
        logging.debug(
            "Checked for day change at end of activity at time %s", activity_end_time
        )

        logging.debug(
            "Final driver state: total_duty_hours_last_8_days=%s, on_duty_window_start=%s",
            driver_state.total_duty_hours_last_8_days,
            driver_state.current_on_duty_window_start,
        )

        logging.info("Completed transport activity, created %s segments", len(segments))

        return RouteSegmentsData(
            segments=segments,
            end_time=activity_end_time,
            driver_state=driver_state,
            geometry=data.geometry,
        )
