"""Save disk space once a complaint is resolved: shrink the pictures attached to it.

Only pictures (JPEG, PNG, WebP) of complaints that are Resolved, Closed or Not within mandate are touched, once each.
A picture is scaled down to at most MAX_SIDE pixels on its longest side and re-saved at a lower quality (PNG stays
lossless). The result replaces the original only when it is at least MIN_SAVING smaller. Text and PDF documents are
left exactly as uploaded. The original picture is not kept, so what was shown is still readable but not pixel-identical.
"""
import io
import os

from django.core.files.base import ContentFile
from django.utils import timezone

from core.models import SystemConfiguration

from .models import Attachment, FollowUpFile, InternalStatus

SETTING = "compress_resolved_files"
MAX_SIDE = 2560
QUALITY = 80
MIN_SAVING = 0.10
DONE_STATUSES = (InternalStatus.RESOLVED, InternalStatus.CLOSED, InternalStatus.NOT_WITHIN_MANDATE)
TYPES = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def enabled():
    return SystemConfiguration.get(SETTING, "1") == "1"


def set_enabled(on):
    SystemConfiguration.objects.update_or_create(key=SETTING, defaults={"value": "1" if on else "0", "description": "Shrink pictures of resolved complaints every day"})


def _pending():
    a = Attachment.objects.filter(complaint__internal_status__in=DONE_STATUSES, compressed_at__isnull=True, content_type__in=TYPES)
    f = FollowUpFile.objects.filter(followup__complaint__internal_status__in=DONE_STATUSES, compressed_at__isnull=True, content_type__in=TYPES)
    return a.select_related("complaint"), f


def waiting():
    a, f = _pending()
    return {"files": a.count() + f.count(), "bytes": sum(a.values_list("size", flat=True)) + sum(f.values_list("size", flat=True))}


def saved():
    total = files = 0
    for model in (Attachment, FollowUpFile):
        for orig, now in model.objects.filter(compressed_at__isnull=False, original_size__isnull=False).values_list("original_size", "size"):
            if orig > now:
                total += orig - now
                files += 1
    return {"files": files, "bytes": total}


def shrink(data, fmt):
    """Return smaller bytes for this picture, or None when it cannot or need not be shrunk."""
    from PIL import Image, ImageOps
    img = Image.open(io.BytesIO(data))
    if getattr(img, "n_frames", 1) > 1:  # animated
        return None
    img = ImageOps.exif_transpose(img)  # apply the camera rotation, because the metadata is dropped below
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    elif fmt == "PNG":
        img.save(out, "PNG", optimize=True)
    else:
        img.save(out, "WEBP", quality=QUALITY, method=6)
    smaller = out.getvalue()
    return smaller if len(smaller) <= len(data) * (1 - MIN_SAVING) else None


def run(limit=500):
    """Shrink up to `limit` waiting pictures. The new file is written first, the rows are pointed at it, then the old one is deleted."""
    a, f = _pending()
    done = {"checked": 0, "shrunk": 0, "bytes_saved": 0, "failed": 0}
    rows = list(a[:limit]) + list(f[:max(0, limit - done["checked"])])
    by_name = {}
    for row in rows:
        by_name.setdefault(row.file.name, []).append(row)  # a follow-up can share the file of an attachment
    for name, group in by_name.items():
        first = group[0]
        done["checked"] += len(group)
        try:
            with first.file.storage.open(name, "rb") as fh:
                data = fh.read()
            new = shrink(data, TYPES[first.content_type])
        except Exception:
            done["failed"] += len(group)
            continue
        now = timezone.now()
        if new is None:
            for r in group:
                r.compressed_at = now
                r.original_size = r.size
                r.save(update_fields=["compressed_at", "original_size"])
            continue
        every = [*Attachment.objects.filter(file=name), *FollowUpFile.objects.filter(file=name)]  # every row using this file
        new_name = first.file.storage.save(os.path.join(os.path.dirname(name), f"c-{os.path.basename(name)}"), ContentFile(new))
        for r in every:
            r.file.name = new_name
            r.original_size = r.size
            r.size = len(new)
            r.compressed_at = now
            r.save(update_fields=["file", "size", "original_size", "compressed_at"])
        first.file.storage.delete(name)
        done["shrunk"] += len(every)
        done["bytes_saved"] += (len(data) - len(new)) * len(every)
    return done
