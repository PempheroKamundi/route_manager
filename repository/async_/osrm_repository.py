"""
repository.async.osrm_repository
~~~~~~~~~~~~~~~~~~~~~~

Repository module where all API requests to OSRM
are defined. All requests to OSRM go through here
"""

import json
import logging
from typing import Any, Dict, Optional

import polyline

from route_manager import settings

from .client import BaseAsyncClient, _AsyncClient
from .mixins import AsyncRouteRepositoryMixin, Location, RouteGeometry, RouteInformation

OSRM_URL = getattr(
    settings, "OSRM_URL", "http://router.project-osrm.org/route/v1/driving"
)

log = logging.getLogger(__name__)


class BaseOSRMError(Exception):
    """Base class for all OSRM errors"""

    pass


class InvalidOSRMResponse(BaseOSRMError):
    """Raised when OSRM returns a response that's not valid JSON"""

    def __init__(self, response):
        self.response = response
        log.error(f"Invalid OSRM response received: {self.response}")
        super().__init__(f"Invalid OSRM response: {self.response}")


class NoOSRMRouteFound(BaseOSRMError):
    """Raised when no OSRM route is found between two coordinates"""

    def __init__(self, origin, destination):
        self.response = origin
        self.destination = destination
        log.error(f"No OSRM route found between {origin} and {destination}")
        super().__init__(f"No OSRM route found between {origin} and {destination}")


def _convert_osrm_to_route_information(data: Dict[str, Any]) -> RouteInformation:
    """
    Create a RouteInformation instance from an OSRM API response.

    Args:
        data (Dict[str, Any]): Dictionary containing OSRM route information.

    Returns:
        RouteInformation: Parsed route information instance.

    """
    log.debug("Converting OSRM response to RouteInformation")

    route = data["routes"][0]  # OSRM returns multiple routes; pick the first one.
    log.debug(
        f"Selected route with distance {route['distance']}m and duration {route['duration']}s"
    )

    # Decode the polyline geometry
    geometry_data = route.get("geometry", "")
    decoded_coordinates = polyline.decode(geometry_data) if geometry_data else []
    log.debug(f"Decoded geometry with {len(decoded_coordinates)} coordinate points")

    geometry = RouteGeometry(type="LineString", coordinates=decoded_coordinates)

    route_info = RouteInformation(
        distance_miles=route["distance"] / 1609.34,  # Convert meters to miles
        duration_hours=route["duration"] / 3600.0,  # Convert seconds to hours
        geometry=geometry,
    )

    log.debug(
        f"Created RouteInformation: distance={route_info.distance_miles:.2f} miles, duration={route_info.duration_hours:.2f} hours"
    )
    return route_info


class AsyncOSRMRouteRepository(AsyncRouteRepositoryMixin):
    """
    Repository for fetching route information from OSRM.

    This class implements the AsyncRouteRepositoryMixin to provide
    asynchronous route information retrieval from the Open Source
    Routing Machine (OSRM) service.

    Attributes:
        _client (BaseAsyncClient): the client used to make asynchronous HTTP requests.
    """

    def __init__(self, client: BaseAsyncClient) -> None:
        """
        Initialize the repository with a client.

        Args:
            client (BaseAsyncClient): an async client for making HTTP requests.
        """
        log.debug("Initializing AsyncOSRMRouteRepository with client")
        self._client = client

    async def get_route_information(
        self, origin: Location, destination: Location
    ) -> RouteInformation:
        """
        Get route information between two locations.

        Constructs a URL with the coordinates and makes an async request
        to the OSRM service to retrieve routing information.

        Args:
            origin (Location): the starting location (lat/long).
            destination (Location): the ending location (lat/long).

        Returns:
            RouteInformation: Detailed information about the route.

        Raises:
            InvalidOSRMResponse: If the OSRM service returns an invalid response.
            NoOSRMRouteFound: If no routes are found between two coordinates.
        """
        log.info(
            f"Getting route information from {origin.latitude},{origin.longitude} to {destination.latitude},{destination.longitude}"
        )

        _origin = f"{origin.latitude},{origin.longitude}"
        _destination = f"{destination.latitude},{destination.longitude}"
        coordinates = f"{_origin};{_destination}"
        url = f"{OSRM_URL}/{coordinates}?overview=full&geometries=polyline"

        log.debug(f"Making request to OSRM URL: {url}")

        response = await self._client.make_request("GET", url)
        log.debug(f"Received response from OSRM with status: {response.status}")

        try:
            data = await response.json()
            log.debug("Successfully parsed JSON response from OSRM")
        except json.decoder.JSONDecodeError as e:
            log.error(f"Failed to decode JSON response from OSRM: {e}")
            raise InvalidOSRMResponse(response) from e

        if data.get("code") != "Ok" or not data.get("routes"):
            log.warning(
                f"OSRM returned no routes: {data.get('code', 'Unknown')} - {data.get('message', 'No message')}"
            )
            raise NoOSRMRouteFound(_origin, _destination)

        log.info("Successfully retrieved route information from OSRM")
        return _convert_osrm_to_route_information(data)


async def get_route_information(
    origin: Location, destination: Location, **kwargs: Optional[dict]
) -> RouteInformation:
    """
    Convenience function for fetching route information from OSRM.

    This function abstracts away the details of creating a client and repository,
    providing a simpler interface for getting route information.

    Args:
        origin (Location): the starting location (lat/long).
        destination (Location): the ending location (lat/long).
        **kwargs: Additional keyword arguments that might be needed in future implementations.

    Returns:
        RouteInformation: Detailed information about the route.

    Example:
        >>> from .mixins import Location
        >>> origin = Location(latitude=52.5169, longitude=13.3887)
        >>> destination = Location(latitude=52.5206, longitude=13.3862)
        >>> route_info = await get_route_information(origin, destination)
    """
    log.info(
        f"get_route_information called for origin={origin.latitude},{origin.longitude} to destination={destination.latitude},{destination.longitude}"
    )

    async with _AsyncClient() as client:
        log.debug("Created AsyncClient")
        repository = AsyncOSRMRouteRepository(client)
        log.debug("Created AsyncOSRMRouteRepository")

        route_info = await repository.get_route_information(origin, destination)
        log.info(
            f"Successfully retrieved route information: {route_info.distance_miles:.2f} miles, {route_info.duration_hours:.2f} hours"
        )
        return route_info
