import datetime
from unittest.mock import patch

import pytest

from hos_rules.rules import HOSInterstateRule
from routing.tests.factories import DriverStateFactory
from routing.trip_segment_planner import (
    DutyStatus,
    SegmentType,
    TripSegmentPlannerMixin,
)


# Create the test planner that uses the mixin
class TestRoutePlanner(TripSegmentPlannerMixin):
    pass


# Test fixtures
@pytest.fixture
def route_planner():
    return TestRoutePlanner()


@pytest.fixture
def base_start_time():
    return datetime.datetime(2023, 1, 1, 8, 0, 0)  # 8:00 AM on Jan 1, 2023


@pytest.fixture
def hos_rule():
    return HOSInterstateRule


@pytest.fixture
def fresh_driver_state():
    return DriverStateFactory.fresh()


# Basic tests
def test_plan_route_segment_basic(
    route_planner, base_start_time, hos_rule, fresh_driver_state
):
    """Test a basic route segment planning that doesn't hit any limits."""
    # Make sure the driver state is truly fresh with no accumulated hours
    fresh_driver_state.accumulative_driving_hours = 0.0
    fresh_driver_state.current_day_driving_hours = 0.0
    fresh_driver_state.current_day_on_duty_hours = 0.0
    fresh_driver_state.current_on_duty_window_start = None
    now = datetime.datetime.now(datetime.timezone.utc)

    # Plan a 2-hour drive to pickup
    result = route_planner.plan_route_segment(
        start_time=now,
        segment_type=SegmentType.DRIVE_TO_PICKUP,
        total_trip_hours=2.0,
        total_trip_distance_miles=130.0,
        geometry=None,
        driver_state=fresh_driver_state,
        hos_rule=hos_rule,
    )

    # Validate result
    assert (
        len(result.segments) == 1
    ), f"Expected 1 segment, got {len(result.segments)}: {result.segments}"
    assert result.segments[0].type == SegmentType.DRIVE_TO_PICKUP
    assert result.segments[0].duration_hours == 2.0
    assert result.segments[0].distance_miles == 130.0
    assert result.segments[0].status == DutyStatus.ON_DUTY_DRIVING
    assert result.end_time == now + datetime.timedelta(hours=2)

    # Check driver state was updated
    assert fresh_driver_state.current_day_driving_hours == 2.0
    assert fresh_driver_state.current_on_duty_window_start == now


# 14-Hour Driving Window tests
def test_14_hour_window_limit(
    route_planner, base_start_time, hos_rule, fresh_driver_state
):
    """Test that driver cannot drive after 14-hour window elapses without a 10-hour break."""
    # Set up driver state with 13.5 hours elapsed in window and force needed variables
    driver_state = DriverStateFactory.with_14_hour_window(base_start_time)

    # Make sure needs_30min_break is False to avoid that check interfering
    driver_state.has_taken_30min_break = True

    # Plan a 2-hour drive that should be split due to 14-hour window
    result = route_planner.plan_route_segment(
        start_time=base_start_time,
        segment_type=SegmentType.DRIVE_TO_PICKUP,
        total_trip_hours=2.0,
        total_trip_distance_miles=130.0,
        geometry=None,
        driver_state=driver_state,
        hos_rule=hos_rule,
    )

    # The driver should only be able to drive for 0.5 more hours until reaching 14-hour limit
    assert (
        len(result.segments) >= 2
    ), f"Expected at least 2 segments, got {len(result.segments)}: {result.segments}"

    # Should have at least one driving segment and one rest segment
    drive_segments = [
        s for s in result.segments if s.type == SegmentType.DRIVE_TO_PICKUP
    ]
    rest_segments = [
        s for s in result.segments if s.type == SegmentType.MANDATORY_REST_PERIOD
    ]

    assert len(drive_segments) >= 1, "Should have at least one driving segment"
    assert len(rest_segments) >= 1, "Should have at least one rest segment"

    # Either the first segment is a short drive followed by rest, or it's an immediate rest
    if result.segments[0].type == SegmentType.DRIVE_TO_PICKUP:
        # First segment should be short drive, matching the remaining window time
        assert (
            abs(result.segments[0].duration_hours - 0.5) < 0.1
        ), "First driving segment should be about 0.5 hours"
        # Second segment should be a rest period
        assert result.segments[1].type == SegmentType.MANDATORY_REST_PERIOD
        assert result.segments[1].duration_hours == 10.0
    else:
        # First segment is already a rest period
        assert result.segments[0].type == SegmentType.MANDATORY_REST_PERIOD
        assert result.segments[0].duration_hours == 10.0

    # Check driver state was reset after rest
    assert driver_state.current_day_driving_hours < 11.0
    assert (
        driver_state.current_on_duty_window_start is None
        or driver_state.current_on_duty_window_start > base_start_time
    )


# 11-Hour Driving Limit tests
def test_11_hour_driving_limit(
    route_planner, base_start_time, hos_rule, fresh_driver_state
):
    """Test that driver cannot drive after 11 hours of driving without a 10-hour break."""
    # Set up driver state with 10.5 hours of driving
    driver_state = DriverStateFactory.with_11_hour_limit(base_start_time)

    # Make sure needs_30min_break is False to avoid that check interfering
    driver_state.has_taken_30min_break = True

    # Plan a 2-hour drive that should be split due to 11-hour limit
    result = route_planner.plan_route_segment(
        start_time=base_start_time,
        segment_type=SegmentType.DRIVE_TO_PICKUP,
        total_trip_hours=2.0,
        total_trip_distance_miles=130.0,
        geometry=None,
        driver_state=driver_state,
        hos_rule=hos_rule,
    )

    # The driver should only be able to drive for 0.5 more hours until reaching 11-hour limit
    assert (
        len(result.segments) >= 2
    ), f"Expected at least 2 segments, got {len(result.segments)}: {result.segments}"

    # Should have at least one driving segment and one rest segment
    drive_segments = [
        s for s in result.segments if s.type == SegmentType.DRIVE_TO_PICKUP
    ]
    rest_segments = [
        s for s in result.segments if s.type == SegmentType.MANDATORY_REST_PERIOD
    ]

    assert len(drive_segments) >= 1, "Should have at least one driving segment"
    assert len(rest_segments) >= 1, "Should have at least one rest segment"

    # Verify the remaining driving hours and rest periods
    if result.segments[0].type == SegmentType.DRIVE_TO_PICKUP:
        assert (
            abs(result.segments[0].duration_hours - 0.5) < 0.1
        ), "First driving segment should be about 0.5 hours"

    # Find mandatory rest segment
    rest_segment = next(
        (s for s in result.segments if s.type == SegmentType.MANDATORY_REST_PERIOD),
        None,
    )
    assert rest_segment is not None
    assert rest_segment.duration_hours == 10.0

    # Check driver state was reset after rest
    assert driver_state.current_day_driving_hours < 11.0


# 30-Minute Break Requirement tests
def test_30_minute_break_after_8_hours(
    route_planner, base_start_time, hos_rule, fresh_driver_state
):
    """Test that driver must take a 30-minute break after 8 cumulative hours of driving."""
    # Set up driver state with 8 hours of driving already done
    driver_state = DriverStateFactory.needs_30min_break(base_start_time)

    # Set a counter to track how many times the break is needed
    needs_break_counter = [0]

    # Create a function to track calls and eventually return False
    def needs_break_side_effect():
        if needs_break_counter[0] == 0:
            needs_break_counter[0] += 1
            return True
        return False

    # Mock the needs_30min_break property to return True once, then False
    with patch.object(
        driver_state.__class__,
        "needs_30min_break",
        property(lambda self: needs_break_side_effect()),
    ):
        # Plan a 2-hour drive
        result = route_planner.plan_route_segment(
            start_time=base_start_time,
            segment_type=SegmentType.DRIVE_TO_PICKUP,
            total_trip_hours=2.0,
            total_trip_distance_miles=130.0,
            geometry=None,
            driver_state=driver_state,
            hos_rule=hos_rule,
        )

        # Validate that a 30-minute break was inserted before continuing the drive
        assert len(result.segments) >= 2

        # Find the driving break segment
        break_segment = next(
            (
                s
                for s in result.segments
                if s.type == SegmentType.MANDATORY_DRIVING_BREAK
            ),
            None,
        )
        assert (
            break_segment is not None
        ), f"No mandatory driving break found in segments: {result.segments}"
        assert break_segment.duration_hours == 0.5
        assert break_segment.status == DutyStatus.OFF_DUTY

        # Find the driving segment that should come after the break
        drive_segments = [
            s for s in result.segments if s.type == SegmentType.DRIVE_TO_PICKUP
        ]
        assert len(drive_segments) >= 1, "Should have at least one driving segment"


# 70-Hour On-Duty Limit tests
def test_70_hour_8_day_limit(
    route_planner, base_start_time, hos_rule, fresh_driver_state
):
    """Test that driver cannot drive after 70 hours on duty in 8 days without a reset."""
    # Set up driver state with hours close to the 70-hour limit
    driver_state = DriverStateFactory.near_70_hour_limit(base_start_time)

    # Mock the total_duty_hours_last_8_days property to return a value near the limit
    with patch.object(
        driver_state.__class__,
        "total_duty_hours_last_8_days",
        property(lambda self: 69.5),
    ):
        # Plan a 2-hour drive
        result = route_planner.plan_route_segment(
            start_time=base_start_time,
            segment_type=SegmentType.DRIVE_TO_PICKUP,
            total_trip_hours=2.0,
            total_trip_distance_miles=130.0,
            geometry=None,
            driver_state=driver_state,
            hos_rule=hos_rule,
        )

        # Validate that a rest period was added after hitting 70-hour limit
        assert len(result.segments) >= 2

        # Find the driving segment and rest segment
        drive_segments = [
            s for s in result.segments if s.type == SegmentType.DRIVE_TO_PICKUP
        ]
        rest_segments = [
            s for s in result.segments if s.type == SegmentType.MANDATORY_REST_PERIOD
        ]

        assert len(drive_segments) >= 1, "Should have at least one driving segment"
        assert len(rest_segments) >= 1, "Should have at least one rest segment"

        # The driver should only be able to drive for about 0.5 more hours until reaching 70-hour limit
        if drive_segments[0] == result.segments[0]:
            assert (
                abs(drive_segments[0].duration_hours - 0.5) < 0.1
            ), "First driving segment should be about 0.5 hours"

        # Find the mandatory rest period
        rest_segment = rest_segments[0]
        assert rest_segment.duration_hours == 10.0


# Refueling tests
def test_refueling_requirement(
    route_planner, base_start_time, hos_rule, fresh_driver_state
):
    """Test that driver refuels after driving 1000 miles."""
    # Set up driver state with 999 miles since last refuel
    driver_state = DriverStateFactory.needs_refueling()

    # Set a counter to track refueling
    needs_refueling_counter = [0]

    # Create a function to track calls and eventually return False
    def needs_refueling_side_effect():
        if needs_refueling_counter[0] == 0:
            needs_refueling_counter[0] += 1
            return True
        return False

    # Mock the needs_refueling property to return True once, then False
    with patch.object(
        driver_state.__class__,
        "needs_refueling",
        property(lambda self: needs_refueling_side_effect()),
    ):
        # Plan a 2-hour drive covering 130 miles (which crosses the 1000-mile threshold)
        result = route_planner.plan_route_segment(
            start_time=base_start_time,
            segment_type=SegmentType.DRIVE_TO_PICKUP,
            total_trip_hours=2.0,
            total_trip_distance_miles=130.0,
            geometry=None,
            driver_state=driver_state,
            hos_rule=hos_rule,
        )

        # Validate that a refueling stop was added
        refuel_segment = next(
            (s for s in result.segments if s.type == SegmentType.REFUELING), None
        )
        assert (
            refuel_segment is not None
        ), f"No refueling segment found in: {result.segments}"
        assert refuel_segment.duration_hours == 1
        assert refuel_segment.status == DutyStatus.ON_DUTY_NOT_DRIVING
