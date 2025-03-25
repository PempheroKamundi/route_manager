from datetime import datetime, timedelta


class TruckerLogService:
    """
    Service class for processing trucker log data and generating formatted daily logs.
    """

    @staticmethod
    def process_trucker_logs(data):
        """
        Process the JSON input data and generate formatted daily logs.

        Args:
            data (dict): JSON data containing segments information

        Returns:
            list: Processed daily logs in the required format
        """
        try:
            # Extract segments directly from the JSON data
            segments = data.get("route_data", [])[0].get("segments", [])
            return TruckerLogService.generate_daily_logs(segments)
        except Exception as e:
            # Log the error
            print(f"Error processing trucker logs: {str(e)}")
            raise ValueError(f"Failed to process trucker logs: {str(e)}")

    @staticmethod
    def convert_status(status):
        """Convert status to the format required in the output"""
        if status == "On Duty (Driving)":
            return "driving"
        elif status == "On Duty (Not Driving)":
            return "onDuty"
        elif status == "Off Duty":
            return "offDuty"
        elif status == "sleeperBerth":
            return "sleeperBerth"

    @staticmethod
    def extract_time(dt_str):
        """Extract hours and minutes from a datetime string"""
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.hour, dt.minute

    @staticmethod
    def generate_daily_logs(segments):
        """Generate the logs for each 24-hour period (midnight to midnight)"""
        # Group segments by date
        daily_segments = {}
        daily_miles = {}
        daily_coords = {}

        for segment in segments:
            start_time = datetime.fromisoformat(
                segment["start_time"].replace("Z", "+00:00")
            )
            end_time = datetime.fromisoformat(
                segment["end_time"].replace("Z", "+00:00")
            )

            # Get dates for the start and end times
            start_date = start_time.date()
            end_date = end_time.date()

            # Initialize storage for each date if not already present
            for date in [start_date, end_date]:
                if date not in daily_segments:
                    daily_segments[date] = []
                if date not in daily_miles:
                    daily_miles[date] = 0
                if date not in daily_coords:
                    daily_coords[date] = {"from": None, "to": None}

            # Set coordinates for the day
            if daily_coords[start_date]["from"] is None:
                daily_coords[start_date]["from"] = segment["start_coordinates"]
            daily_coords[end_date]["to"] = segment["end_coordinates"]

            # Calculate miles for driving segments
            if segment["status"] == "On Duty (Driving)":
                if start_date == end_date:
                    # If the segment is within one day
                    daily_miles[start_date] += segment["distance_miles"]
                else:
                    # Split miles proportionally if segment spans multiple days
                    total_duration = (end_time - start_time).total_seconds()
                    midnight = datetime.combine(
                        start_date + timedelta(days=1), datetime.min.time()
                    ).replace(tzinfo=start_time.tzinfo)

                    # Calculate seconds until midnight
                    seconds_in_start_day = (midnight - start_time).total_seconds()

                    # Proportion of miles in each day
                    miles_in_start_day = (
                        seconds_in_start_day / total_duration
                    ) * segment["distance_miles"]
                    miles_in_end_day = segment["distance_miles"] - miles_in_start_day

                    daily_miles[start_date] += miles_in_start_day
                    daily_miles[end_date] += miles_in_end_day

            # Process the segment for each day it spans
            current_date = start_date
            while current_date <= end_date:
                # Calculate segment start and end times for this day
                day_start = (
                    start_time
                    if current_date == start_date
                    else datetime.combine(current_date, datetime.min.time()).replace(
                        tzinfo=start_time.tzinfo
                    )
                )
                day_end = (
                    end_time
                    if current_date == end_date
                    else datetime.combine(
                        current_date + timedelta(days=1), datetime.min.time()
                    ).replace(tzinfo=start_time.tzinfo)
                )

                # Extract hours and minutes
                start_hour, start_minute = day_start.hour, day_start.minute
                end_hour, end_minute = day_end.hour, day_end.minute

                # Adjust for midnight
                if end_hour == 0 and end_minute == 0:
                    end_hour = 24
                    end_minute = 0

                # Create log entry
                log_entry = {
                    "status": TruckerLogService.convert_status(segment["status"]),
                    "startHour": start_hour,
                    "startMinute": start_minute,
                    "endHour": end_hour,
                    "endMinute": end_minute,
                    "location": segment["location"],
                }

                daily_segments[current_date].append(log_entry)
                current_date += timedelta(days=1)

        # Sort segments and fill gaps
        for date in daily_segments:
            # Sort by start time
            daily_segments[date].sort(key=lambda x: (x["startHour"], x["startMinute"]))

            # Fill gaps with off-duty time
            filled_segments = []
            current_hour = 0
            current_minute = 0

            for segment in daily_segments[date]:
                # Check for gap
                if segment["startHour"] > current_hour or (
                    segment["startHour"] == current_hour
                    and segment["startMinute"] > current_minute
                ):
                    # Add gap segment
                    filled_segments.append(
                        {
                            "status": "offDuty",
                            "startHour": current_hour,
                            "startMinute": current_minute,
                            "endHour": segment["startHour"],
                            "endMinute": segment["startMinute"],
                            "location": "Gap (Off Duty)",
                        }
                    )

                # Add current segment
                filled_segments.append(segment)

                # Update current position
                current_hour = segment["endHour"]
                current_minute = segment["endMinute"]

            # Add final off-duty segment if needed
            if current_hour < 24:
                filled_segments.append(
                    {
                        "status": "offDuty",
                        "startHour": current_hour,
                        "startMinute": current_minute,
                        "endHour": 24,
                        "endMinute": 0,
                        "location": "End of Day (Off Duty)",
                    }
                )

            daily_segments[date] = filled_segments

        # Format into final result
        result = []
        for date in sorted(daily_segments.keys()):
            date_str = date.strftime("%Y-%m-%d")

            # Ensure we have coordinates for the day
            from_coords = daily_coords[date]["from"] or [0, 0]
            to_coords = daily_coords[date]["to"] or from_coords

            # Create the daily log entry
            log_entry = {
                "date": date_str,
                "total_miles_driving": round(daily_miles[date], 2),
                "from": from_coords,
                "to": to_coords,
                "log": daily_segments[date],
            }

            result.append(log_entry)

        return result
