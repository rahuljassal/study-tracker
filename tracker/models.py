from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Max
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    starter_plan_created = models.BooleanField(default=False)


class Playlist(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="playlists",
    )
    name = models.CharField(max_length=120)
    start_date = models.DateField()
    videos_per_day = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.name

    @property
    def estimated_end_date(self):
        return self.get_estimated_end_date()

    def get_estimated_end_date(self, as_of=None):
        as_of = as_of or timezone.localdate()
        video_count = getattr(self, "video_count", None)
        completed_count = getattr(self, "completed_count", None)
        prefetched_videos = getattr(
            self, "_prefetched_objects_cache", {}
        ).get("videos")

        if video_count is None:
            video_count = (
                len(prefetched_videos)
                if prefetched_videos is not None
                else self.videos.count()
            )
        if completed_count is None:
            completed_count = (
                sum(video.completed_at is not None for video in prefetched_videos)
                if prefetched_videos is not None
                else self.videos.filter(completed_at__isnull=False).count()
            )

        if not video_count:
            return None

        pending_count = video_count - completed_count
        if pending_count <= 0:
            last_completed_at = getattr(self, "last_completed_at", None)
            if last_completed_at is None:
                if prefetched_videos is not None:
                    completion_dates = [
                        video.completed_at
                        for video in prefetched_videos
                        if video.completed_at is not None
                    ]
                    last_completed_at = max(completion_dates, default=None)
                else:
                    last_completed_at = self.videos.aggregate(
                        last=Max("completed_at")
                    )["last"]
            return (
                timezone.localtime(last_completed_at).date()
                if last_completed_at
                else as_of
            )

        forecast_start = max(self.start_date, as_of)
        days_needed = (
            pending_count + self.videos_per_day - 1
        ) // self.videos_per_day

        return forecast_start + timedelta(days=days_needed - 1)


class Video(models.Model):
    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="videos",
    )
    position = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    duration_seconds = models.PositiveIntegerField(default=0)
    url = models.URLField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["playlist", "position"],
                name="unique_video_position_per_playlist",
            ),
        ]

    @property
    def duration_display(self):
        if not self.duration_seconds:
            return "Duration not set"
        minutes, seconds = divmod(self.duration_seconds, 60)
        if minutes and seconds:
            return f"{minutes} min {seconds} sec"
        if minutes:
            return f"{minutes} min"
        return f"{seconds} sec"

    def __str__(self):
        return self.title