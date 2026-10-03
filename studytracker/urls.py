from django.contrib import admin
from django.urls import include, path

from tracker.views import dashboard


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", dashboard, name="dashboard"),
]