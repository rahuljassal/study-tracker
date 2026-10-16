from datetime import date, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.template.loader import get_template
from django.test import Client, SimpleTestCase
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tracker.models import Playlist, Video
from tracker.services import duration_seconds, parse_video_lines
from tracker.youtube_import import (
    YouTubeImportError,
    extract_playlist_id,
    fetch_youtube_playlist,
)


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

    def test_estimated_end_date_uses_rounded_up_days_and_includes_start_date(self):
        user = get_user_model().objects.create_user(username="date-owner")
        playlist = Playlist.objects.create(
            owner=user,
            name="Date estimate",
            start_date=date(2026, 10, 3),
            videos_per_day=2,
        )
        for position in range(5):
            Video.objects.create(
                playlist=playlist,
                position=position,
                title=f"Lesson {position + 1}",
            )

        self.assertEqual(
            playlist.get_estimated_end_date(as_of=date(2026, 10, 3)),
            date(2026, 10, 5),
        )

    def test_empty_playlist_has_no_estimated_end_date(self):
        user = get_user_model().objects.create_user(username="empty-date-owner")
        playlist = Playlist.objects.create(
            owner=user,
            name="Empty plan",
            start_date=date(2026, 10, 3),
            videos_per_day=2,
        )

        self.assertIsNone(playlist.get_estimated_end_date(as_of=date(2026, 10, 3)))

    def test_estimate_uses_configured_daily_pace_for_remaining_videos(self):
        user = get_user_model().objects.create_user(username="fast-date-owner")
        playlist = Playlist.objects.create(
            owner=user,
            name="Fast progress",
            start_date=date(2026, 10, 3),
            videos_per_day=1,
        )
        for position in range(30):
            Video.objects.create(
                playlist=playlist,
                position=position,
                title=f"Lesson {position + 1}",
                completed_at=(
                    timezone.make_aware(datetime(2026, 10, 3, 12))
                    if position < 2
                    else None
                ),
            )

        self.assertEqual(
            playlist.get_estimated_end_date(as_of=date(2026, 10, 3)),
            date(2026, 10, 30),
        )

        Video.objects.filter(playlist=playlist, position__in=[2, 3]).update(
            completed_at=timezone.make_aware(datetime(2026, 10, 3, 15))
        )
        self.assertEqual(
            playlist.get_estimated_end_date(as_of=date(2026, 10, 3)),
            date(2026, 10, 28),
        )

    def test_estimate_uses_latest_completion_date_when_all_videos_are_done(self):
        user = get_user_model().objects.create_user(username="finished-date-owner")
        playlist = Playlist.objects.create(
            owner=user,
            name="Finished plan",
            start_date=date(2026, 10, 3),
            videos_per_day=2,
        )
        Video.objects.create(
            playlist=playlist,
            position=0,
            title="Lesson",
            completed_at=timezone.make_aware(datetime(2026, 10, 5, 12)),
        )

        self.assertEqual(
            playlist.get_estimated_end_date(as_of=date(2026, 10, 6)),
            date(2026, 10, 5),
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

    @patch("tracker.views.fetch_youtube_playlist")
    def test_create_playlist_from_youtube_url_uses_imported_title_and_videos(
        self, import_playlist
    ):
        import_playlist.return_value = {
            "name": "Imported course",
            "videos": [
                {
                    "title": "First lesson",
                    "duration_seconds": 125,
                    "url": "https://www.youtube.com/watch?v=video123",
                }
            ],
        }

        response = self.client.post(
            reverse("playlist_create"),
            {
                "name": "",
                "youtube_playlist_url": "https://www.youtube.com/playlist?list=PL123456",
                "videos_text": "",
                "start_date": "2026-10-03",
                "videos_per_day": 2,
            },
        )

        self.assertEqual(response.status_code, 302)
        playlist = Playlist.objects.get(owner=self.user, name="Imported course")
        video = playlist.videos.get()
        self.assertEqual(video.title, "First lesson")
        self.assertEqual(video.duration_seconds, 125)
        self.assertEqual(video.url, "https://www.youtube.com/watch?v=video123")

    @patch("tracker.views.fetch_youtube_playlist")
    def test_create_form_displays_youtube_import_errors_without_saving(
        self, import_playlist
    ):
        import_playlist.side_effect = YouTubeImportError(
            "This playlist is private or unavailable."
        )

        response = self.client.post(
            reverse("playlist_create"),
            {
                "name": "",
                "youtube_playlist_url": "https://www.youtube.com/playlist?list=PL123456",
                "videos_text": "",
                "start_date": "2026-10-03",
                "videos_per_day": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This playlist is private or unavailable.")
        self.assertFalse(Playlist.objects.filter(owner=self.user).exists())

    def test_create_form_requires_one_video_source(self):
        response = self.client.post(
            reverse("playlist_create"),
            {
                "name": "Mixed sources",
                "youtube_playlist_url": "https://www.youtube.com/playlist?list=PL123456",
                "videos_text": "Manual | 01:00 | https://example.com/video",
                "start_date": "2026-10-03",
                "videos_per_day": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a YouTube playlist URL or pasted videos")
        self.assertFalse(Playlist.objects.filter(owner=self.user).exists())

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

    @patch("django.utils.timezone.localdate", return_value=date(2026, 10, 3))
    def test_playlist_list_and_detail_show_estimated_end_date(self, _localdate):
        playlist = self.make_playlist()
        for position in range(3):
            Video.objects.create(
                playlist=playlist,
                position=position,
                title=f"Lesson {position + 1}",
            )

        dashboard = self.client.get(reverse("dashboard"))
        detail = self.client.get(reverse("playlist_detail", args=[playlist.pk]))

        self.assertContains(dashboard, "estimated end Oct 4, 2026")
        self.assertContains(detail, "estimated end Oct 4, 2026")

    def test_playlist_detail_shows_video_duration_in_minutes(self):
        playlist = self.make_playlist()
        Video.objects.create(
            playlist=playlist,
            position=0,
            title="A timed lesson",
            duration_seconds=664,
        )

        response = self.client.get(reverse("playlist_detail", args=[playlist.pk]))

        self.assertContains(response, "11 min 4 sec")


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


class YouTubePlaylistImportTests(SimpleTestCase):
    def test_extract_playlist_id_from_supported_youtube_urls(self):
        self.assertEqual(
            extract_playlist_id(
                "https://www.youtube.com/playlist?list=PLabc_123-xyz"
            ),
            "PLabc_123-xyz",
        )
        self.assertEqual(
            extract_playlist_id("https://youtu.be/watch?list=PLabc123"),
            "PLabc123",
        )

    def test_rejects_non_youtube_or_non_playlist_urls(self):
        for url in (
            "https://example.com/playlist?list=PLabc123",
            "javascript:alert(1)",
            "https://www.youtube.com/watch?v=video123",
        ):
            with self.subTest(url=url), self.assertRaises(YouTubeImportError):
                extract_playlist_id(url)

    @override_settings(YOUTUBE_API_KEY="test-key")
    @patch("tracker.youtube_import._youtube_api_get")
    def test_fetches_playlist_video_metadata_in_playlist_order(self, api_get):
        api_get.side_effect = [
            {"items": [{"snippet": {"title": "Python course"}}]},
            {
                "items": [
                    {
                        "contentDetails": {"videoId": "video123"},
                        "snippet": {"title": "Playlist lesson"},
                    }
                ]
            },
            {
                "items": [
                    {
                        "id": "video123",
                        "snippet": {"title": "Python lesson"},
                        "contentDetails": {"duration": "PT1H2M3S"},
                    }
                ]
            },
        ]

        result = fetch_youtube_playlist(
            "https://www.youtube.com/playlist?list=PLabc123"
        )

        self.assertEqual(result["name"], "Python course")
        self.assertEqual(
            result["videos"],
            [
                {
                    "title": "Python lesson",
                    "duration_seconds": 3723,
                    "url": "https://www.youtube.com/watch?v=video123",
                }
            ],
        )

    @override_settings(YOUTUBE_API_KEY="test-key")
    @patch("tracker.youtube_import._youtube_api_get")
    def test_follows_playlist_pagination(self, api_get):
        first_page = [
            {
                "contentDetails": {"videoId": f"video_{index}"},
                "snippet": {"title": f"Lesson {index}"},
            }
            for index in range(50)
        ]
        api_get.side_effect = [
            {"items": [{"snippet": {"title": "Paged course"}}]},
            {"items": first_page, "nextPageToken": "page-two"},
            {
                "items": [
                    {
                        "contentDetails": {"videoId": "last_video"},
                        "snippet": {"title": "Last lesson"},
                    }
                ]
            },
            {"items": []},
            {"items": []},
        ]

        result = fetch_youtube_playlist(
            "https://www.youtube.com/playlist?list=PLabc123"
        )

        self.assertEqual(len(result["videos"]), 51)
        self.assertEqual(result["videos"][-1]["title"], "Last lesson")
        self.assertEqual(api_get.call_args_list[2].args[1]["pageToken"], "page-two")

    @override_settings(YOUTUBE_API_KEY="test-key")
    @patch("tracker.youtube_import._youtube_api_get")
    def test_import_is_capped_at_200_videos(self, api_get):
        playlist_entries = [
            {
                "contentDetails": {"videoId": f"video_{index}"},
                "snippet": {"title": f"Lesson {index}"},
            }
            for index in range(201)
        ]
        api_get.side_effect = [
            {"items": [{"snippet": {"title": "Large course"}}]},
            {"items": playlist_entries, "nextPageToken": "ignored-after-cap"},
            {"items": []},
            {"items": []},
            {"items": []},
            {"items": []},
        ]

        result = fetch_youtube_playlist(
            "https://www.youtube.com/playlist?list=PLabc123"
        )

        self.assertEqual(len(result["videos"]), 200)
        self.assertEqual(api_get.call_count, 6)

    @override_settings(YOUTUBE_API_KEY="")
    def test_missing_api_key_reports_configuration_error(self):
        with self.assertRaisesMessage(YouTubeImportError, "YOUTUBE_API_KEY"):
            fetch_youtube_playlist(
                "https://www.youtube.com/playlist?list=PLabc123"
            )


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