"""
repository.async.mixins
~~~~~~~~~~~~~~~~~~~~~~~

Provides mixin classes to be inherited by various
repository implementations.
"""

from abc import ABC
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, Field


class Location(BaseModel):
    """Represents a geographical location."""

    longitude: float
    latitude: float


class RouteGeometry(BaseModel):
    """Represents the geometry of a route."""

    type: str = Field(default="LineString")
    coordinates: List[Tuple[float, float]] = Field(default_factory=list)


class RouteStep(BaseModel):
    """Represents a single step in the route directions."""

    distance: float
    duration: float
    geometry: RouteGeometry
    name: str
    mode: str = Field(default="driving")
    maneuver: Dict[str, Any] = Field(default_factory=dict)
    intersections: List[Dict[str, Any]] = Field(default_factory=list)


class RouteInformation(BaseModel):
    """Represents the complete routing information."""

    distance_miles: float
    duration_hours: float
    geometry: RouteGeometry


class AsyncRouteRepositoryMixin(ABC):
    """Repository mixin for route information."""

    async def get_route_information(
        self, origin: Location, destination: Location
    ) -> RouteInformation:
        """Fetches route information asynchronously.

        Args:
            origin (Location): Starting point of the route.
            destination (Location): Destination point of the route.

        Returns:
            RouteInformation: Parsed route details.

        Raises:
            NotImplementedError: If not implemented in the subclass.
        """
        raise NotImplementedError("get_route_information not implemented")
