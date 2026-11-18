"""Upload limits an Administrator can change on the Settings page (stored in SystemConfiguration).
The web proxy rejects any single request over 40 MB, so files-per-upload x size-per-file may not exceed that."""
from django.conf import settings

from .models import SystemConfiguration

PROXY_LIMIT_MB = 40
BOUNDS = {"upload_max_mb": (1, 20), "upload_max_files": (1, 10), "photo_max_kb": (50, 5120)}


def _int(key, default):
    try:
        return int(SystemConfiguration.get(key, "") or default)
    except ValueError:
        return default


def get_limits():
    return {
        "upload_max_mb": _int("upload_max_mb", getattr(settings, "ATTACHMENT_MAX_MB", 5)),
        "upload_max_files": _int("upload_max_files", getattr(settings, "ATTACHMENT_MAX_FILES", 5)),
        "photo_max_kb": _int("photo_max_kb", 5120),
    }


def validate_limits(values):
    """Return {field: message} for any value out of range, including the combined-size cap."""
    errors = {}
    for key, (lo, hi) in BOUNDS.items():
        if key in values and not (isinstance(values[key], int) and not isinstance(values[key], bool) and lo <= values[key] <= hi):
            unit = "KB" if key.endswith("kb") else "MB" if key.endswith("mb") else "files"
            errors[key] = f"Enter a whole number from {lo} to {hi} {unit}."
    if not errors:
        merged = {**get_limits(), **values}
        if merged["upload_max_mb"] * merged["upload_max_files"] > PROXY_LIMIT_MB:
            errors["upload_max_files"] = f"Files per upload times size per file cannot exceed {PROXY_LIMIT_MB} MB in total."
    return errors


def save_limits(values):
    for key in BOUNDS:
        if key in values:
            SystemConfiguration.objects.update_or_create(key=key, defaults={"value": str(values[key]), "description": "Upload limit"})
