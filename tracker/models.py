from django.conf import settings
from django.db import models


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

    def __str__(self):
        return self.title