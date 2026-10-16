from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from tracker.forms import AddVideosForm, PlaylistForm
from tracker.models import Playlist, Video
from tracker.onboarding import provision_starter_plan
from tracker.youtube_import import YouTubeImportError, fetch_youtube_playlist

STARTER_PLAN_CHECK_SESSION_KEY = "tracker_starter_plan_checked_for"


@login_required
def dashboard(request):
    if request.session.get(STARTER_PLAN_CHECK_SESSION_KEY) != request.user.pk:
        provision_starter_plan(request.user)
        request.session[STARTER_PLAN_CHECK_SESSION_KEY] = request.user.pk
    playlists = request.user.playlists.annotate(
        video_count=Count("videos"),
        completed_count=Count(
            "videos", filter=Q(videos__completed_at__isnull=False)
        ),
        last_completed_at=Max("videos__completed_at"),
    ).order_by("created_at", "id")
    return render(request, "tracker/dashboard.html", {"playlists": playlists})


@login_required
def playlist_create(request):
    if request.method == "POST":
        form = PlaylistForm(request.POST)
        if form.is_valid():
            imported_playlist = None
            youtube_playlist_url = form.cleaned_data.get("youtube_playlist_url", "")
            if youtube_playlist_url:
                try:
                    imported_playlist = fetch_youtube_playlist(youtube_playlist_url)
                except YouTubeImportError as exc:
                    form.add_error("youtube_playlist_url", str(exc))
            if form.errors:
                return render(
                    request,
                    "tracker/playlist_form.html",
                    {
                        "form": form,
                        "page_title": "New playlist",
                        "submit_label": "Create playlist",
                    },
                )
            with transaction.atomic():
                playlist = form.save(commit=False)
                playlist.owner = request.user
                if imported_playlist:
                    if not request.POST.get("name", "").strip():
                        playlist.name = imported_playlist["name"]
                playlist.save()
                initial_videos = (
                    imported_playlist["videos"]
                    if imported_playlist
                    else form.cleaned_data["videos_text"]
                )
                Video.objects.bulk_create(
                    [
                        Video(playlist=playlist, position=index, **video)
                        for index, video in enumerate(initial_videos)
                    ]
                )
            messages.success(request, "Playlist created.")
            return redirect("playlist_detail", playlist_id=playlist.pk)
    else:
        form = PlaylistForm(initial={"start_date": timezone.localdate()})
    return render(
        request,
        "tracker/playlist_form.html",
        {"form": form, "page_title": "New playlist", "submit_label": "Create playlist"},
    )


@login_required
def playlist_detail(request, playlist_id):
    playlist = get_object_or_404(
        Playlist.objects.filter(owner=request.user).prefetch_related("videos"),
        pk=playlist_id,
    )
    videos = playlist.videos.all()
    completed_count = sum(bool(video.completed_at) for video in videos)
    playlist.video_count = len(videos)
    playlist.completed_count = completed_count
    completed_at_values = [
        video.completed_at for video in videos if video.completed_at is not None
    ]
    playlist.last_completed_at = max(completed_at_values, default=None)
    return render(
        request,
        "tracker/playlist_detail.html",
        {
            "playlist": playlist,
            "videos": videos,
            "completed_count": completed_count,
            "video_count": len(videos),
            "add_videos_form": AddVideosForm(),
        },
    )


@login_required
def playlist_update(request, playlist_id):
    playlist = get_object_or_404(Playlist, pk=playlist_id, owner=request.user)
    if request.method == "POST":
        form = PlaylistForm(request.POST, instance=playlist, include_videos=False)
        if form.is_valid():
            form.save()
            messages.success(request, "Playlist settings saved.")
            return redirect("playlist_detail", playlist_id=playlist.pk)
    else:
        form = PlaylistForm(instance=playlist, include_videos=False)
    return render(
        request,
        "tracker/playlist_form.html",
        {"form": form, "page_title": "Edit playlist", "submit_label": "Save changes"},
    )


@login_required
def playlist_delete(request, playlist_id):
    playlist = get_object_or_404(Playlist, pk=playlist_id, owner=request.user)
    if request.method == "POST":
        playlist.delete()
        messages.success(request, "Playlist deleted.")
        return redirect("dashboard")
    return render(request, "tracker/playlist_confirm_delete.html", {"playlist": playlist})


@login_required
@require_POST
def playlist_add_videos(request, playlist_id):
    playlist = get_object_or_404(Playlist, pk=playlist_id, owner=request.user)
    form = AddVideosForm(request.POST)
    if form.is_valid():
        start_position = playlist.videos.aggregate(last=Max("position"))["last"]
        start_position = 0 if start_position is None else start_position + 1
        Video.objects.bulk_create(
            [
                Video(playlist=playlist, position=start_position + index, **video)
                for index, video in enumerate(form.cleaned_data["videos_text"])
            ]
        )
        messages.success(request, "Videos added.")
    else:
        messages.error(request, " ".join(form.errors.get("videos_text", [])))
    return redirect("playlist_detail", playlist_id=playlist.pk)


@login_required
@require_POST
def video_toggle(request, playlist_id, video_id):
    video = get_object_or_404(
        Video.objects.select_related("playlist"),
        pk=video_id,
        playlist_id=playlist_id,
        playlist__owner=request.user,
    )
    video.completed_at = None if video.completed_at else timezone.now()
    video.save(update_fields=["completed_at"])
    return redirect("playlist_detail", playlist_id=playlist_id)