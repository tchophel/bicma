"""Reachability checks for the external APIs this system depends on. They feed the up/down graph on Logs > API."""
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

from .models import ApiHealthCheck

SERVICES = [("dcrc", "DCRC citizen details (BCRS)"), ("zest", "ZESt employee directory")]
LABELS = dict(SERVICES)
DUMMY_CID = "00000000000"  # a CID that matches nobody: a "not found" answer still proves the API is up


def configured(service):
    if service == "dcrc":
        return bool(settings.BCRS_API_URL)
    if service == "zest":
        return bool(settings.ZEST_API_URL)
    return False


def _check_dcrc():
    from . import bcrs
    bcrs.lookup(DUMMY_CID)  # raises on timeouts, 5xx and rejected credentials; a 404 for the dummy CID means "up"


def _check_zest():
    headers = {"Accept": "application/json"}
    if settings.ZEST_API_TOKEN:
        headers[settings.ZEST_AUTH_HEADER or "Authorization"] = settings.ZEST_API_TOKEN
    try:
        urllib.request.urlopen(urllib.request.Request(settings.ZEST_API_URL, headers=headers), timeout=8).close()
    except urllib.error.HTTPError as exc:
        if exc.code >= 500 or exc.code in (401, 403):
            raise


def check(service):
    """Run one check and store it. Returns the saved ApiHealthCheck, or None if the service is not configured."""
    if not configured(service):
        return None
    start = time.monotonic()
    ok, status, error = True, 200, ""
    try:
        {"dcrc": _check_dcrc, "zest": _check_zest}[service]()
    except urllib.error.HTTPError as exc:
        ok, status, error = False, exc.code, f"HTTP {exc.code}"
    except Exception as exc:
        ok, status, error = False, 0, f"{type(exc).__name__}: {exc}"[:300]
    return ApiHealthCheck.objects.create(service=service, ok=ok, status=status, error=error[:300],
                                         latency_ms=int((time.monotonic() - start) * 1000))


def check_all():
    return [c for c in (check(s) for s, _ in SERVICES) if c]


def summary(hours=24, max_points=400):
    """Per service: current state, uptime, latency and the checks in the window (thinned to max_points)."""
    import datetime as dt
    since = timezone.now() - dt.timedelta(hours=hours)
    out = []
    for key, label in SERVICES:
        qs = ApiHealthCheck.objects.filter(service=key, checked_at__gte=since).order_by("checked_at")
        rows = list(qs.values_list("checked_at", "ok", "latency_ms", "status", "error"))
        total = len(rows)
        ups = sum(1 for r in rows if r[1])
        latest = ApiHealthCheck.objects.filter(service=key).order_by("-checked_at").first()
        step = max(1, -(-total // max_points))
        # thinned series: keep every failure so a short outage is never hidden by thinning
        series = [r for i, r in enumerate(rows) if i % step == 0 or not r[1]]
        # incidents: stretches of consecutive failed checks
        incidents, current = [], None
        for t, ok, ms, st, err in rows:
            if not ok and current is None:
                current = {"from": t, "to": t, "error": err}
            elif not ok:
                current["to"] = t
            elif current is not None:
                incidents.append({**current, "recovered_at": t}); current = None
        if current:
            incidents.append({**current, "recovered_at": None})
        out.append({
            "service": key, "label": label, "configured": configured(key),
            "state": "not_configured" if not configured(key) else ("no_data" if latest is None else ("up" if latest.ok else "down")),
            "last_checked": latest.checked_at if latest else None, "last_error": latest.error if latest and not latest.ok else "",
            "checks": total, "uptime_pct": round(100 * ups / total, 2) if total else None,
            "avg_ms": round(sum(r[2] for r in rows if r[1]) / ups) if ups else None,
            "incidents": incidents[-10:],
            "series": [{"t": t, "ok": ok, "ms": ms, "status": st, "error": err} for t, ok, ms, st, err in series],
        })
    return out
