import datetime
from unittest.mock import MagicMock, patch

import pytest

from repository.async_.tests.factory import RouteInformationFactory
from routing.activity_planner import USATripActivityPlannerMixin
from routing.segment_planner.base_segment_planner import (DutyStatus,
                                                          RouteSegmentsData,
                                                          SegmentType)
from routing.tests.factory import DriverStateFactory


# Enum value mock for PICKUP_DROP_OFF_TIME
class MockPickupDropOffTime:
    value = 1.5  # 1.5 hours for pickup/drop-off activities


# Mock for HOSInterstateRule
class MockHOSInterstateRule:
    PICKUP_DROP_OFF_TIME = MockPickupDropOffTime()


# Test class
class TestUSATripActivityPlannerMixin:

    @pytest.fixture
    def activity_planner(self):
        return USATripActivityPlannerMixin()

    @pytest.fixture
    def driver_state(self):
        # Create a driver state with mocked methods
        driver_state = DriverStateFactory()
        # Add mocks for the methods we want to assert on
        driver_state.check_day_change = MagicMock()
        driver_state.add_on_duty_hours = MagicMock()
        return driver_state

    @pytest.fixture
    def route_information(self):
        return RouteInformationFactory()

    @pytest.fixture
    def current_time(self):
        return datetime.datetime(2023, 1, 15, 10, 0, 0)  # 10:00 AM on Jan 15, 2023

    def test_handle_pickup(
        self, activity_planner, driver_state, route_information, current_time
    ):
        """Test the handle_pickup method of USATripActivityPlannerMixin."""
        with patch.object(
            USATripActivityPlannerMixin, "_manage_transport_activity"
        ) as mock_manage:
            # Configure the mock
            mock_manage.return_value = RouteSegmentsData(
                segments=[],
                end_time=current_time + datetime.timedelta(hours=1.5),
                driver_state=driver_state,
                geometry=route_information.geometry,
            )

            # Call the method
            result = activity_planner.handle_pickup(
                current_time=current_time,
                driver_state=driver_state,
                hos_rule=MockHOSInterstateRule,
                data=route_information,
                segment_type=SegmentType.PICKUP,
            )

            # Assertions
            mock_manage.assert_called_once_with(
                current_time=current_time,
                driver_state=driver_state,
                hos_rule=MockHOSInterstateRule,
                data=route_information,
                segment_type=SegmentType.PICKUP,
            )
            assert isinstance(result, RouteSegmentsData)
            assert result.end_time == current_time + datetime.timedelta(hours=1.5)

    def test_handle_drop_off(
        self, activity_planner, driver_state, route_information, current_time
    ):
        """Test the handle_drop_off method of USATripActivityPlannerMixin."""
        with patch.object(
            USATripActivityPlannerMixin, "_manage_transport_activity"
        ) as mock_manage:
            # Configure the mock
            mock_manage.return_value = RouteSegmentsData(
                segments=[],
                end_time=current_time + datetime.timedelta(hours=1.5),
                driver_state=driver_state,
                geometry=route_information.geometry,
            )

            # Call the method
            result = activity_planner.handle_drop_off(
                current_time=current_time,
                driver_state=driver_state,
                hos_rule=MockHOSInterstateRule,
                data=route_information,
                segment_type=SegmentType.DROP_OFF,
            )

            # Assertions
            mock_manage.assert_called_once_with(
                current_time=current_time,
                driver_state=driver_state,
                hos_rule=MockHOSInterstateRule,
                data=route_information,
                segment_type=SegmentType.DROP_OFF,
            )
            assert isinstance(result, RouteSegmentsData)
            assert result.end_time == current_time + datetime.timedelta(hours=1.5)

    def test_manage_transport_activity_new_duty_window(
        self, activity_planner, driver_state, route_information, current_time
    ):
        """Test _manage_transport_activity method with a new duty window."""
        # Set up driver_state for a new duty window
        driver_state.current_on_duty_window_start = None

        # Calculate the expected end time
        activity_end_time = current_time + datetime.timedelta(hours=1.5)

        result = USATripActivityPlannerMixin._manage_transport_activity(
            current_time=current_time,
            driver_state=driver_state,
            hos_rule=MockHOSInterstateRule,
            data=route_information,
            segment_type=SegmentType.PICKUP,
        )

        # Assertions for method calls
        from unittest.mock import call

        expected_calls_check_day_change = [call(current_time), call(activity_end_time)]
        # Verify check_day_change was called correctly
        driver_state.check_day_change.assert_has_calls(expected_calls_check_day_change)

        # Verify add_on_duty_hours was called correctly
        driver_state.add_on_duty_hours.assert_called_once_with(
            MockHOSInterstateRule.PICKUP_DROP_OFF_TIME.value
        )

        # Verify segments
        assert len(result.segments) == 1
        segment = result.segments[0]
        assert segment.type == SegmentType.PICKUP
        assert segment.start_time == current_time
        assert segment.end_time == activity_end_time
        assert segment.duration_hours == 1.5
        assert segment.distance_miles == 0
        assert segment.status == DutyStatus.ON_DUTY_NOT_DRIVING

        # Verify the end time is correct
        assert result.end_time == activity_end_time

        # Verify driver state was updated correctly
        assert result.driver_state == driver_state

    def test_manage_transport_activity_existing_duty_window(
        self, activity_planner, driver_state, route_information, current_time
    ):
        """Test _manage_transport_activity method with an existing duty window."""
        # Set up driver_state with an existing duty window
        previous_window_start = current_time - datetime.timedelta(hours=2)
        driver_state.current_on_duty_window_start = previous_window_start

        # Calculate the expected end time
        activity_end_time = current_time + datetime.timedelta(hours=1.5)

        result = USATripActivityPlannerMixin._manage_transport_activity(
            current_time=current_time,
            driver_state=driver_state,
            hos_rule=MockHOSInterstateRule,
            data=route_information,
            segment_type=SegmentType.DROP_OFF,
        )

        # Assertions for method calls
        from unittest.mock import call

        expected_calls_check_day_change = [call(current_time), call(activity_end_time)]
        # Verify check_day_change was called correctly
        driver_state.check_day_change.assert_has_calls(expected_calls_check_day_change)

        # Verify add_on_duty_hours was called correctly
        driver_state.add_on_duty_hours.assert_called_once_with(
            MockHOSInterstateRule.PICKUP_DROP_OFF_TIME.value
        )

        # Verify segments
        assert len(result.segments) == 1
        segment = result.segments[0]
        assert segment.type == SegmentType.DROP_OFF
        assert segment.start_time == current_time
        assert segment.end_time == activity_end_time
        assert segment.duration_hours == 1.5
        assert segment.distance_miles == 0
        assert segment.status == DutyStatus.ON_DUTY_NOT_DRIVING

        # Verify the end time is correct
        assert result.end_time == activity_end_time

        # Verify driver state was updated correctly
        assert result.driver_state == driver_state

        # Verify the duty window was preserved
        assert driver_state.current_on_duty_window_start == previous_window_start
