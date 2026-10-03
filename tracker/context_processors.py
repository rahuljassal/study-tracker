import os


def oauth_providers(request):
    connected_social_providers = set()
    resolver_match = getattr(request, "resolver_match", None)
    if (
        request.user.is_authenticated
        and resolver_match
        and resolver_match.url_name == "socialaccount_connections"
    ):
        connected_social_providers = set(
            request.user.socialaccount_set.values_list("provider", flat=True)
        )
    return {
        "google_oauth_configured": bool(
            os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET")
        ),
        "github_oauth_configured": bool(
            os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET")
        ),
        "connected_social_providers": connected_social_providers,
    }