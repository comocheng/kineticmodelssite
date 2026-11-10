"""URLconf of the canonical URLs /id/<kind>/<key> (provenance.id_resolver)."""
from django.urls import path

from provenance import id_resolver

urlpatterns = [
    path("<str:kind>/<path:key>", id_resolver.resolve, name="record-id"),
]
