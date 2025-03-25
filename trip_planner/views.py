import asyncio
import datetime
import hashlib
import json
import logging

from django.core.cache import cache
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
from .serializers import TripSerializer, TruckerLogInputSerializer
from .services import TruckerLogService

logger = logging.getLogger(__name__)


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


def _get_user_start_time(start_time_str: str):
    try:
        start_time = datetime.datetime.fromisoformat(str(start_time_str))
        return start_time
    except ValueError:
        start_time = datetime.datetime.fromisoformat(
            start_time_str.replace("Z", "+00:00")
        )
        return start_time


def _generate_cache_key(data_dict):
    """
    Generate a cache key from request data
    """
    serialized = json.dumps(data_dict, sort_keys=True)
    return f"trip_cache_{hashlib.md5(serialized.encode()).hexdigest()}"


@method_decorator(csrf_exempt, name="dispatch")
class TripView(APIView):
    parser_classes = [JSONParser]
    throttle_classes = [TripUserRateThrottle, TripAnonRateThrottle]

    # Cache timeout in seconds (30 minutes)
    CACHE_TIMEOUT = 60 * 30

    """
    A simple view that processes trip data asynchronously with rate limiting and caching
    """

    def post(self, request):
        serializer = TripSerializer(data=request.data)

        if serializer.is_valid():
            cache_key = _generate_cache_key(serializer.validated_data)

            cached_response = cache.get(cache_key)
            if cached_response:
                logger.info(f"Cache hit for key: {cache_key}")
                return Response(cached_response, status=status.HTTP_200_OK)

            logger.info(f"Cache miss for key: {cache_key}")

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
            start_time_str = serializer.validated_data["start_time"]
            timezone_offset = serializer.validated_data["timezone_offset_minutes"]

            driver_timezone = datetime.timezone(
                datetime.timedelta(minutes=timezone_offset)
            )

            start_time = _get_user_start_time(start_time_str)
            # Convert to driver's timezone
            start_time = start_time.astimezone(driver_timezone)

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
                    route_planner.plan_route_trip(start_time)
                )
                normalized_data = FrontEndNormalizer(route_plan.to_dict()).normalize()

                cache.set(cache_key, normalized_data, self.CACHE_TIMEOUT)

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


class TruckerLogProcessView(APIView):
    throttle_classes = [TripUserRateThrottle, TripAnonRateThrottle]

    # Cache timeout in seconds (30 minutes)
    CACHE_TIMEOUT = 60 * 30

    """
    API view for processing trucker logs with caching.
    """

    def post(self, request, *args, **kwargs):
        serializer = TruckerLogInputSerializer(data=request.data)

        if serializer.is_valid():
            cache_key = _generate_cache_key(serializer.validated_data)

            cached_response = cache.get(cache_key)
            if cached_response:
                logger.info(f"Cache hit for trucker log: {cache_key}")
                return Response(
                    {"status": "success", "data": cached_response, "cached": True},
                    status=status.HTTP_200_OK,
                )

            logger.info(f"Cache miss for trucker log: {cache_key}")

            result = TruckerLogService.process_trucker_logs(serializer.validated_data)

            cache.set(cache_key, result, self.CACHE_TIMEOUT)

            return Response(
                {"status": "success", "data": result}, status=status.HTTP_200_OK
            )

        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
