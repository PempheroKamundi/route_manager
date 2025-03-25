from typing import Any, Dict

import factory

from ..mixins import Location, RouteGeometry, RouteInformation


class LocationFactory(factory.Factory):
    class Meta:
        model = Location

    latitude = factory.Faker("latitude")
    longitude = factory.Faker("longitude")


class RouteGeometryFactory(factory.Factory):
    class Meta:
        model = RouteGeometry

    type = "LineString"
    coordinates = factory.List(
        [
            factory.List([factory.Faker("longitude"), factory.Faker("latitude")])
            for _ in range(5)
        ]
    )


class RouteInformationFactory(factory.Factory):
    class Meta:
        model = RouteInformation

    distance_miles = factory.Faker("pyfloat", positive=True, min_value=1, max_value=100)
    duration_hours = factory.Faker("pyfloat", positive=True, min_value=0.1, max_value=5)
    geometry = factory.SubFactory(RouteGeometryFactory)


class MockResponseFactory:
    """Factory for creating mock HTTP responses"""

    @staticmethod
    def create_success_response(route_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a mock successful response from OSRM"""
        if route_data is None:
            route_data = {
                "code": "Ok",
                "routes": [
                    {
                        "distance": 1000.0,  # meters
                        "duration": 360.0,  # seconds
                        "geometry": "_ibE_mcbBeBmA",  # Sample polyline
                    }
                ],
            }
        return route_data

    @staticmethod
    def create_no_route_response() -> Dict[str, Any]:
        """Create a mock response where no route is found"""
        return {"code": "NoRoute", "routes": []}
