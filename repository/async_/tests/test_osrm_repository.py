from unittest.mock import AsyncMock, patch

import pytest

from ..mixins import RouteInformation
from ..osrm_repository import (
    AsyncOSRMRouteRepository,
    NoOSRMRouteFound,
    _convert_osrm_to_route_information,
    get_route_information,
)
from .factory import LocationFactory, MockResponseFactory


class TestAsyncOSRMRouteRepository:

    @pytest.fixture
    def client(self):
        """Mock client fixture"""
        return AsyncMock()

    @pytest.fixture
    def repository(self, client):
        """Repository fixture with mock client"""
        return AsyncOSRMRouteRepository(client)

    @pytest.mark.asyncio
    async def test_get_route_information_success(self, repository, client):
        """Test successful route information retrieval"""
        # Setup
        origin = LocationFactory(latitude=52.5169, longitude=13.3887)
        destination = LocationFactory(latitude=52.5206, longitude=13.3862)

        mock_response = MockResponseFactory.create_success_response()
        client.make_request.return_value = mock_response

        # Execute
        result = await repository.get_route_information(origin, destination)

        # Assert
        assert isinstance(result, RouteInformation)
        assert result.distance_miles > 0
        assert result.duration_hours > 0
        assert result.geometry.type == "LineString"

        # Verify the client was called correctly
        expected_url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{origin.longitude},{origin.latitude};"
            f"{destination.longitude},{destination.latitude}"
        )
        client.make_request.assert_called_once_with("GET", expected_url)

    @pytest.mark.asyncio
    async def test_get_route_information_no_route(self, repository, client):
        """Test no route found response handling"""
        # Setup
        origin = LocationFactory()
        destination = LocationFactory()

        mock_response = MockResponseFactory.create_no_route_response()
        client.make_request.return_value = mock_response

        # Execute and assert
        with pytest.raises(NoOSRMRouteFound):
            await repository.get_route_information(origin, destination)


# Tests for the utility function
class TestConvertOSRMToRouteInformation:

    def test_convert_osrm_to_route_information(self):
        """Test the conversion function from OSRM data to RouteInformation"""
        # Setup
        osrm_data = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 5000.0,  # meters
                    "duration": 1800.0,  # seconds
                    "geometry": "_ibE_mcbBeBmA",  # Sample polyline
                }
            ],
        }

        # Execute
        result = _convert_osrm_to_route_information(osrm_data)

        # Assert
        assert isinstance(result, RouteInformation)
        assert result.distance_miles == pytest.approx(5000.0 / 1609.34)
        assert result.duration_hours == pytest.approx(1800.0 / 3600.0)
        assert result.geometry.type == "LineString"
        assert isinstance(result.geometry.coordinates, list)


# Tests for the convenience function
class TestGetRouteInformation:

    @pytest.mark.asyncio
    @patch("repository.async_.osrm_repository._AsyncClient")
    async def test_get_route_information_function(self, mock_async_client_class):
        """Test the convenience function that wraps the repository"""
        # Setup
        origin = LocationFactory()
        destination = LocationFactory()

        # Configure the mocks
        mock_client_instance = AsyncMock()
        mock_async_client_class.return_value.__aenter__.return_value = (
            mock_client_instance
        )

        mock_response = MockResponseFactory.create_success_response()
        mock_client_instance.make_request.return_value = mock_response

        # Execute
        result = await get_route_information(origin, destination)

        # Assert
        assert isinstance(result, RouteInformation)
        assert result.distance_miles > 0
        assert result.duration_hours > 0

        # Verify the client was called correctly
        expected_url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{origin.longitude},{origin.latitude};"
            f"{destination.longitude},{destination.latitude}"
        )
        mock_client_instance.make_request.assert_called_once_with("GET", expected_url)
