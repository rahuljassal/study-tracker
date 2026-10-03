from django.db import transaction
from django.utils import timezone

from tracker.models import Playlist, UserProfile, Video


STARTER_STEPS = [
    "Choose a skill and set a learning goal",
    "Find a course, playlist, or learning resource",
    "Complete your first lesson",
    "Practice one idea from what you learned",
    "Review your progress and plan the next step",
]


@transaction.atomic
def provision_starter_plan(user):
    profile, _ = UserProfile.objects.select_for_update().get_or_create(user=user)
    if profile.starter_plan_created:
        return None

    playlist = Playlist.objects.create(
        owner=user,
        name="My First Learning Plan",
        start_date=timezone.localdate(),
        videos_per_day=1,
    )
    Video.objects.bulk_create(
        [
            Video(playlist=playlist, position=index, title=title)
            for index, title in enumerate(STARTER_STEPS)
        ]
    )
    profile.starter_plan_created = True
    profile.save(update_fields=["starter_plan_created"])
    return playlist