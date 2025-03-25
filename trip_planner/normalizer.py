import math
from functools import lru_cache
from typing import Dict, List

from shapely.geometry import LineString


class FrontEndNormalizer:
    """
    Normalizes route plan data for frontend consumption by adding coordinate mapping
    to route segments.

    This class processes route geometry and segment data, adding precise start and end
    coordinates to each segment based on distance calculations along the route.
    """

    def __init__(self, route_plan: Dict):
        """
        Initialize the normalizer with a route plan.

        Args:
            route_plan: Dictionary containing route data with 'route_geometry' and 'segments'

        Raises:
            ValueError: If route_plan is missing required keys or has invalid structure
        """
        if not isinstance(route_plan, dict):
            raise ValueError("Route plan must be a dictionary")

        if "route_geometry" not in route_plan or "segments" not in route_plan:
            raise ValueError(
                "Route plan must contain 'route_geometry' and 'segments' keys"
            )

        if "coordinates" not in route_plan["route_geometry"]:
            raise ValueError("Route geometry must contain 'coordinates' key")

        self._route_plan = route_plan
        self._route_line = None
        self._miles_per_degree = None
        self._route_length_deg = None

    def normalize(self) -> Dict:
        """
        Process the route plan by mapping segments to coordinates.

        Returns:
            Updated route plan with segment coordinate data

        Raises:
            ValueError: If the route has no valid driving segments or coordinates
        """
        self._prepare_route_geometry()
        self.map_segments_with_coordinates()
        return self._route_plan

    @staticmethod
    @lru_cache(maxsize=128)  # Cache frequent distance calculations
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great-circle distance between two points using the Haversine formula.

        Args:
            lat1: Latitude of first point in decimal degrees
            lon1: Longitude of first point in decimal degrees
            lat2: Latitude of second point in decimal degrees
            lon2: Longitude of second point in decimal degrees

        Returns:
            Distance in miles
        """
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        r = 3958.8  # Earth radius in miles

        return c * r

    def _prepare_route_geometry(self) -> None:
        """
        Prepare route geometry by converting coordinates to a LineString and
        calculating route metrics.

        Raises:
            ValueError: If the route has no valid coordinates or driving segments
        """
        coordinates = self._route_plan["route_geometry"]["coordinates"]

        if not coordinates or len(coordinates) < 2:
            raise ValueError("Route must have at least two coordinates")

        # Convert [lat, lon] format to [lon, lat] for shapely
        shapely_coords = [(lon, lat) for lat, lon in coordinates]
        self._route_line = LineString(shapely_coords)

        # Calculate the total length of the route in degrees
        self._route_length_deg = self._route_line.length

        if self._route_length_deg <= 0:
            raise ValueError("Route length must be greater than zero")

        # Calculate the ratio between route length in degrees and miles
        total_driving_miles = sum(
            seg.get("distance_miles", 0)
            for seg in self._route_plan["segments"]
            if seg.get("type", "").lower().find("drive") != -1
        )

        if total_driving_miles <= 0:
            raise ValueError(
                "Route must have at least one driving segment with positive distance"
            )

        self._miles_per_degree = total_driving_miles / self._route_length_deg

    def find_point_at_distance(self, distance_miles: float) -> List[float]:
        """
        Find a geographical point at a specific distance along the route.

        Args:
            distance_miles: Distance along the route in miles

        Returns:
            Coordinate in [lat, lon] format

        Raises:
            ValueError: If route geometry hasn't been prepared
        """
        if self._route_line is None or self._miles_per_degree is None:
            raise ValueError("Route geometry must be prepared before finding points")

        # Convert miles to the equivalent distance in degrees
        distance_deg = (
            distance_miles / self._miles_per_degree if self._miles_per_degree > 0 else 0
        )

        # Ensure we don't exceed the route length
        distance_deg = min(max(0, distance_deg), self._route_length_deg)

        # Use interpolation to find the point
        point = self._route_line.interpolate(distance_deg)

        # Return in the format [lat, lon] as expected by the original data
        return [point.y, point.x]

    def map_segments_with_coordinates(self) -> None:
        """
        Map each segment to its coordinates along the route.

        Updates each segment in place with start_coordinates and end_coordinates.

        Raises:
            ValueError: If route geometry hasn't been prepared
        """
        if self._route_line is None:
            raise ValueError("Route geometry must be prepared before mapping segments")

        # Process each segment
        distance_traveled = 0

        for segment in self._route_plan["segments"]:
            # Store the starting location
            start_coordinates = self.find_point_at_distance(distance_traveled)
            segment["start_coordinates"] = start_coordinates

            # Add distance if this is a driving segment
            if segment.get("type", "").lower().find("drive") != -1:
                distance_traveled += segment.get("distance_miles", 0)

            # Store the ending location
            end_coordinates = self.find_point_at_distance(distance_traveled)
            segment["end_coordinates"] = end_coordinates
