"""Writers for the API, email and SMS logs. Logging must never break the request it describes."""
import logging
import re

from django.db import transaction

from .models import ApiLog, EmailLog

log = logging.getLogger(__name__)

_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_LONG_DIGITS = re.compile(r"\d{9,}")


def clean_path(path):
    """Path only (never the query string); long digit runs such as a CID are masked."""
    return _LONG_DIGITS.sub(lambda m: "*" * (len(m.group()) - 4) + m.group()[-4:], path.split("?")[0])[:300]


def api_call(service, method, path, status, duration_ms, error=""):
    try:
        with transaction.atomic():
            ApiLog.objects.create(direction="out", service=service[:10], method=method[:8], path=clean_path(path), status=status or 0,
                                  duration_ms=max(0, int(duration_ms)), error=error[:300])
    except Exception:  # pragma: no cover
        log.exception("Could not write the API log")


def email(kind, recipient, subject, ok, error="", reference="", notification=None):
    try:
        with transaction.atomic():
            EmailLog.objects.create(kind=kind[:40], recipient=recipient[:254], subject=subject[:300],
                                status="sent" if ok else "failed", error=error[:300], reference=reference[:40], notification=notification)
    except Exception:  # pragma: no cover
        log.exception("Could not write the email log")
