import datetime

import pytest
from freezegun import freeze_time

from routing.tests.factories import DriverStateFactory


@pytest.fixture
def fresh_driver():
    """Fixture providing a fresh driver state."""
    return DriverStateFactory()


class TestDrivingAndDutyHours:
    """Tests for driving and on-duty hour tracking."""

    def test_add_driving_hours(self, fresh_driver):
        """Test that adding driving hours updates all relevant counters."""
        fresh_driver.add_driving_hours(4.0)

        assert fresh_driver.current_day_driving_hours == 4.0
        assert fresh_driver.current_day_on_duty_hours == 4.0
        assert fresh_driver.accumulative_driving_hours == 4.0
        assert fresh_driver.duty_hours_last_8_days[0] == 4.0

    def test_add_on_duty_hours(self, fresh_driver):
        """Test that adding on-duty hours updates only on-duty counters."""
        fresh_driver.add_on_duty_hours(2.0)

        assert fresh_driver.current_day_driving_hours == 0.0  # Unchanged
        assert fresh_driver.current_day_on_duty_hours == 2.0
        assert fresh_driver.accumulative_driving_hours == 0.0  # Unchanged
        assert fresh_driver.duty_hours_last_8_days[0] == 2.0

    def test_combined_hours(self, fresh_driver):
        """Test combination of driving and on-duty hours."""
        fresh_driver.add_driving_hours(5.0)
        fresh_driver.add_on_duty_hours(2.0)

        assert fresh_driver.current_day_driving_hours == 5.0
        assert fresh_driver.current_day_on_duty_hours == 7.0
        assert fresh_driver.accumulative_driving_hours == 5.0
        assert fresh_driver.duty_hours_last_8_days[0] == 7.0


class Test14HourDrivingWindow:
    """Tests for the 14-hour driving window regulation."""

    @freeze_time("2023-01-01 08:00:00", tz_offset=0)
    def test_available_hours_within_14_hour_window(self, fresh_driver):
        """Test available hours calculation within the 14-hour window."""
        # Set window start at 8:00 AM
        driver = fresh_driver
        driver.current_on_duty_window_start = datetime.datetime.now(
            datetime.timezone.utc
        )

        # Still at 8:00 AM, full hours available
        assert driver.available_driving_hours == min(14.0, 11.0, 70.0)

        # Advance time by 6 hours to 2:00 PM
        with freeze_time("2023-01-01 14:00:00", tz_offset=0):
            # 14 - 6 = 8 hours left in window
            assert driver.available_driving_hours == min(8.0, 11.0, 70.0)

        # Advance time by 12 hours to 8:00 PM
        with freeze_time("2023-01-01 20:00:00", tz_offset=0):
            # 14 - 12 = 2 hours left in window
            assert driver.available_driving_hours == min(2.0, 11.0, 70.0)

        # Advance time by 14 hours to 10:00 PM (window closed)
        with freeze_time("2023-01-01 22:00:00", tz_offset=0):
            # 14 - 14 = 0 hours left in window
            assert driver.available_driving_hours == 0.0

    @freeze_time("2023-01-01 08:00:00", tz_offset=0)
    def test_14_hour_window_reset_after_10_hour_break(self, fresh_driver):
        """Test that 10-hour break resets the 14-hour window."""
        # Set window start at 8:00 AM
        driver = fresh_driver
        driver.current_on_duty_window_start = datetime.datetime.now(
            datetime.timezone.utc
        )

        # Advance time by 13 hours to 9:00 PM
        with freeze_time("2023-01-01 21:00:00", tz_offset=0):
            assert driver.available_driving_hours == 1.0  # 1 hour left (14 - 13 = 1)

        # Take 10-hour break
        driver.take_10_hour_break()

        # After break, window should reset
        assert driver.current_on_duty_window_start is None

        # Start a new window at 7:00 AM the next day
        with freeze_time("2023-01-02 07:00:00", tz_offset=0):
            driver.current_on_duty_window_start = datetime.datetime.now(
                datetime.timezone.utc
            )
            assert driver.available_driving_hours == min(
                14.0, 11.0, 70.0
            )  # Full window again


class Test11HourDrivingLimit:
    """Tests for the 11-hour driving limit regulation."""

    def test_available_driving_hours_with_11_hour_limit(self, fresh_driver):
        """Test available hours calculation with 11-hour driving limit."""
        driver = fresh_driver
        driver.current_on_duty_window_start = datetime.datetime.now(
            datetime.timezone.utc
        )

        # Add 4 hours of driving
        driver.add_driving_hours(4.0)
        assert driver.available_driving_hours == min(7.0, 14.0, 70.0)  # 11 - 4 = 7

        # Add 3 more hours
        driver.add_driving_hours(3.0)
        assert driver.available_driving_hours == min(
            4.0, 14.0 - (7 / 24), 70.0 - 7
        )  # 11 - 7 = 4

        # Add 4 more hours (exceeding limit)
        driver.add_driving_hours(4.0)
        assert driver.available_driving_hours == 0.0  # 11 - 11 = 0

    def test_11_hour_limit_reset_after_10_hour_break(self, fresh_driver):
        """Test that 10-hour break resets the 11-hour driving limit."""
        driver = fresh_driver
        driver.current_on_duty_window_start = datetime.datetime.now(
            datetime.timezone.utc
        )

        # Add 10 hours of driving
        driver.add_driving_hours(10.0)
        assert driver.available_driving_hours == 1.0  # 11 - 10 = 1

        # Take 10-hour break
        driver.take_10_hour_break()

        # After break, limit should reset
        assert driver.current_day_driving_hours == 0.0

        # Start a new window
        driver.current_on_duty_window_start = datetime.datetime.now(
            datetime.timezone.utc
        )
        assert driver.available_driving_hours == min(
            11.0, 14.0, 70.0 - 10
        )  # Full driving hours again


class Test30MinuteBreakRequirement:
    """Tests for the 30-minute break requirement."""

    def test_needs_30min_break_after_8_hours(self, fresh_driver):
        """Test that 30-min break is needed after 8 cumulative hours of driving."""
        driver = fresh_driver

        # Drive for 7.9 hours
        driver.add_driving_hours(7.9)
        assert not driver.needs_30min_break

        # Drive for another 0.1 hours (total 8.0)
        driver.add_driving_hours(0.1)
        assert driver.needs_30min_break

    def test_30min_break_resets_accumulative_driving(self, fresh_driver):
        """Test that taking a 30-min break resets the accumulative driving counter."""
        driver = fresh_driver

        # Drive for 8 hours
        driver.add_driving_hours(8.0)
        assert driver.needs_30min_break

        # Take 30-min break
        driver.add_30_min_break()
        assert not driver.needs_30min_break

        # Drive for 7.9 more hours
        driver.add_driving_hours(7.9)
        assert not driver.needs_30min_break

    def test_10_hour_break_satisfies_30min_requirement(self, fresh_driver):
        """Test that a 10-hour break also satisfies the 30-min break requirement."""
        driver = fresh_driver

        # Drive for 8 hours
        driver.add_driving_hours(8.0)
        assert driver.needs_30min_break

        # Take 10-hour break
        driver.take_10_hour_break()
        assert not driver.needs_30min_break
        assert driver.accumulative_driving_hours == 0.0


class Test70Hour8DayLimit:
    """Tests for the 70-hour in 8 consecutive days limit."""

    def test_total_duty_hours_calculation(self, fresh_driver):
        """Test that total duty hours are correctly calculated."""
        driver = fresh_driver

        # Set hours for 8 days
        driver.duty_hours_last_8_days = [10.0, 9.0, 8.0, 10.0, 11.0, 9.0, 8.0, 5.0]
        assert driver.total_duty_hours_last_8_days == 70.0

    def test_available_hours_with_70_hour_limit(self, fresh_driver):
        """Test available hours calculation with 70-hour limit."""
        driver = fresh_driver
        driver.current_on_duty_window_start = datetime.datetime.now(
            datetime.timezone.utc
        )

        # Set 65 hours already used
        driver.duty_hours_last_8_days = [5.0, 10.0, 8.0, 9.0, 11.0, 9.0, 8.0, 5.0]
        assert driver.total_duty_hours_last_8_days == 65.0

        # Available hours should be limited by 70-hour rule
        assert driver.available_driving_hours == min(5.0, 11.0, 14.0)  # 70 - 65 = 5

        # Add 5 more hours (reaching limit)
        driver.add_driving_hours(5.0)
        assert driver.available_driving_hours == 0.0  # 70 - 70 = 0

    def test_rolling_8_day_window(self, fresh_driver):
        """Test that the 8-day window rolls properly."""
        driver = fresh_driver

        # Set initial state with 70 hours
        driver.duty_hours_last_8_days = [10.0, 9.0, 8.0, 10.0, 11.0, 9.0, 8.0, 5.0]
        assert driver.total_duty_hours_last_8_days == 70.0

        # Start a new day (oldest day drops off)
        driver.start_new_day()
        # New state: [0.0, 10.0, 9.0, 8.0, 10.0, 11.0, 9.0, 8.0]
        assert driver.duty_hours_last_8_days[0] == 0.0
        assert driver.duty_hours_last_8_days[7] == 8.0
        assert driver.total_duty_hours_last_8_days == 65.0  # 70 - 5 = 65

        # Work 5 hours on new day
        driver.add_driving_hours(5.0)
        # New state: [5.0, 10.0, 9.0, 8.0, 10.0, 11.0, 9.0, 8.0]
        assert driver.total_duty_hours_last_8_days == 70.0

        # Start another new day
        driver.start_new_day()
        # New state: [0.0, 5.0, 10.0, 9.0, 8.0, 10.0, 11.0, 9.0]
        assert driver.total_duty_hours_last_8_days == 62.0  # 70 - 8 = 62


class TestDayChangeAndMileage:
    """Tests for day change detection and mileage tracking."""

    def test_check_day_change(self, fresh_driver):
        """Test detection of day change."""
        driver = fresh_driver

        # Set initial day
        initial_time = datetime.datetime(2023, 1, 1, 12, 0, 0)
        driver.check_day_change(initial_time)
        assert driver.last_day_check == initial_time.date()

        # Set hours worked
        driver.add_driving_hours(6.0)
        assert driver.current_day_driving_hours == 6.0

        # Check same day - no change
        same_day = datetime.datetime(2023, 1, 1, 18, 0, 0)
        driver.check_day_change(same_day)
        assert driver.current_day_driving_hours == 6.0  # Unchanged

        # Check next day - should reset daily counters
        next_day = datetime.datetime(2023, 1, 2, 8, 0, 0)
        driver.check_day_change(next_day)
        assert driver.last_day_check == next_day.date()
        assert driver.current_day_driving_hours == 0.0  # Reset
        assert driver.duty_hours_last_8_days[0] == 0.0  # New day
        assert driver.duty_hours_last_8_days[1] == 6.0  # Previous day

    def test_mileage_tracking(self, fresh_driver):
        """Test tracking of miles driven and refueling."""
        driver = fresh_driver

        # Add miles
        driver.add_miles(400.0)
        assert driver.miles_since_refueling == 400.0

        # Add more miles
        driver.add_miles(300.0)
        assert driver.miles_since_refueling == 700.0

        # Refuel
        driver.refuel()
        assert driver.miles_since_refueling == 0.0

        # Add miles after refueling
        driver.add_miles(500.0)
        assert driver.miles_since_refueling == 500.0

    def test_needs_refueling(self, fresh_driver):
        """Test detection of refueling need."""
        driver = fresh_driver

        # Add 900 miles
        driver.add_miles(900.0)
        assert not driver.needs_refueling

        # Add 100 more miles (total 1000)
        driver.add_miles(100.0)
        assert driver.needs_refueling

        # Refuel
        driver.refuel()
        assert not driver.needs_refueling


class TestPickupAndDropoff:
    """Tests for pickup and drop-off time assumptions."""

    def test_pickup_and_dropoff_hours(self, fresh_driver):
        """Test 1-hour assumption for pickup and drop-off."""
        driver = fresh_driver
        driver.current_on_duty_window_start = datetime.datetime.now(
            datetime.timezone.utc
        )

        # Add 1 hour for pickup (on-duty, not driving)
        driver.add_on_duty_hours(1.0)
        assert driver.current_day_driving_hours == 0.0
        assert driver.current_day_on_duty_hours == 1.0

        # Drive for 5 hours
        driver.add_driving_hours(5.0)
        assert driver.current_day_driving_hours == 5.0
        assert driver.current_day_on_duty_hours == 6.0

        # Add 1 hour for drop-off (on-duty, not driving)
        driver.add_on_duty_hours(1.0)
        assert driver.current_day_driving_hours == 5.0
        assert driver.current_day_on_duty_hours == 7.0

        # Verify impact on available hours
        # 11-hour driving limit: 11 - 5 = 6
        # 14-hour window: impacted by 7 hours total
        # 70-hour limit: 70 - 7 = 63
        assert driver.available_driving_hours == min(6.0, 14.0 - (7 / 24), 63.0)


class TestComprehensiveScenarios:
    """Tests for comprehensive real-world scenarios."""

    def test_full_day_with_breaks_scenario(self, fresh_driver):
        """Test a full day scenario with driving, breaks, and on-duty time."""
        driver = fresh_driver

        # 6:00 AM: Start day and duty window
        start_time = datetime.datetime(
            2023, 1, 1, 6, 0, 0, tzinfo=datetime.timezone.utc
        )
        driver.current_on_duty_window_start = start_time
        driver.check_day_change(start_time)

        # 6:00-7:00 AM: Pickup (2 hour on-duty, not driving)
        driver.add_on_duty_hours(2.0)

        # 7:00-11:00 AM: Driving (4 hours)
        driver.add_driving_hours(4.0)

        # 11:30 AM-3:30 PM: Driving (4 hours)
        driver.add_driving_hours(4.0)

        # 3:30-4:00 PM: Required 30-minute break (after 8 hours driving)
        assert driver.needs_30min_break
        driver.add_30_min_break()

        # 4:00-7:00 PM: Driving (3 hours, reaching 11-hour limit)
        driver.add_driving_hours(3.0)

        # 7:00-8:00 PM: Drop-off (1 hour on-duty, not driving)
        driver.add_on_duty_hours(1.0)

        # Verify final state
        assert driver.current_day_driving_hours == 11.0  # Reached limit
        assert (
            driver.current_day_on_duty_hours == 14.0
        )  # 11 driving + 2 on-duty + 1 hour breaks
        assert driver.available_driving_hours == 0.0  # No more driving allowed
        assert driver.total_duty_hours_last_8_days == 14.0

        # Taking 10-hour break
        driver.take_10_hour_break()

        # Next day (after break)
        next_day = datetime.datetime(2023, 1, 2, 6, 0, 0, tzinfo=datetime.timezone.utc)
        driver.check_day_change(next_day)
        driver.current_on_duty_window_start = next_day

        # Verify reset state
        # Next day (after break)
        with freeze_time("2023-01-02 06:00:00", tz_offset=0):
            next_day = datetime.datetime.now(datetime.timezone.utc)
            driver.check_day_change(next_day)
            driver.current_on_duty_window_start = next_day

            # Verify reset state
            assert driver.current_day_driving_hours == 0.0
            assert driver.current_day_on_duty_hours == 0.0
            assert driver.available_driving_hours == min(
                11.0, 14.0, 70.0 - 14.0
            )  # Full driving hours

    def test_multiple_day_70hour_scenario(self, fresh_driver):
        """Test a scenario reaching the 70-hour limit over multiple days."""
        driver = fresh_driver

        # Simulate 7 days of driving with varying hours
        day1 = datetime.datetime(2023, 1, 1, 6, 0, 0)
        driver.check_day_change(day1)
        driver.current_on_duty_window_start = day1
        driver.add_driving_hours(8.0)
        driver.add_on_duty_hours(2.0)  # Day 1: 10 hours

        day2 = datetime.datetime(2023, 1, 2, 6, 0, 0)
        driver.check_day_change(day2)
        driver.current_on_duty_window_start = day2
        driver.add_driving_hours(9.0)
        driver.add_on_duty_hours(2.0)  # Day 2: 11 hours

        day3 = datetime.datetime(2023, 1, 3, 6, 0, 0)
        driver.check_day_change(day3)
        driver.current_on_duty_window_start = day3
        driver.add_driving_hours(8.0)
        driver.add_on_duty_hours(1.0)  # Day 3: 9 hours

        day4 = datetime.datetime(2023, 1, 4, 6, 0, 0)
        driver.check_day_change(day4)
        driver.current_on_duty_window_start = day4
        driver.add_driving_hours(10.0)
        driver.add_on_duty_hours(1.0)  # Day 4: 11 hours

        day5 = datetime.datetime(2023, 1, 5, 6, 0, 0)
        driver.check_day_change(day5)
        driver.current_on_duty_window_start = day5
        driver.add_driving_hours(9.0)
        driver.add_on_duty_hours(1.0)  # Day 5: 10 hours

        day6 = datetime.datetime(2023, 1, 6, 6, 0, 0)
        driver.check_day_change(day6)
        driver.current_on_duty_window_start = day6
        driver.add_driving_hours(7.0)
        driver.add_on_duty_hours(2.0)  # Day 6: 9 hours

        day7 = datetime.datetime(2023, 1, 7, 6, 0, 0)
        driver.check_day_change(day7)
        driver.current_on_duty_window_start = day7
        driver.add_driving_hours(8.0)
        driver.add_on_duty_hours(1.0)  # Day 7: 9 hours

        with freeze_time(
            "2023-01-07 15:00:00", tz_offset=0
        ):  # Same day as day7, just later
            # Total: 10 + 11 + 9 + 11 + 10 + 9 + 9 = 69 hours
            assert driver.total_duty_hours_last_8_days == 69.0
            assert driver.available_driving_hours == min(
                1.0, 11.0 - 8.0, 14.0 - 9.0
            )  # 1 hour left

        # Day 8 - add 1 more hour to reach limit
        day8 = datetime.datetime(2023, 1, 8, 6, 0, 0)
        driver.check_day_change(day8)
        driver.current_on_duty_window_start = day8
        driver.add_driving_hours(1.0)

        # Total: 11 + 9 + 11 + 10 + 9 + 9 + 1 = 70 hours (day 1 dropped off)
        assert driver.total_duty_hours_last_8_days == 70.0
        assert driver.available_driving_hours == 0.0  # Reached limit

        # Day 9 - day 1 drops off, freeing up 11 hours
        day9 = datetime.datetime(2023, 1, 9, 6, 0, 0)
        driver.check_day_change(day9)
        driver.current_on_duty_window_start = day9

        # Total after day 9: 11 + 9 + 11 + 10 + 9 + 9 + 1 + 0 = 60 hours (only day 1 dropped off)
        assert driver.total_duty_hours_last_8_days == 60.0
