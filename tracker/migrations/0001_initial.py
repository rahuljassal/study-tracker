from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Playlist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("start_date", models.DateField()),
                ("videos_per_day", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="playlists", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("starter_plan_created", models.BooleanField(default=False)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Video",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=200)),
                ("duration_seconds", models.PositiveIntegerField(default=0)),
                ("url", models.URLField(blank=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("playlist", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="videos", to="tracker.playlist")),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.AddConstraint(
            model_name="video",
            constraint=models.UniqueConstraint(fields=("playlist", "position"), name="unique_video_position_per_playlist"),
        ),
    ]