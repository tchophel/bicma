"""CID lookup against the BCRS API. Configured entirely from the environment:

BCRS_API_URL     full URL; use {cid} as the placeholder, e.g. https://host/citizen/{cid}
                 (without {cid}, the CID is sent as ?cid=...)
BCRS_API_METHOD  GET (default) or POST (CID sent as JSON {"cid": ...})
BCRS_AUTH_HEADER header name for the credential (default Authorization)
BCRS_API_TOKEN   static credential, sent as-is in that header (include "Bearer " yourself if needed)

Or, for OAuth2 client credentials (WSO2), set instead:
BCRS_TOKEN_URL, BCRS_CLIENT_ID, BCRS_CLIENT_SECRET
The access token is fetched on demand, cached until shortly before it expires, and sent as "Bearer <token>".
"""
import base64
import time
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


_token = {"value": "", "expires": 0.0}


def _access_token(force=False):
    """OAuth2 client-credentials token, cached in memory per process."""
    if not force and _token["value"] and time.time() < _token["expires"]:
        return _token["value"]
    basic = base64.b64encode(f"{settings.BCRS_CLIENT_ID}:{settings.BCRS_CLIENT_SECRET}".encode()).decode()
    req = urllib.request.Request(
        settings.BCRS_TOKEN_URL, data=b"grant_type=client_credentials", method="POST",
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode())
    _token["value"] = data["access_token"]
    _token["expires"] = time.time() + max(30, int(data.get("expires_in", 300)) - 60)
    return _token["value"]


def lookup(cid, _retry=True):
    """Return {"first_name", "middle_name", "last_name", "full_name"} or None if the CID is not found."""
    url = getattr(settings, "BCRS_API_URL", "")
    if not url:
        raise NotConfigured()
    method = (getattr(settings, "BCRS_API_METHOD", "GET") or "GET").upper()
    headers = {"Accept": "application/json"}
    token = getattr(settings, "BCRS_API_TOKEN", "")
    oauth = bool(getattr(settings, "BCRS_TOKEN_URL", "") and getattr(settings, "BCRS_CLIENT_ID", ""))
    if oauth:
        headers["Authorization"] = f"Bearer {_access_token()}"
    elif token:
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
        if exc.code == 401 and oauth and _retry:  # token revoked or expired early: fetch a new one once
            _access_token(force=True)
            return lookup(cid, _retry=False)
        if exc.code in (400, 404):
            return None
        log.error("BCRS lookup failed with HTTP %s", exc.code)
        raise
    first, middle, last = (_find(body, k) for k in ("firstName", "middleName", "lastName"))
    if not first and not last:
        return None
    parts = [str(x).strip() for x in (first, middle, last) if x]  # middleName is often null
    return {"first_name": first or "", "middle_name": middle or "", "last_name": last or "", "full_name": " ".join(parts)}
