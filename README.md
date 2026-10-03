# Study Tracker

A personal learning-plan tracker being developed as a multi-user Django web app. Each signed-in user owns their playlists and progress. The original local prototype remains in `study_tracker.py`; this Django app uses its own `db.sqlite3` for local development.

## Local setup

Use Python 3.11 or newer. From the project directory:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py test
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Until a social provider is configured, the sign-in page explains that setup is needed.

## Local social sign-in

Create OAuth apps with Google and/or GitHub, then put each client ID and secret in `.env`. Never commit `.env` or provider secrets.

Use these callback URLs in the provider settings:

- Google: `http://127.0.0.1:8000/accounts/google/login/callback/`
- GitHub: `http://127.0.0.1:8000/accounts/github/login/callback/`

Restart the development server after changing `.env`. OAuth flows cannot be completed until valid provider credentials are configured.

## Phase 1 scope

Phase 1 supplies OAuth wiring, a protected dashboard, user-owned playlist/video data models, and a generic five-step starter learning plan. Playlist editing, completion tracking, scheduling, and production deployment are later phases. New user data starts fresh; the prototype's `tracker.db` is not imported.

For cross-tool handoff and phase status, read [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) before continuing implementation.
