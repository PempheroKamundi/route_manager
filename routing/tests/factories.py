import datetime

import factory
from factory import fuzzy

from ..driver_state import DriverState
from ..trip_segment_planner import DutyStatus, RouteSegment, SegmentType


class RouteSegmentFactory(factory.Factory):
    class Meta:
        model = RouteSegment

    type = fuzzy.FuzzyChoice(list(SegmentType))
    start_time = factory.LazyFunction(lambda: datetime.datetime.now())
    end_time = factory.LazyFunction(
        lambda: datetime.datetime.now() + datetime.timedelta(hours=1)
    )
    duration_hours = 1.0
    distance_miles = 65.0
    location = "Test Location"
    status = factory.fuzzy.FuzzyChoice(list(DutyStatus))

    @factory.post_generation
    def calculate_duration(obj, create, extracted, **kwargs):
        if create:
            obj.duration_hours = (obj.end_time - obj.start_time).total_seconds() / 3600
            return obj


class DriverStateFactory(factory.Factory):
    """Factory for creating DriverState instances with default values."""

    class Meta:
        model = DriverState

    duty_hours_last_8_days = factory.LazyFunction(lambda: [0.0] * 8)
    current_day_driving_hours = 0.0
    current_day_on_duty_hours = 0.0
    current_on_duty_window_start = None
    accumulative_driving_hours = 0.0
    miles_since_refueling = 0.0
    current_off_duty_hours = 0.0
    last_day_check = None

    @classmethod
    def fresh(cls):
        """Create a completely fresh driver state."""
        return cls()

    @classmethod
    def with_14_hour_window(cls, start_time, elapsed_hours=13.5, driving_hours=10.0):
        """Create a driver state with an active 14-hour window."""
        return cls(
            current_on_duty_window_start=start_time
            - datetime.timedelta(hours=elapsed_hours),
            current_day_driving_hours=driving_hours,
            current_day_on_duty_hours=elapsed_hours,
        )

    @classmethod
    def with_11_hour_limit(cls, start_time, driving_hours=10.5, duty_hours=12.0):
        """Create a driver state near the 11-hour driving limit."""
        return cls(
            current_on_duty_window_start=start_time
            - datetime.timedelta(hours=duty_hours),
            current_day_driving_hours=driving_hours,
            current_day_on_duty_hours=duty_hours,
        )

    @classmethod
    def needs_30min_break(cls, start_time, driving_hours=8.0):
        """Create a driver state that needs a 30-minute break."""
        return cls(
            current_on_duty_window_start=start_time
            - datetime.timedelta(hours=driving_hours),
            current_day_driving_hours=driving_hours,
            current_day_on_duty_hours=driving_hours,
            accumulative_driving_hours=driving_hours,
        )

    @classmethod
    def near_70_hour_limit(cls, start_time, total_hours=69.5, today_hours=4.0):
        """Create a driver state near the 70-hour/8-day limit."""
        state = cls(
            current_on_duty_window_start=start_time
            - datetime.timedelta(hours=today_hours),
            current_day_driving_hours=today_hours,
            current_day_on_duty_hours=today_hours,
        )
        # Set up the duty_hours_last_8_days to match the total
        state.duty_hours_last_8_days[0] = today_hours
        remaining = total_hours - today_hours
        # Distribute remaining hours over previous days
        for i in range(1, 8):
            if remaining <= 0:
                break
            hours_to_add = min(
                remaining, 10.0
            )  # Distribute in chunks of up to 10 hours
            state.duty_hours_last_8_days[i] = hours_to_add
            remaining -= hours_to_add
        return state

    @classmethod
    def needs_refueling(cls, miles=999):
        """Create a driver state that needs refueling."""
        return cls(miles_since_refueling=miles)
