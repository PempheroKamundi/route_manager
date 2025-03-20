import asyncio

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from repository.mixins import Location
from routing.route_planner import StandardRoutePlanner

from .serializers import TripSerializer


@method_decorator(csrf_exempt, name="dispatch")
class TripView(APIView):
    parser_classes = [JSONParser]

    """
    A simple view that processes trip data asynchronously
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

            route_planner = StandardRoutePlanner.create_planner(
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
            results = loop.run_until_complete(route_planner.plan_route_trip())
            print(results)

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
