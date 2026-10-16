import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

from django.conf import settings


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
MAX_IMPORTED_VIDEOS = 200
PAGE_SIZE = 50
VIDEO_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
DURATION_PATTERN = re.compile(
    r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?\Z"
)


class YouTubeImportError(Exception):
    """An expected, user-displayable playlist import failure."""


def extract_playlist_id(playlist_url):
    try:
        parsed = urlparse(playlist_url.strip())
        host = (parsed.hostname or "").lower()
    except ValueError as exc:
        raise YouTubeImportError("Enter a valid YouTube playlist URL.") from exc

    allowed_hosts = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }
    if parsed.scheme not in {"http", "https"} or host not in allowed_hosts:
        raise YouTubeImportError("Enter a valid YouTube playlist URL.")

    if parsed.path not in {"/playlist", "/watch", "/embed/videoseries", "/"}:
        raise YouTubeImportError("Enter a YouTube playlist URL, not a video or channel URL.")

    playlist_id = parse_qs(parsed.query).get("list", [""])[0]
    if not playlist_id or not VIDEO_ID_PATTERN.fullmatch(playlist_id):
        raise YouTubeImportError("That URL does not contain a valid YouTube playlist ID.")
    return playlist_id


def _api_error_reason(error):
    try:
        payload = json.loads(error.read().decode("utf-8"))
        return payload["error"]["errors"][0]["reason"]
    except (UnicodeDecodeError, ValueError, KeyError, IndexError, TypeError):
        return ""


def _api_failure(reason=""):
    if reason in {"quotaExceeded", "dailyLimitExceeded"}:
        return YouTubeImportError(
            "YouTube API quota has been exceeded. Please try again later."
        )
    if reason == "playlistNotFound":
        return YouTubeImportError(
            "This playlist was not found. It may be deleted or unavailable."
        )
    if reason in {"playlistItemsNotAccessible", "forbidden"}:
        return YouTubeImportError(
            "This playlist is private or unavailable. Only public playlists can be imported."
        )
    if reason in {"keyInvalid", "accessNotConfigured", "youtubeSignupRequired"}:
        return YouTubeImportError(
            "YouTube import is not configured correctly. Check the API key and YouTube Data API v3 access."
        )
    return YouTubeImportError(
        "YouTube could not return this playlist. Check that it is public and try again."
    )


def _youtube_api_get(resource, params):
    api_key = getattr(settings, "YOUTUBE_API_KEY", "")
    if not api_key:
        raise YouTubeImportError(
            "YouTube import is not configured. Set YOUTUBE_API_KEY on the server."
        )

    query = urlencode({**params, "key": api_key})
    request_url = f"{YOUTUBE_API_BASE}/{resource}?{query}"
    try:
        with urlopen(request_url, timeout=10) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise _api_failure(_api_error_reason(exc)) from None
    except (URLError, TimeoutError):
        raise YouTubeImportError(
            "Could not connect to YouTube. Please try again."
        ) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise YouTubeImportError(
            "YouTube returned an unexpected response. Please try again."
        ) from None

    if not isinstance(payload, dict):
        raise YouTubeImportError(
            "YouTube returned an unexpected response. Please try again."
        )
    return payload


def _response_items(payload):
    items = payload.get("items")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise YouTubeImportError(
            "YouTube returned an unexpected response. Please try again."
        )
    return items


def _duration_seconds(value):
    if not isinstance(value, str):
        return 0
    match = DURATION_PATTERN.fullmatch(value or "")
    if not match:
        return 0
    parts = {name: int(amount or 0) for name, amount in match.groupdict().items()}
    return (
        parts["days"] * 86400
        + parts["hours"] * 3600
        + parts["minutes"] * 60
        + parts["seconds"]
    )


def fetch_youtube_playlist(playlist_url):
    playlist_id = extract_playlist_id(playlist_url)
    playlist_response = _youtube_api_get(
        "playlists",
        {"part": "snippet", "id": playlist_id, "maxResults": 1},
    )
    playlist_items = _response_items(playlist_response)
    if not playlist_items:
        raise YouTubeImportError(
            "This playlist was not found. It may be private, deleted, or unavailable."
        )

    playlist_snippet = playlist_items[0].get("snippet")
    if not isinstance(playlist_snippet, dict):
        playlist_snippet = {}
    playlist_title = playlist_snippet.get("title")
    playlist_title = playlist_title.strip() if isinstance(playlist_title, str) else ""
    if not playlist_title:
        raise YouTubeImportError("YouTube did not provide a title for this playlist.")

    entries = []
    page_token = None
    seen_page_tokens = set()
    while len(entries) < MAX_IMPORTED_VIDEOS:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": PAGE_SIZE,
        }
        if page_token:
            params["pageToken"] = page_token
        page = _youtube_api_get("playlistItems", params)
        for item in _response_items(page):
            content_details = item.get("contentDetails")
            if not isinstance(content_details, dict):
                content_details = {}
            resource = content_details.get("videoId")
            snippet = item.get("snippet")
            if not isinstance(snippet, dict):
                snippet = {}
            if not resource:
                resource_id = snippet.get("resourceId")
                if isinstance(resource_id, dict):
                    resource = resource_id.get("videoId")
            if isinstance(resource, str) and VIDEO_ID_PATTERN.fullmatch(resource):
                entries.append(item)
                if len(entries) == MAX_IMPORTED_VIDEOS:
                    break

        next_token = page.get("nextPageToken")
        if len(entries) >= MAX_IMPORTED_VIDEOS or not next_token:
            break
        if not isinstance(next_token, str) or next_token in seen_page_tokens:
            raise YouTubeImportError(
                "YouTube returned an invalid playlist page. Please try again."
            )
        seen_page_tokens.add(next_token)
        page_token = next_token

    if not entries:
        raise YouTubeImportError("This playlist does not contain any available videos.")

    video_details = {}
    video_ids = []
    for item in entries:
        content_details = item.get("contentDetails")
        if not isinstance(content_details, dict):
            content_details = {}
        video_id = content_details.get("videoId")
        if not video_id:
            snippet = item.get("snippet")
            resource_id = snippet.get("resourceId") if isinstance(snippet, dict) else None
            video_id = resource_id.get("videoId") if isinstance(resource_id, dict) else None
        video_ids.append(video_id)

    for offset in range(0, len(video_ids), PAGE_SIZE):
        response = _youtube_api_get(
            "videos",
            {
                "part": "snippet,contentDetails",
                "id": ",".join(video_ids[offset : offset + PAGE_SIZE]),
                "maxResults": PAGE_SIZE,
            },
        )
        for video in _response_items(response):
            video_id = video.get("id")
            if video_id:
                video_details[video_id] = video

    videos = []
    for item, video_id in zip(entries, video_ids):
        detail = video_details.get(video_id, {})
        detail_snippet = detail.get("snippet", {})
        detail_content = detail.get("contentDetails", {})
        fallback_snippet = item.get("snippet")
        if not isinstance(detail_snippet, dict):
            detail_snippet = {}
        if not isinstance(detail_content, dict):
            detail_content = {}
        if not isinstance(fallback_snippet, dict):
            fallback_snippet = {}
        title = detail_snippet.get("title") or fallback_snippet.get("title")
        title = title.strip() if isinstance(title, str) else "Unavailable video"
        title = title[:200] or "Unavailable video"
        videos.append(
            {
                "title": title,
                "duration_seconds": _duration_seconds(detail_content.get("duration")),
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )

    return {"name": playlist_title[:120], "videos": videos}
