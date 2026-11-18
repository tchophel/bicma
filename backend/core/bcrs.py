"""CID lookup against the BCRS API. Configured entirely from the environment:

BCRS_API_URL     full URL; use {cid} as the placeholder, e.g. https://host/citizen/{cid}
                 (without {cid}, the CID is sent as ?cid=...)
BCRS_API_METHOD  GET (default) or POST (CID sent as JSON {"cid": ...})
BCRS_AUTH_HEADER header name for the credential (default Authorization)
BCRS_API_TOKEN   credential value, sent as-is in that header (include "Bearer " yourself if needed)
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)


class NotConfigured(Exception):
    pass


def _find(obj, key):
    """First value for `key` anywhere in a nested JSON structure (case-insensitive)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() == key.lower():
                return v
        for v in obj.values():
            found = _find(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find(v, key)
            if found is not None:
                return found
    return None


def lookup(cid):
    """Return {"first_name", "middle_name", "last_name", "full_name"} or None if the CID is not found."""
    url = getattr(settings, "BCRS_API_URL", "")
    if not url:
        raise NotConfigured()
    method = (getattr(settings, "BCRS_API_METHOD", "GET") or "GET").upper()
    headers = {"Accept": "application/json"}
    token = getattr(settings, "BCRS_API_TOKEN", "")
    if token:
        headers[getattr(settings, "BCRS_AUTH_HEADER", "Authorization") or "Authorization"] = token
    data = None
    if "{cid}" in url:
        url = url.replace("{cid}", urllib.parse.quote(cid, safe=""))
    elif method == "GET":
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"cid": cid})
    if method == "POST":
        data = json.dumps({"cid": cid}).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 404):
            return None
        log.error("BCRS lookup failed with HTTP %s", exc.code)
        raise
    first, middle, last = (_find(body, k) for k in ("firstName", "middleName", "lastName"))
    if not first and not last:
        return None
    parts = [str(x).strip() for x in (first, middle, last) if x]  # middleName is often null
    return {"first_name": first or "", "middle_name": middle or "", "last_name": last or "", "full_name": " ".join(parts)}
