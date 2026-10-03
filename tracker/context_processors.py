import os


def oauth_providers(request):
    return {
        "google_oauth_configured": bool(
            os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET")
        ),
        "github_oauth_configured": bool(
            os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET")
        ),
    }