from django import forms

from tracker.models import Playlist
from tracker.services import parse_video_lines


class PlaylistForm(forms.ModelForm):
    videos_text = forms.CharField(
        label="Videos (optional)",
        required=False,
        help_text="One per line: title | duration | URL. You can also add videos later.",
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
        self.fields["videos_per_day"].min_value = 1
        self.fields["videos_per_day"].max_value = 100
        if not include_videos:
            self.fields.pop("videos_text")

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