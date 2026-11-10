from django.urls import path
from . import views

urlpatterns = [
    path("", views.query_console, name="query_console"),
]
