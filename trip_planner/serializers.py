from rest_framework import serializers


class LocationSerializer(serializers.Serializer):
    longitude = serializers.FloatField()
    latitude = serializers.FloatField()


class TripSerializer(serializers.Serializer):
    current_location = LocationSerializer()
    pickup_location = LocationSerializer()
    drop_off_location = LocationSerializer()
    current_cycle_used = serializers.FloatField()
