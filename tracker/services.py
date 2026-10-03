import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


DURATION_PATTERN = re.compile(r"(?:\d{1,3}:)?\d{1,3}:\d{2}|NA", re.IGNORECASE)
URL_VALIDATOR = URLValidator(schemes=["http", "https"])


def duration_seconds(value):
    if value.upper() == "NA":
        return 0
    parts = [int(part) for part in value.split(":")]
    if len(parts) not in (2, 3) or parts[-1] > 59:
        raise ValueError("Invalid duration")
    if len(parts) == 3 and parts[-2] > 59:
        raise ValueError("Invalid duration")
    total = 0
    for part in parts:
        total = total * 60 + part
    return total


def parse_video_lines(text):
    videos = []
    errors = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3 or not DURATION_PATTERN.fullmatch(parts[-2]):
            errors.append(f"Line {line_number}: use title | duration | URL.")
            continue
        title_parts = parts[:-2]
        if len(title_parts) > 1 and title_parts[0].isdigit():
            title_parts = title_parts[1:]
        title = " | ".join(title_parts).strip()
        url = parts[-1]
        if not title or len(title) > 200:
            errors.append(f"Line {line_number}: title must be between 1 and 200 characters.")
            continue
        try:
            URL_VALIDATOR(url)
            duration = duration_seconds(parts[-2])
        except (ValidationError, ValueError):
            errors.append(f"Line {line_number}: enter a valid HTTP/HTTPS URL and duration.")
            continue
        videos.append({"title": title, "duration_seconds": duration, "url": url})

    if len(videos) > 200:
        errors.append("A playlist can contain at most 200 videos at a time.")
    if errors:
        raise ValidationError(errors)
    return videos