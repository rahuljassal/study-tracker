from django.contrib import admin
from django.urls import include, path

from tracker.views import (
    dashboard,
    playlist_add_videos,
    playlist_create,
    playlist_delete,
    playlist_detail,
    playlist_update,
    video_toggle,
)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", dashboard, name="dashboard"),
    path("playlists/new/", playlist_create, name="playlist_create"),
    path("playlists/<int:playlist_id>/", playlist_detail, name="playlist_detail"),
    path("playlists/<int:playlist_id>/edit/", playlist_update, name="playlist_update"),
    path("playlists/<int:playlist_id>/delete/", playlist_delete, name="playlist_delete"),
    path("playlists/<int:playlist_id>/videos/add/", playlist_add_videos, name="playlist_add_videos"),
    path("playlists/<int:playlist_id>/videos/<int:video_id>/toggle/", video_toggle, name="video_toggle"),
]