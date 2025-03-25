import datetime

import factory
import pytest

from repository.async_.mixins import RouteGeometry
from repository.async_.tests.factory import RouteGeometryFactory
from routing.segment_planner.base_segment_planner import (
    DutyStatus,
    RouteSegment,
    SegmentType,
)
from routing.trip_summarizer import TripSummaryMixin


class RouteSegmentFactory(factory.Factory):
    """Factory for generating RouteSegment objects."""

    class Meta:
        model = RouteSegment

    type = factory.Iterator(
        [
            SegmentType.DRIVE_TO_PICKUP,
            SegmentType.MANDATORY_REST_PERIOD,
            SegmentType.PICKUP,
            SegmentType.DRIVE_TO_DROP_OFF,
            SegmentType.DROP_OFF,
        ]
    )
    status = factory.LazyAttribute(
        lambda o: (
            DutyStatus.ON_DUTY_DRIVING
            if o.type in [SegmentType.DRIVE_TO_PICKUP, SegmentType.DRIVE_TO_DROP_OFF]
            else (
                DutyStatus.OFF_DUTY
                if o.type
                in [
                    SegmentType.MANDATORY_REST_PERIOD,
                    SegmentType.MANDATORY_DRIVING_BREAK,
                ]
                else DutyStatus.ON_DUTY_NOT_DRIVING
            )
        )
    )
    distance_miles = factory.LazyAttribute(
        lambda o: (
            factory.Faker("pyfloat", min_value=5, max_value=100).evaluate(
                None, None, {}
            )
            if o.type in [SegmentType.DRIVE_TO_PICKUP, SegmentType.DRIVE_TO_DROP_OFF]
            else 0.0
        )
    )
    duration_hours = factory.LazyAttribute(
        lambda o: (
            factory.Faker("pyfloat", min_value=0.5, max_value=1.0).evaluate(
                None, None, {}
            )
            if o.type in [SegmentType.PICKUP, SegmentType.DROP_OFF]
            else (
                factory.Faker("pyfloat", min_value=1.0, max_value=5.0).evaluate(
                    None, None, {}
                )
                if o.type
                in [SegmentType.DRIVE_TO_PICKUP, SegmentType.DRIVE_TO_DROP_OFF]
                else (
                    factory.Faker("pyfloat", min_value=8.0, max_value=10.0).evaluate(
                        None, None, {}
                    )
                    if o.type == SegmentType.MANDATORY_REST_PERIOD
                    else factory.Faker(
                        "pyfloat", min_value=0.5, max_value=1.0
                    ).evaluate(None, None, {})
                )
            )
        )
    )
    start_time = factory.LazyFunction(lambda: datetime.datetime.now())
    end_time = factory.LazyFunction(
        lambda: datetime.datetime.now() + datetime.timedelta(hours=2)
    )
    location = factory.Faker("city")


class TestTripSummaryMixin:
    """Test cases for TripSummaryMixin."""

    @pytest.fixture
    def trip_summary_mixin(self):
        """Fixture to create a TripSummaryMixin instance."""

        class TripSummaryMixinImpl(TripSummaryMixin):
            pass

        return TripSummaryMixinImpl()

    def test_combine_geometries_basic(self, trip_summary_mixin):
        """Test basic geometry combination with non-overlapping coordinates."""
        # Create two geometries with different coordinates
        geometry1 = RouteGeometryFactory(
            coordinates=[(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]
        )
        geometry2 = RouteGeometryFactory(
            coordinates=[(3.0, 3.0), (4.0, 4.0), (5.0, 5.0)]
        )

        # Combine geometries
        combined = trip_summary_mixin.combine_geometries(geometry1, geometry2)

        # Assert the result is a RouteGeometry
        assert isinstance(combined, RouteGeometry)
        assert combined.type == "LineString"

        # Check that coordinates were combined properly
        assert combined.coordinates == [
            (0.0, 0.0),
            (1.0, 1.0),
            (2.0, 2.0),
            (3.0, 3.0),
            (4.0, 4.0),
            (5.0, 5.0),
        ]

    def test_combine_geometries_with_overlap(self, trip_summary_mixin):
        """Test geometry combination with overlapping end/start points."""
        # Create geometries with overlapping connection point
        geometry1 = RouteGeometryFactory(
            coordinates=[(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]
        )
        geometry2 = RouteGeometryFactory(
            coordinates=[(2.0, 2.0), (3.0, 3.0), (4.0, 4.0)]
        )

        # Combine geometries
        combined = trip_summary_mixin.combine_geometries(geometry1, geometry2)

        # Check that the duplicate point was removed
        assert combined.coordinates == [
            (0.0, 0.0),
            (1.0, 1.0),
            (2.0, 2.0),
            (3.0, 3.0),
            (4.0, 4.0),
        ]

        # Ensure we have 5 coordinates (not 6) due to deduplication
        assert len(combined.coordinates) == 5

    def test_combine_geometries_empty_coordinates(self, trip_summary_mixin):
        """Test combining geometries when one has empty coordinates."""
        geometry1 = RouteGeometryFactory(coordinates=[])
        geometry2 = RouteGeometryFactory(
            coordinates=[(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
        )

        combined = trip_summary_mixin.combine_geometries(geometry1, geometry2)

        # Should have all coordinates from geometry2
        assert combined.coordinates == [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]

    def test_combine_geometries_different_types(self, trip_summary_mixin):
        """Test combining geometries with different types."""
        geometry1 = RouteGeometryFactory(
            type="LineString", coordinates=[(0.0, 0.0), (1.0, 1.0)]
        )
        geometry2 = RouteGeometryFactory(
            type="MultiPoint", coordinates=[(2.0, 2.0), (3.0, 3.0)]  # Different type
        )

        combined = trip_summary_mixin.combine_geometries(geometry1, geometry2)

        # Type should be taken from the first geometry
        assert combined.type == "LineString"
        assert combined.coordinates == [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]

    def test_calculate_trip_summary(self, trip_summary_mixin):
        """Test the calculate_trip_summary method with simple segments."""
        # Create test segments
        segments = [
            RouteSegmentFactory(
                type=SegmentType.DRIVE_TO_PICKUP,
                status=DutyStatus.ON_DUTY_DRIVING,
                distance_miles=50.0,
                duration_hours=1.0,
            ),
            RouteSegmentFactory(
                type=SegmentType.MANDATORY_DRIVING_BREAK,
                status=DutyStatus.OFF_DUTY,
                distance_miles=0.0,
                duration_hours=0.5,
            ),
            RouteSegmentFactory(
                type=SegmentType.DRIVE_TO_DROP_OFF,
                status=DutyStatus.ON_DUTY_DRIVING,
                distance_miles=75.0,
                duration_hours=1.5,
            ),
        ]

        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(hours=3)

        # Create test geometries
        to_pickup_geometry = RouteGeometryFactory(coordinates=[(0.0, 0.0), (1.0, 1.0)])
        to_drop_off_geometry = RouteGeometryFactory(
            coordinates=[(1.0, 1.0), (2.0, 2.0)]
        )

        # Calculate trip summary
        route_plan = trip_summary_mixin.calculate_trip_summary(
            segments=segments,
            start_time=start_time,
            end_time=end_time,
            to_pickup_geometry=to_pickup_geometry,
            to_drop_off_geometry=to_drop_off_geometry,
        )

        # Assertions
        assert route_plan.total_distance_miles == 125.0  # 50 + 0 + 75
        assert route_plan.total_duration_hours == 3.0  # 1 + 0.5 + 1.5
        assert route_plan.driving_time == 2.5  # 1 + 1.5
        assert route_plan.resting_time == 0.5  # 0.5

        # Check geometry was combined correctly
        assert len(route_plan.route_geometry.coordinates) == 3  # [(0,0), (1,1), (2,2)]

    def test_calculate_trip_summary_with_nested_segments(self, trip_summary_mixin):
        """Test trip summary calculation with nested segments."""
        # Create nested segments structure
        nested_segments = [
            [
                RouteSegmentFactory(
                    type=SegmentType.DRIVE_TO_PICKUP,
                    status=DutyStatus.ON_DUTY_DRIVING,
                    distance_miles=30.0,
                    duration_hours=0.75,
                ),
                RouteSegmentFactory(
                    type=SegmentType.PICKUP,
                    status=DutyStatus.ON_DUTY_NOT_DRIVING,
                    distance_miles=0.0,
                    duration_hours=1.0,
                ),
            ],
            RouteSegmentFactory(
                type=SegmentType.MANDATORY_DRIVING_BREAK,
                status=DutyStatus.OFF_DUTY,
                distance_miles=0.0,
                duration_hours=0.5,
            ),
            RouteSegmentFactory(
                type=SegmentType.DRIVE_TO_DROP_OFF,
                status=DutyStatus.ON_DUTY_DRIVING,
                distance_miles=60.0,
                duration_hours=1.25,
            ),
        ]

        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(hours=3.5)

        to_pickup_geometry = RouteGeometryFactory()
        to_drop_off_geometry = RouteGeometryFactory()

        # Calculate trip summary
        route_plan = trip_summary_mixin.calculate_trip_summary(
            segments=nested_segments,
            start_time=start_time,
            end_time=end_time,
            to_pickup_geometry=to_pickup_geometry,
            to_drop_off_geometry=to_drop_off_geometry,
        )

        # Assertions
        assert route_plan.total_distance_miles == 90.0  # 30 + 0 + 0 + 60 = 90
        assert route_plan.total_duration_hours == 3.5  # 0.75 + 1.0 + 0.5 + 1.25
        assert route_plan.driving_time == 2.0
        assert route_plan.resting_time == 0.5  # 0.5

        # Check that original structure is preserved
        assert len(route_plan.segments) == 3
        assert isinstance(route_plan.segments[0], list)
        assert len(route_plan.segments[0]) == 2
