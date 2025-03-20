from django.urls import path

from .views import TripView

urlpatterns = [
    path("api/trips/", TripView.as_view(), name="trip-list"),
]
