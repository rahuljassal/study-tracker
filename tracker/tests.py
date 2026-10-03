from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tracker.models import Playlist, Video


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="learner",
            email="learner@example.com",
            password="test-only-password",
        )

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_dashboard_provisions_generic_starter_plan_once(self):
        self.client.force_login(self.user)

        first_response = self.client.get(reverse("dashboard"))
        second_response = self.client.get(reverse("dashboard"))

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(Playlist.objects.filter(owner=self.user).count(), 1)
        starter = Playlist.objects.get(owner=self.user)
        self.assertEqual(starter.name, "My First Learning Plan")
        self.assertEqual(starter.videos.count(), 5)
        self.assertFalse(starter.videos.exclude(url="").exists())

    def test_dashboard_never_lists_another_users_playlist(self):
        other_user = get_user_model().objects.create_user(
            username="other",
            email="other@example.com",
            password="test-only-password",
        )
        Playlist.objects.create(
            owner=other_user,
            name="Private plan belonging to someone else",
            start_date="2026-10-03",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Private plan belonging to someone else")
        self.assertContains(response, "My First Learning Plan")


class PlaylistOwnershipModelTests(TestCase):
    def test_videos_belong_to_a_playlist_and_are_ordered(self):
        user = get_user_model().objects.create_user(username="owner")
        playlist = Playlist.objects.create(
            owner=user,
            name="Skill plan",
            start_date="2026-10-03",
        )
        Video.objects.create(playlist=playlist, position=1, title="Second step")
        Video.objects.create(playlist=playlist, position=0, title="First step")

        self.assertEqual(
            list(playlist.videos.values_list("title", flat=True)),
            ["First step", "Second step"],
        )