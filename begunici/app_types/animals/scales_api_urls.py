from django.urls import path

from . import scales_api


app_name = "scales_api"

urlpatterns = [
    path("animals/", scales_api.animals, name="animals"),
    path("bindings/", scales_api.bindings, name="bindings"),
    path("identification/", scales_api.identification, name="identification"),
    path("places/", scales_api.places, name="places"),
    path("weights/", scales_api.weights, name="weights"),
    path("movements/", scales_api.movements, name="movements"),
]
