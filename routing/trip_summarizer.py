import datetime
import logging
from dataclasses import dataclass
from typing import Any, List

import pandas as pd

from repository.async_.mixins import RouteGeometry
from routing.segment_planner.base_segment_planner import RouteSegment

logger = logging.getLogger(__name__)


@dataclass
class RoutePlan:
    segments: List[RouteSegment]
    total_distance_miles: float
    total_duration_hours: float
    start_time: datetime.datetime
    end_time: datetime.datetime
    route_geometry: RouteGeometry
    driving_time: datetime.datetime
    resting_time: datetime.datetime

    def to_dict(self):
        """
        Serializes the RoutePlan object to a dictionary.

        Returns:
            dict: Dictionary representation of the RoutePlan with all nested objects
                 properly serialized for JSON conversion. Nested segment lists are flattened
                 while maintaining chronological order.
        """
        # Flatten segments while preserving order
        serialized_segments = []
        for item in self.segments:
            if isinstance(item, list):
                # Flatten nested list of segments
                for segment in item:
                    serialized_segments.append(segment.to_dict())
            else:
                # Handle individual segment
                serialized_segments.append(item.to_dict())

        return {
            "segments": serialized_segments,
            "total_distance_miles": float(self.total_distance_miles),
            "total_duration_hours": float(self.total_duration_hours),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "route_geometry": self.route_geometry.model_dump_json(),
            "driving_time": self.driving_time,
            "resting_time": self.resting_time,
        }


class TripSummaryMixin:
    """Mixin that provides trip summary using pandas for efficient data processing."""

    def calculate_trip_summary(
        self,
        segments: List[RouteSegment],
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        to_pickup_geometry: Any,
        to_drop_off_geometry: Any,
    ) -> RoutePlan:

        # Flatten segments list in case there are nested lists
        flat_segments = []
        for item in segments:
            if isinstance(item, list):
                flat_segments.extend(item)
            else:
                flat_segments.append(item)

        # Convert segments to pandas DataFrame for efficient operations
        segments_data = []
        for segment in flat_segments:
            segments_data.append(segment.to_dict())

        df = pd.DataFrame(segments_data)

        # Calculate total distance and duration
        total_distance = df["distance_miles"].sum()
        total_duration = df["duration_hours"].sum()

        # Additional analytics if needed
        # Can be useful for other metrics
        driving_time = df[df["status"].str.contains("Driving")]["duration_hours"].sum()
        rest_time = df[df["status"] == "Off Duty"]["duration_hours"].sum()

        # Combine route geometries for full trip visualization
        combined_geometry = self.combine_geometries(
            to_pickup_geometry, to_drop_off_geometry
        )

        return RoutePlan(
            segments=segments,  # Keep original segment structure
            total_distance_miles=total_distance,
            total_duration_hours=total_duration,
            start_time=start_time,
            end_time=end_time,
            route_geometry=combined_geometry,
            driving_time=driving_time,
            resting_time=rest_time,
        )

    @staticmethod
    def combine_geometries(
        geometry1: RouteGeometry, geometry2: RouteGeometry
    ) -> RouteGeometry:
        """
        Combine two route geometries into a single RouteGeometry object.

        Args:
            geometry1 (RouteGeometry): First geometry (e.g., route to pickup)
            geometry2 (RouteGeometry): Second geometry (e.g., route to drop-off)

        Returns:
            RouteGeometry: Combined geometry for visualization
        """

        # Create a new RouteGeometry with merged coordinates
        coords1 = geometry1.coordinates
        coords2 = geometry2.coordinates

        # Skip duplicate connecting point if present
        if coords1 and coords2 and coords1[-1] == coords2[0]:
            merged_coords = coords1 + coords2[1:]
        else:
            merged_coords = coords1 + coords2

        return RouteGeometry(type=geometry1.type, coordinates=merged_coords)
