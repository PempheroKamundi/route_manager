import logging

from route_manager import settings

from ._async_clients import BaseAsyncClient, _AsyncClient
from .mixins import AsyncRouteRepositoryMixin, Location, RouteInformation

OSRM_URL = getattr(
    settings, "OSRM_URL", "https://router.project-osrm.org/route/v1/driving"
)

log = logging.getLogger(__name__)


class BaseOSRMRouteRepository(AsyncRouteRepositoryMixin):
    def __init__(self, client: BaseAsyncClient):
        self._client = client

    async def get_route_information(
        self, origin: Location, destination: Location
    ) -> RouteInformation:
        coordinates = f"{origin.longitude},{origin.latitude};{destination.longitude},{destination.longitude}"
        url = f"{OSRM_URL}/{coordinates}"

        # Make the request
        response = await self._client.make_request("GET", url)
        return RouteInformation.from_dict(response)


class OSRMRouteRepository(AsyncRouteRepositoryMixin):

    async def get_route_information(
        self, origin: Location, destination: Location
    ) -> RouteInformation:
        async with _AsyncClient() as client:
            return await BaseOSRMRouteRepository(client).get_route_information(
                origin, destination
            )
