# Implementation Status

## Current checkpoint

- Phase: 1 of 4, foundation and account privacy
- Status: Phase 1 validated; explicit Google-to-GitHub account linking UI implemented, awaiting user OAuth acceptance
- Last updated: 2026-10-03

## Completed

- Reviewed the local prototype and preserved `study_tracker.py` and `tracker.db`.
- Added Django project configuration, PostgreSQL URL support, static-file middleware, allauth Google/GitHub provider configuration, and a local environment template.
- Added owner-linked playlist/video models, a login-protected dashboard, and idempotent generic starter-plan provisioning.
- Added a custom social sign-in page that only shows providers with credentials configured in the environment.
- Added an initial migration, focused Phase 1 tests, local `.env` loading, and a README with startup and OAuth callback instructions.
- Created project-local `.venv` and verified that Django commands work with `.venv/bin/python`.
- Added the migration package marker after discovering Django otherwise treated `tracker` as unmigrated.
- Registered the project-level `static/` directory after browser inspection found the CSS was returning 404.
- Started the local development server at `http://127.0.0.1:8000/`; browser shows the Google sign-in button, confirming Google credentials are detected without exposing their values.
- Confirmed both `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` are set without printing their values; after reload, the sign-in page shows both Google and GitHub buttons.
- Server log confirms the Google callback completed and redirected to the dashboard; user signed out afterward.
- Added a signed-in account connections page and header link so users can explicitly attach a second OAuth provider to the current user account.
- Added connected-provider detection so the page offers only providers not already linked.
- Added tests confirming the connections page requires authentication and displays both configured provider connection actions.
- Added a separate `socialaccount/signup.html` override for `/accounts/3rdparty/signup/`, with the shared auth styling, provider-aware guidance, and a route back to the existing-account linking flow.

## Files changed

- `manage.py`, `requirements.txt`, `.env.example`, `.gitignore`
- `studytracker/` project settings, URL configuration, and WSGI entry point
- `tracker/` app models, view, onboarding helper, app config, and OAuth context processor
- `tracker/migrations/0001_initial.py`, `tracker/tests.py`
- `templates/` base, login, and dashboard templates
- `templates/socialaccount/connections.html`
- `templates/socialaccount/login.html`, `templates/socialaccount/signup.html`
- `static/tracker/app.css`
- `tracker/context_processors.py`, `tracker/tests.py`
- `README.md`, `IMPLEMENTATION_STATUS.md`
- `.venv/` (ignored local environment; no environment binaries should be committed)

## Validation

- Dependency installation: Django, django-allauth, psycopg, WhiteNoise, and Gunicorn installed in the selected Python environment.
- Syntax checks: passed for `tracker/tests.py`, `studytracker/settings.py`, `tracker/migrations/0001_initial.py`, `tracker/onboarding.py`, `tracker/views.py`, and `manage.py` using Pylance file-syntax diagnostics.
- The shell's base Conda `python` does not have Django. Use the project virtual environment command `.venv/bin/python` for this project.
- `.venv/bin/python manage.py check`: passed.
- `.venv/bin/python manage.py makemigrations --check --dry-run`: passed (`No changes detected`).
- `.venv/bin/python manage.py showmigrations tracker`: discovered `0001_initial`.
- `.venv/bin/python manage.py migrate`: passed; tracker schema applied to Django's local `db.sqlite3`.
- `.venv/bin/python manage.py test tracker -v 1`: passed, 7 tests after adding account-connection and social-signup template coverage.
- After registering project-level static files, `.venv/bin/python manage.py check` and `.venv/bin/python manage.py test tracker -v 1` both passed again; login page stylesheet now loads without 404s.
- Test execution emits a non-fatal WhiteNoise warning that `staticfiles/` has not yet been collected; run `collectstatic` for production/static deployment.
- Google OAuth: local callback completed successfully.
- GitHub OAuth: client ID and secret are detected and its button renders; direct sign-in to an existing Google account with the same email correctly goes through allauth's signup guard because providers are not automatically merged by email.
- Secure linking path is implemented: sign into the established account with Google, open **Connected accounts** in the header, then choose **Connect GitHub** while authenticated. Complete GitHub consent to attach it to that same Study Tracker user.

## Known constraints

- Core playlist CRUD/progress workflows are intentionally deferred to Phase 2.
- The generic starter plan currently contains editable learning steps without video URLs; tracker workflow work can refine presentation in Phase 2.
- Existing SQLite data is not imported; `.gitignore` excludes both the prototype `tracker.db` and Django's local `db.sqlite3`.
- User has not yet completed a GitHub provider connection round-trip. Connect it from the authenticated **Connected accounts** page; then sign out and verify both providers reach the same dashboard/account.
- The account signup, social provider confirmation, social signup, and connected-accounts routes each use the Study Tracker layout.

## Resume instruction

Read this file first. Use `.venv/bin/python` (or activate `.venv`) to run the app. Phase 1 code and automated checks are complete; ask the user to test Google OAuth and the dashboard, then pause for feedback. Do not start Phase 2 until the user explicitly asks to continue.

## Next action

- User acceptance: sign in with Google, open **Connected accounts**, connect GitHub, then sign out and confirm GitHub returns to the same dashboard. Record outcome and ask whether to begin Phase 2.
