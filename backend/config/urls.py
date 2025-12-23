"""URL configuration for PropLens project."""
from django.urls import path
from proplens.api import api

urlpatterns = [
    path("api/", api.urls),
]
