import datetime
import pprint
from dataclasses import dataclass
from typing import Any, List

from routing.trip_segment_planner import RouteSegment


@dataclass
class RoutePlan:
    segments: List[RouteSegment]
    total_distance_miles: float
    total_duration_hours: float
    start_time: datetime.datetime
    end_time: datetime.datetime
    route_geometry: Any


class TripSummaryMixin:
    """Mixin that provides trip summary functionality while using
    independent functions.
    """

    def calculate_trip_summary(
        self,
        segments: List[Any],  # RouteSegment
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        to_pickup_geometry: Any,
        to_drop_off_geometry: Any,
    ) -> RoutePlan:

        # Calculate total distance and duration from all segments
        total_distance = 0
        total_duration = 0

        with open("debug_segments.pkl", "w") as f:
            pp = pprint.PrettyPrinter(stream=f)
            pp.pprint(segments)

        for segment in segments:
            total_distance += segment.distance_miles
            total_duration += segment.duration_hours

        # Flatten segments list in case there are nested lists
        flat_segments = []
        for item in segments:
            if isinstance(item, list):
                flat_segments.extend(item)
            else:
                flat_segments.append(item)

        # Combine route geometries for full trip visualization
        combined_geometry = self.combine_geometries(
            to_pickup_geometry, to_drop_off_geometry
        )

        return RoutePlan(
            segments=segments,
            total_distance_miles=total_distance,
            total_duration_hours=total_duration,
            start_time=start_time,
            end_time=end_time,
            route_geometry=combined_geometry,
        )

    @staticmethod
    def combine_geometries(geometry1: Any, geometry2: Any) -> Any:
        print(geometry1, geometry2)
        """
        Combine two route geometries into a single geometry for.

        visualization.

        Handles various geometry formats including:
        - GeoJSON objects
        - Coordinate arrays
        - String representations
        - Empty/null geometries

        Args:
            geometry1: First geometry (e.g., route to pickup)
            geometry2: Second geometry (e.g., route to drop-off)

        Returns:
            Combined geometry suitable for visualization
        """
        # Handle empty geometries
        if not geometry1:
            return geometry2
        if not geometry2:
            return geometry1

        # Handle different geometry types

        # 1. If the geometries are lists/arrays of coordinates
        if isinstance(geometry1, list) and isinstance(geometry2, list):
            combined = list(geometry1)

            # Skip the first point of geometry2 if it's identical to the last point of geometry1
            # (This avoids duplicated points at the connection)
            if geometry2 and combined and geometry2[0] == combined[-1]:
                combined.extend(geometry2[1:])
            else:
                combined.extend(geometry2)

            return combined

        # 2. If the geometries are strings
        if isinstance(geometry1, str) and isinstance(geometry2, str):
            # For empty strings
            if not geometry1.strip():
                return geometry2
            if not geometry2.strip():
                return geometry1

            return geometry1 + geometry2

        # 3. If the geometries are dictionaries (like GeoJSON)
        if isinstance(geometry1, dict) and isinstance(geometry2, dict):
            # If they have the same type, try to merge their coordinates/features
            if geometry1.get("type") == geometry2.get("type"):
                # For LineString or similar types with coordinates
                if "coordinates" in geometry1 and "coordinates" in geometry2:
                    coords1 = geometry1["coordinates"]
                    coords2 = geometry2["coordinates"]

                    # Skip duplicate connecting point if present
                    if coords1 and coords2 and coords1[-1] == coords2[0]:
                        merged_coords = coords1 + coords2[1:]
                    else:
                        merged_coords = coords1 + coords2

                    return {"type": geometry1["type"], "coordinates": merged_coords}

                # For FeatureCollection with features array
                if "features" in geometry1 and "features" in geometry2:
                    return {
                        "type": "FeatureCollection",
                        "features": geometry1["features"] + geometry2["features"],
                    }

        # 4. Default: create a composite object for unknown or mixed geometry types
        return {"type": "CompositeGeometry", "geometries": [geometry1, geometry2]}
