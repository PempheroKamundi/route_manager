import asyncio
import datetime

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from repository.async_.client import NetworkTimeOutError
from repository.async_.mixins import Location
from repository.async_.osrm_repository import InvalidOSRMResponse, NoOSRMRouteFound
from routing.route_planner.standard_route_planner import USAStandardRoutePlanner

from .normalizer import FrontEndNormalizer
from .serializers import TripSerializer


class TripUserRateThrottle(UserRateThrottle):
    """
    Rate throttle for authenticated users
    """

    rate = "40/minute"  # 10 requests per minute for authenticated users


class TripAnonRateThrottle(AnonRateThrottle):
    """
    Rate throttle for anonymous users
    """

    rate = "20/minute"  # 20 requests per minute for anonymous users


@method_decorator(csrf_exempt, name="dispatch")
class TripView(APIView):
    parser_classes = [JSONParser]
    throttle_classes = [TripUserRateThrottle, TripAnonRateThrottle]

    """
    A simple view that processes trip data asynchronously with rate limiting
    """

    def post(self, request):
        serializer = TripSerializer(data=request.data)

        if serializer.is_valid():
            current_location = Location(
                longitude=serializer.validated_data["current_location"]["longitude"],
                latitude=serializer.validated_data["current_location"]["latitude"],
            )

            pickup_location = Location(
                longitude=serializer.validated_data["pickup_location"]["longitude"],
                latitude=serializer.validated_data["pickup_location"]["latitude"],
            )

            drop_off_location = Location(
                longitude=serializer.validated_data["drop_off_location"]["longitude"],
                latitude=serializer.validated_data["drop_off_location"]["latitude"],
            )

            current_cycle_used = serializer.validated_data["current_cycle_used"]
            planned_time = datetime.datetime.now(datetime.timezone.utc)

            route_planner = USAStandardRoutePlanner.create_route(
                current_location=current_location,
                pickup_location=pickup_location,
                drop_off_location=drop_off_location,
                current_cycle_used=current_cycle_used,
            )

            # Get the current event loop or create a new one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Run the async method in the event loop
            try:
                route_plan = loop.run_until_complete(
                    route_planner.plan_route_trip(planned_time)
                )
                normalized_data = FrontEndNormalizer(route_plan.to_dict()).normalize()
                return Response(normalized_data, status=status.HTTP_200_OK)

            except InvalidOSRMResponse:
                return Response(
                    {
                        "error": "Unable to process routing request due to invalid response from routing service."
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            except NoOSRMRouteFound:
                return Response(
                    {
                        "error": "No viable route could be found for the requested journey."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            except NetworkTimeOutError:
                return Response(
                    {"error": "Routing service timed out. Please try again later."},
                    status=status.HTTP_504_GATEWAY_TIMEOUT,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
