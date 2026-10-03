from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, SimpleTestCase
from django.template.loader import get_template
from django.test import TestCase
from django.urls import reverse

from tracker.models import Playlist, Video
from tracker.services import duration_seconds, parse_video_lines


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
        self.assertEqual(
            self.client.session.get("tracker_starter_plan_checked_for"),
            self.user.pk,
        )

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


class SocialAccountConnectionPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="connections")

    def test_connection_page_requires_authentication(self):
        response = self.client.get(reverse("socialaccount_connections"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_connection_page_uses_tracker_layout(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("socialaccount_connections"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connected accounts")
        self.assertContains(response, "Connect Google")
        self.assertContains(response, "Connect GitHub")
        self.assertContains(response, 'href="/accounts/google/login/?process=connect"')
        self.assertContains(response, 'href="/accounts/github/login/?process=connect"')


class LoginProviderLinkTests(TestCase):
    def test_sign_in_page_uses_direct_allauth_routes(self):
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/accounts/google/login/"')
        self.assertContains(response, 'href="/accounts/github/login/"')


class SocialSignupTemplateTests(TestCase):
    def test_third_party_signup_uses_project_template(self):
        template = get_template("socialaccount/signup.html")

        self.assertTrue(template.origin.name.endswith("templates/socialaccount/signup.html"))


class PlaylistCrudTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="crud-user",
            email="crud@example.com",
        )
        self.client.force_login(self.user)

    def make_playlist(self, owner=None):
        return Playlist.objects.create(
            owner=owner or self.user,
            name="Study plan",
            start_date="2026-10-03",
            videos_per_day=2,
        )

    def test_create_playlist_and_parse_video_entries(self):
        response = self.client.post(
            reverse("playlist_create"),
            {
                "name": "Python course",
                "start_date": "2026-10-03",
                "videos_per_day": 2,
                "videos_text": "01 | Intro | 11:04 | https://example.com/intro",
            },
        )

        self.assertEqual(response.status_code, 302)
        playlist = Playlist.objects.get(owner=self.user, name="Python course")
        video = playlist.videos.get()
        self.assertEqual(video.title, "Intro")
        self.assertEqual(video.duration_seconds, 664)
        self.assertEqual(video.url, "https://example.com/intro")

    def test_create_rejects_non_http_video_url(self):
        response = self.client.post(
            reverse("playlist_create"),
            {
                "name": "Invalid links",
                "start_date": "2026-10-03",
                "videos_per_day": 1,
                "videos_text": "Lesson | 02:10 | javascript:alert(1)",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Playlist.objects.filter(owner=self.user, name="Invalid links").exists())

    def test_edit_playlist_and_delete_it_with_videos(self):
        playlist = self.make_playlist()
        video = Video.objects.create(playlist=playlist, position=0, title="Lesson")

        response = self.client.post(
            reverse("playlist_update", args=[playlist.pk]),
            {
                "name": "Updated plan",
                "start_date": "2026-10-05",
                "videos_per_day": 3,
            },
        )
        playlist.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(playlist.name, "Updated plan")
        self.assertEqual(playlist.videos_per_day, 3)

        response = self.client.post(reverse("playlist_delete", args=[playlist.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Playlist.objects.filter(pk=playlist.pk).exists())
        self.assertFalse(Video.objects.filter(pk=video.pk).exists())

    def test_add_video_entries_and_toggle_completion(self):
        playlist = self.make_playlist()
        first = Video.objects.create(playlist=playlist, position=0, title="First")

        response = self.client.post(
            reverse("playlist_add_videos", args=[playlist.pk]),
            {"videos_text": "Second | NA | https://example.com/second"},
        )
        self.assertEqual(response.status_code, 302)
        second = playlist.videos.get(position=1)
        self.assertEqual(second.duration_seconds, 0)

        response = self.client.post(
            reverse("video_toggle", args=[playlist.pk, first.pk])
        )
        first.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(first.completed_at)

        self.client.post(reverse("video_toggle", args=[playlist.pk, first.pk]))
        first.refresh_from_db()
        self.assertIsNone(first.completed_at)

    def test_other_user_cannot_read_edit_delete_or_mutate_playlist(self):
        other_user = get_user_model().objects.create_user(username="another-user")
        playlist = self.make_playlist(owner=other_user)
        video = Video.objects.create(playlist=playlist, position=0, title="Private")

        detail = self.client.get(reverse("playlist_detail", args=[playlist.pk]))
        edit = self.client.get(reverse("playlist_update", args=[playlist.pk]))
        delete = self.client.post(reverse("playlist_delete", args=[playlist.pk]))
        add_video = self.client.post(
            reverse("playlist_add_videos", args=[playlist.pk]),
            {"videos_text": "Injected | NA | https://example.com/injected"},
        )
        toggle = self.client.post(
            reverse("video_toggle", args=[playlist.pk, video.pk])
        )

        self.assertEqual([detail.status_code, edit.status_code, delete.status_code], [404, 404, 404])
        self.assertEqual([add_video.status_code, toggle.status_code], [404, 404])
        self.assertEqual(playlist.videos.count(), 1)
        self.assertIsNone(video.completed_at)

    def test_playlist_detail_escapes_user_supplied_video_title(self):
        playlist = self.make_playlist()
        Video.objects.create(
            playlist=playlist,
            position=0,
            title="<script>alert(1)</script>",
        )

        response = self.client.get(reverse("playlist_detail", args=[playlist.pk]))

        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")


class VideoImportValidationTests(SimpleTestCase):
    def test_duration_parser_accepts_supported_formats(self):
        self.assertEqual(duration_seconds("11:04"), 664)
        self.assertEqual(duration_seconds("1:04:45"), 3885)
        self.assertEqual(duration_seconds("NA"), 0)

    def test_duration_parser_rejects_invalid_ranges(self):
        with self.assertRaises(ValueError):
            duration_seconds("1:60:00")
        with self.assertRaises(ValueError):
            duration_seconds("4:90")

    def test_video_parser_rejects_invalid_scheme_and_duration(self):
        with self.assertRaises(ValidationError):
            parse_video_lines("Lesson | 01:00 | javascript:alert(1)")
        with self.assertRaises(ValidationError):
            parse_video_lines("Lesson | 1:99:00 | https://example.com/video")


class CsrfProtectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="csrf-user")
        self.playlist = Playlist.objects.create(
            owner=self.user,
            name="CSRF test playlist",
            start_date="2026-10-03",
        )
        self.video = Video.objects.create(
            playlist=self.playlist,
            position=0,
            title="CSRF test video",
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def test_all_mutation_endpoints_reject_missing_csrf_token(self):
        requests = [
            ("post", reverse("playlist_create"), {
                "name": "Should not save",
                "start_date": "2026-10-03",
                "videos_per_day": 1,
            }),
            ("post", reverse("playlist_update", args=[self.playlist.pk]), {
                "name": "Changed",
                "start_date": "2026-10-03",
                "videos_per_day": 1,
            }),
            ("post", reverse("playlist_delete", args=[self.playlist.pk]), {}),
            ("post", reverse("playlist_add_videos", args=[self.playlist.pk]), {
                "videos_text": "New | NA | https://example.com/new",
            }),
            ("post", reverse("video_toggle", args=[self.playlist.pk, self.video.pk]), {}),
        ]

        for method, url, data in requests:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url, data)
                self.assertEqual(response.status_code, 403)

        self.assertEqual(Playlist.objects.filter(name="Should not save").count(), 0)
        self.assertTrue(Playlist.objects.filter(pk=self.playlist.pk).exists())
        self.video.refresh_from_db()
        self.assertIsNone(self.video.completed_at)