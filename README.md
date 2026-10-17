# Study Tracker

A personal learning-plan tracker being developed as a multi-user Django web app. Each signed-in user owns their playlists and progress. The original local prototype remains in `study_tracker.py`; this Django app uses its own `db.sqlite3` for local development.

## Local setup

Use Python 3.11 or newer. From the project directory:

```sh
.venv/bin/python manage.py check
DATABASE_URL= .venv/bin/python manage.py test tracker
DATABASE_URL= .venv/bin/python manage.py migrate
DATABASE_URL= .venv/bin/python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Until a social provider is configured, the sign-in page explains that setup is needed.

The blank `DATABASE_URL` prefix in the test command keeps automated tests on local SQLite even if `.env` points to Render. Do not run Django's test suite against your hosted PostgreSQL database.

## Local social sign-in

Create OAuth apps with Google and/or GitHub, then put each client ID and secret in `.env`. Never commit `.env` or provider secrets.

Use these callback URLs in the provider settings:

- Google: `http://127.0.0.1:8000/accounts/google/login/callback/`
- GitHub: `http://127.0.0.1:8000/accounts/github/login/callback/`

Restart the development server after changing `.env`. OAuth flows cannot be completed until valid provider credentials are configured.

## Playlist workflows

After signing in, use **New playlist** to create a plan, optionally paste video lines, and open a playlist to add steps or mark them complete. The dashboard provides edit and delete actions. Playlist reads and mutations are scoped to the signed-in owner. The prototype's `tracker.db` is not imported automatically.

The playlist list and detail page show a dynamic estimated end date based on the configured videos-per-day pace and the number of videos still pending. Completing more videos shortens the estimate without changing the configured pace; changing completion status, adding videos, or changing the daily pace updates it. A completed plan shows the date its last video was completed; an empty plan has no estimate. Video durations display in minutes and seconds when available.

The dashboard and playlist detail also show today's scheduled videos, how many of those are complete, and how many remain. Videos are scheduled in playlist order, in daily batches based on the playlist start date and videos-per-day setting. The dashboard also shows an accessible completion progress bar and the remaining-video count for each playlist.

At the top of the dashboard, an overall pie-style chart aggregates completed and remaining videos across all of the signed-in user's playlists.

On a playlist detail page, videos can be marked complete and dragged by their handle to change their schedule order. To change playlist contents, update playlist settings or add videos.

To create a playlist from a public YouTube playlist, enter its playlist URL on **New playlist**. Leave the playlist name blank to use YouTube's title; the importer adds up to the first 200 available videos, including their durations and watch URLs. Pasted video lines remain available as an alternative, but cannot be combined with a YouTube URL in the same submission. Private or unavailable playlists cannot be imported.

Enable **YouTube Data API v3** in Google Cloud and set `YOUTUBE_API_KEY` in local `.env` and the Render web service environment. Keep the key private; the server uses it only for API requests. The import form reports missing configuration, quota exhaustion, and unavailable playlists without exposing the key.

## Response performance

The pages are small server-rendered HTML; the sign-in page is about 840 bytes, so HTML response structure is not the main latency source. Provider button rendering previously caused avoidable allauth database lookups; the page now links directly to the local allauth routes. Connected-provider lookup is limited to the connections page, and the starter-plan existence check is cached in the signed-in session.

For the Render deployment, place the web service and PostgreSQL database in the same region and use Render's **Internal Database URL** in the web service environment. Use the **External Database URL** only when connecting from your laptop for manual testing; the extra network round-trip makes local requests slower. Warm local measurements after this change were around 1–2 ms TTFB for the sign-in page, but first requests and requests to a remote database can be slower. Measure production after deployment before considering a separate JSON API or frontend rewrite.

## Test local CRUD against Render PostgreSQL

To make browser actions from your laptop write to the hosted database, set `DATABASE_URL` in your local `.env` to Render's **External Database URL**. Do not use Render's Internal URL from a laptop. Keep the URL private and never commit `.env`.

Check connectivity and schema without showing the URL:

```sh
.venv/bin/python manage.py check --database default
.venv/bin/python manage.py showmigrations tracker
```

Then start the local app:

```sh
.venv/bin/python manage.py runserver
```

Sign in and create a clearly named temporary playlist, add a step, edit the playlist settings, mark the step complete, refresh to confirm persistence, then delete the temporary playlist. These actions go to the configured database, so use test data and avoid other users' records.

To inspect your records from Django's shell, use your account's email locally (do not share it in chat):

```python
from django.contrib.auth import get_user_model
from tracker.models import Playlist, Video

user = get_user_model().objects.get(email="your-oauth-email")
list(Playlist.objects.filter(owner=user).values("id", "name", "start_date", "videos_per_day"))
list(Video.objects.filter(playlist__owner=user).values("id", "playlist_id", "title", "completed_at"))
```

Start the shell with `.venv/bin/python manage.py shell`. Do not run `manage.py test` with the Render URL active; automated tests create and destroy a test database.

## Production security settings

In the Render web service environment, set `DEBUG=0`, a long random `SECRET_KEY`, `ALLOWED_HOSTS` to the deployed hostname without a scheme, `CSRF_TRUSTED_ORIGINS` to the HTTPS origin, and the database and OAuth credentials. Keep secrets in Render's environment settings. The app enables HTTPS redirects, secure cookies, HSTS, and a strict referrer policy in production. HSTS subdomain and preload options remain off unless every relevant hostname is HTTPS-ready.

For cross-tool handoff and phase status, read [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) before continuing implementation.
