"""Upload rules an Administrator can change on Administration > Uploads (stored in SystemConfiguration):
the largest document and profile photo (in KB), files per upload, and which kinds of file are accepted.
The web proxy rejects any single request over 40 MB, so files-per-upload x size-per-file may not exceed that."""
from django.conf import settings

from .models import SystemConfiguration

PROXY_LIMIT_KB = 40 * 1024
BOUNDS = {"upload_max_kb": (50, 20480), "upload_max_files": (1, 10), "photo_max_kb": (50, 5120)}

# group key -> (label, extensions)
TYPE_GROUPS = {
    "pdf": ("PDF", ["pdf"]),
    "image": ("Images (JPG, PNG)", ["jpg", "jpeg", "png"]),
    "word": ("Word documents", ["doc", "docx"]),
    "excel": ("Excel spreadsheets", ["xls", "xlsx"]),
    "powerpoint": ("PowerPoint", ["ppt", "pptx"]),
    "text": ("Text and CSV", ["txt", "csv"]),
    "audio": ("Audio (MP3)", ["mp3"]),
    "video": ("Video (MP4)", ["mp4"]),
}
DEFAULT_TYPES = ["pdf", "image", "word", "excel", "text", "audio", "video"]


def _int(key, default):
    try:
        return int(SystemConfiguration.get(key, "") or default)
    except ValueError:
        return default


def get_limits():
    raw = SystemConfiguration.get("upload_types", "")
    groups = [g for g in raw.split(",") if g in TYPE_GROUPS] or DEFAULT_TYPES
    return {
        "upload_max_kb": _int("upload_max_kb", getattr(settings, "ATTACHMENT_MAX_MB", 5) * 1024),
        "upload_max_files": _int("upload_max_files", getattr(settings, "ATTACHMENT_MAX_FILES", 5)),
        "photo_max_kb": _int("photo_max_kb", 5120),
        "upload_types": groups,
        "allowed_extensions": [e for g in groups for e in TYPE_GROUPS[g][1]],
        "type_catalog": [{"key": k, "label": v[0], "extensions": v[1]} for k, v in TYPE_GROUPS.items()],
    }


def validate_limits(values):
    """Return {field: message} for any value out of range, including the combined-size cap."""
    errors = {}
    for key, (lo, hi) in BOUNDS.items():
        if key in values and not (isinstance(values[key], int) and not isinstance(values[key], bool) and lo <= values[key] <= hi):
            errors[key] = f"Enter a whole number of KB from {lo} to {hi} ({hi // 1024} MB)." if key != "upload_max_files" else f"Enter a whole number from {lo} to {hi}."
    if "upload_types" in values:
        t = values["upload_types"]
        if not (isinstance(t, list) and t and all(x in TYPE_GROUPS for x in t)):
            errors["upload_types"] = "Choose at least one kind of file."
    if not errors:
        merged = {**get_limits(), **{k: v for k, v in values.items() if k in BOUNDS}}
        if merged["upload_max_kb"] * merged["upload_max_files"] > PROXY_LIMIT_KB:
            errors["upload_max_files"] = f"Files per upload times size per file cannot exceed {PROXY_LIMIT_KB // 1024} MB in total."
    return errors


def save_limits(values):
    for key in BOUNDS:
        if key in values:
            SystemConfiguration.objects.update_or_create(key=key, defaults={"value": str(values[key]), "description": "Upload limit"})
    if "upload_types" in values:
        SystemConfiguration.objects.update_or_create(key="upload_types", defaults={"value": ",".join(values["upload_types"]), "description": "Accepted kinds of file"})


def human(kb):
    return f"{kb / 1024:g} MB" if kb >= 1024 else f"{kb} KB"
