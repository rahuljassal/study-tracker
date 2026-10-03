from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from tracker.onboarding import provision_starter_plan


@login_required
def dashboard(request):
    provision_starter_plan(request.user)
    playlists = request.user.playlists.prefetch_related("videos").all()
    return render(request, "tracker/dashboard.html", {"playlists": playlists})