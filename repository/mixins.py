from abc import ABC
from collections import namedtuple
from dataclasses import dataclass, field
from typing import Any, Dict, List

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


@dataclass
class RouteInformation:
    """Represents the complete routing information."""

    distance_miles: float
    duration_hours: float
    geometry: RouteGeometry
    steps: List[RouteStep]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RouteInformation":
        """
        Create a RouteData instance from a dictionary.

        Args:
            data: Dictionary containing route information

        Returns:
            RouteData instance
        """
        # Convert the geometry dict to a RouteGeometry object
        geometry = RouteGeometry(
            type=data["geometry"]["type"], coordinates=data["geometry"]["coordinates"]
        )

        # Convert the steps list to RouteStep objects
        steps = []
        for step_data in data["steps"]:
            step_geometry = RouteGeometry(
                type=step_data["geometry"]["type"],
                coordinates=step_data["geometry"]["coordinates"],
            )

            step = RouteStep(
                distance=step_data["distance"],
                duration=step_data["duration"],
                geometry=step_geometry,
                name=step_data["name"],
                mode=step_data.get("mode", "driving"),
                maneuver=step_data.get("maneuver", {}),
                intersections=step_data.get("intersections", []),
            )
            steps.append(step)

        return cls(
            distance_miles=data["distance_miles"],
            duration_hours=data["duration_hours"],
            geometry=geometry,
            steps=steps,
        )


class AsyncRouteRepositoryMixin(ABC):
    """Repository mixin for routes"""

    async def get_route_information(
        self, origin: Location, destination: Location
    ) -> RouteInformation:
        raise NotImplementedError("get_route_information not implemented")
