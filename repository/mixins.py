from abc import ABC
from collections import namedtuple
from dataclasses import dataclass, field
from typing import Any, Dict, List

import polyline

Location = namedtuple("Location", ["longitude", "latitude"])


@dataclass
class RouteGeometry:
    """Represents the geometry of a route."""

    type: str
    coordinates: List[List[float]]


@dataclass
class RouteStep:
    """Represents a single step in the route directions."""

    distance: float
    duration: float
    geometry: RouteGeometry
    name: str
    mode: str = "driving"
    maneuver: Dict[str, Any] = field(default_factory=dict)
    intersections: List[Dict[str, Any]] = field(default_factory=list)


class RouteInformation:
    """Represents the complete routing information."""

    def __init__(
        self,
        distance_miles: float,
        duration_hours: float,
        geometry: RouteGeometry,
        steps: List[RouteStep],
    ):
        self.distance_miles = distance_miles
        self.duration_hours = duration_hours
        self.geometry = geometry
        self.steps = steps

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RouteInformation":
        """
        Create a RouteInformation instance from an OSRM API response.

        Args:
            data: Dictionary containing OSRM route information

        Returns:
            RouteInformation instance

        Raises:
            ValueError: If the route is impossible or data format is invalid
        """
        # Check if there are any routes available
        if "code" not in data or data["code"] != "Ok" or not data.get("routes"):
            raise ValueError("No valid route found or impossible route")

        # Get the first route (OSRM returns an array of routes)
        route = data["routes"][0]

        # Decode the polyline geometry
        decoded_geometry = None
        if "geometry" in route:
            if isinstance(route["geometry"], str):
                # If geometry is a polyline string, decode it
                decoded_coordinates = polyline.decode(route["geometry"])
                decoded_geometry = RouteGeometry(
                    type="LineString", coordinates=decoded_coordinates
                )
            elif isinstance(route["geometry"], dict):
                # If geometry is already a GeoJSON object
                decoded_geometry = RouteGeometry(
                    type=route["geometry"].get("type", "LineString"),
                    coordinates=route["geometry"].get("coordinates", []),
                )
        else:
            # Default empty geometry if none provided
            decoded_geometry = RouteGeometry()

        # Convert meters to miles and seconds to hours
        distance_miles = route["distance"] / 1609.34  # meters to miles
        duration_hours = route["duration"] / 3600.0  # seconds to hours

        # Process steps if available
        steps = []
        if "legs" in route and route["legs"]:
            for leg in route["legs"]:
                if "steps" in leg:
                    for step_data in leg["steps"]:
                        # Process step geometry
                        step_geometry = None
                        if "geometry" in step_data:
                            if isinstance(step_data["geometry"], str):
                                # Decode polyline geometry
                                step_coordinates = polyline.decode(
                                    step_data["geometry"]
                                )
                                step_geometry = RouteGeometry(
                                    type="LineString", coordinates=step_coordinates
                                )
                            elif isinstance(step_data["geometry"], dict):
                                step_geometry = RouteGeometry(
                                    type=step_data["geometry"].get(
                                        "type", "LineString"
                                    ),
                                    coordinates=step_data["geometry"].get(
                                        "coordinates", []
                                    ),
                                )
                        else:
                            step_geometry = RouteGeometry()

                        # Create step object
                        step = RouteStep(
                            distance=step_data.get("distance", 0),
                            duration=step_data.get("duration", 0),
                            geometry=step_geometry,
                            name=step_data.get("name", ""),
                            mode=step_data.get("mode", "driving"),
                            maneuver=step_data.get("maneuver", {}),
                            intersections=step_data.get("intersections", []),
                        )
                        steps.append(step)

        return cls(
            distance_miles=distance_miles,
            duration_hours=duration_hours,
            geometry=decoded_geometry,
            steps=steps,
        )


class AsyncRouteRepositoryMixin(ABC):
    """Repository mixin for routes"""

    async def get_route_information(
        self, origin: Location, destination: Location
    ) -> RouteInformation:
        raise NotImplementedError("get_route_information not implemented")
