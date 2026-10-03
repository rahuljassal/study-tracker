from django.urls import path

from tracker.views import dashboard


urlpatterns = [path("", dashboard, name="dashboard")]