from django import forms

from tracker.models import Playlist
from tracker.services import parse_video_lines


class PlaylistForm(forms.ModelForm):
    youtube_playlist_url = forms.CharField(
        label="YouTube playlist URL (optional)",
        required=False,
        max_length=500,
        help_text=(
            "Import up to 200 videos from a public playlist. Leave the playlist "
            "name blank to use the YouTube playlist title."
        ),
        widget=forms.URLInput(
            attrs={
                "placeholder": "https://www.youtube.com/playlist?list=...",
                "spellcheck": "false",
            }
        ),
    )
    videos_text = forms.CharField(
        label="Videos (optional)",
        required=False,
        help_text=(
            "Fallback/manual entry: one per line as title | duration | URL. "
            "Use either this or a YouTube playlist URL, not both."
        ),
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Lesson 1 | 12:34 | https://example.com/video",
                "spellcheck": "false",
            }
        ),
    )

    class Meta:
        model = Playlist
        fields = ["name", "start_date", "videos_per_day"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "name": "Playlist name",
            "start_date": "Start date",
            "videos_per_day": "Videos per day",
        }

    def __init__(self, *args, include_videos=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = False
        self.fields["videos_per_day"].min_value = 1
        self.fields["videos_per_day"].max_value = 100
        if not include_videos:
            self.fields.pop("youtube_playlist_url")
            self.fields.pop("videos_text")

    def clean(self):
        cleaned_data = super().clean()
        youtube_playlist_url = cleaned_data.get("youtube_playlist_url", "").strip()
        videos_text = cleaned_data.get("videos_text", "")
        name = cleaned_data.get("name", "").strip()

        if youtube_playlist_url and videos_text:
            self.add_error(
                "videos_text",
                "Choose a YouTube playlist URL or pasted videos, not both.",
            )
        if not youtube_playlist_url and not name:
            self.add_error("name", "Enter a playlist name or provide a YouTube playlist URL.")
        if youtube_playlist_url and not name:
            cleaned_data["name"] = "YouTube playlist"

        return cleaned_data

    def clean_videos_text(self):
        text = self.cleaned_data.get("videos_text", "")
        if not text.strip():
            return []
        return parse_video_lines(text)


class AddVideosForm(forms.Form):
    videos_text = forms.CharField(
        label="Paste video entries",
        help_text="One per line: title | duration | URL. Use NA when duration is unknown.",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Lesson 1 | 12:34 | https://example.com/video",
                "spellcheck": "false",
            }
        ),
    )

    def clean_videos_text(self):
        return parse_video_lines(self.cleaned_data["videos_text"])