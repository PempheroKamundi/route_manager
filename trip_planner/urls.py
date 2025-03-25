from django.urls import path

from .views import TripView, TruckerLogProcessView

urlpatterns = [
    path("api/trips/", TripView.as_view(), name="trip-list"),
    path("api/process-logs/", TruckerLogProcessView.as_view(), name="process-logs"),
]
