"""Bhutan NDI (National Digital Identity) verifier client, used for staff sign-in.

    1. authenticate()         -> short-lived bearer token (cached)
    2. create_proof_request() -> {thread_id, deep_link_url, proof_url}
    3. the staff member scans the QR (or opens the deep link) in the NDI wallet and shares their Foundational ID
    4. the result arrives over NATS (core/ndi_nats.py) and is written to NdiVerification
    5. the sign-in view matches the disclosed CID to an active user

Endpoints and credentials come from settings.NDI (environment variables).
"""
import base64
import io
import logging
import threading
import time
from pathlib import Path

import requests
from django.conf import settings

from . import logs

log = logging.getLogger(__name__)
_TIMEOUT = 20
_LOGO = Path(__file__).resolve().parent / "assets" / "ndi-logo.png"


class NDIError(Exception):
    """The NDI API returned an error or could not be reached."""


class AuthenticationRejected(NDIError):
    """NDI rejected the configured client credentials or authentication request."""


class NotConfigured(NDIError):
    pass


def configured():
    n = settings.NDI
    return bool(n["CLIENT_ID"] and n["CLIENT_SECRET"] and n["NATS_SEED"])


def _call(method, url, **kw):
    """requests call that records an outbound API log entry (no bodies, tokens or secrets)."""
    start = time.monotonic()
    status, error = 0, ""
    try:
        resp = requests.request(method, url, timeout=_TIMEOUT, **kw)
        status = resp.status_code
        return resp
    except requests.RequestException as exc:
        error = type(exc).__name__
        raise NDIError(f"NDI request failed: {error}") from exc
    finally:
        from urllib.parse import urlsplit
        p = urlsplit(url)
        logs.api_call("ndi", method, f"{p.netloc}{p.path}", status, (time.monotonic() - start) * 1000, error=error)


_lock = threading.Lock()
_token = {"value": None, "expires_at": 0.0}


def authenticate(force=False):
    """A valid bearer access token, refreshed shortly before it expires."""
    if not configured():
        raise NotConfigured("Bhutan NDI sign-in is not set up yet.")
    n = settings.NDI
    with _lock:
        now = time.time()
        if not force and _token["value"] and now < _token["expires_at"]:
            return _token["value"]
        resp = _call("POST", n["AUTH_ENDPOINT"], json={
            "client_id": n["CLIENT_ID"], "client_secret": n["CLIENT_SECRET"], "grant_type": n["GRANT_TYPE"]})
        if resp.status_code in (400, 401, 403):
            raise AuthenticationRejected(f"NDI authentication rejected ({resp.status_code})")
        if resp.status_code not in (200, 201):
            raise NDIError(f"NDI authentication failed ({resp.status_code})")
        data = resp.json()
        if not data.get("access_token"):
            raise NDIError("NDI authentication response had no access token")
        _token["value"] = data["access_token"]
        _token["expires_at"] = now + max(int(data.get("expires_in", 3600)) - 60, 30)
        return _token["value"]


def _proof_attributes():
    n = settings.NDI
    return [{"name": name, "restrictions": [{"schema_name": "Foundational ID", "cred_def_id": n["FOUNDATIONAL_ID_CRED_DEF_ID"]}]}
            for name in n["LOGIN_ATTRIBUTES"]]


def create_proof_request(proof_name="Sign in to BICMA CMS"):
    """Ask NDI for a proof request. Returns {thread_id, deep_link_url, proof_url}."""
    payload = {"proofName": proof_name, "purpose": "login", "proofAttributes": _proof_attributes()}
    url = f"{settings.NDI['API_HOST']}/verifier/v1/proof-request"

    def post(tok):
        return _call("POST", url, json=payload, headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})

    resp = post(authenticate())
    if resp.status_code in (401, 403):  # token went stale: refresh once
        resp = post(authenticate(force=True))
    if resp.status_code not in (200, 201):
        raise NDIError(f"NDI proof request failed ({resp.status_code})")
    data = (resp.json() or {}).get("data") or {}
    if not data.get("proofRequestThreadId"):
        raise NDIError("NDI proof request response had no thread id")
    return {"thread_id": data["proofRequestThreadId"], "deep_link_url": data.get("deepLinkURL", ""), "proof_url": data.get("proofRequestURL", "")}


def qr_data_url(content, with_logo=True):
    """PNG QR code as a data: URL, with the NDI emblem in the centre when available."""
    import qrcode
    from PIL import Image, ImageDraw
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#000000", back_color="#FFFFFF").convert("RGBA")
    if with_logo and _LOGO.exists():
        try:
            logo = Image.open(_LOGO).convert("RGBA")
            target = img.size[0] // 4
            logo = logo.resize((target, target), Image.LANCZOS)
            pad = max(target // 12, 6)
            ring = target + pad * 2
            backing = Image.new("RGBA", (ring, ring), (0, 0, 0, 0))
            ImageDraw.Draw(backing).ellipse([0, 0, ring - 1, ring - 1], fill=(255, 255, 255, 255))
            mask = Image.new("L", (target, target), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, target - 1, target - 1], fill=255)
            logo.putalpha(mask)
            img.alpha_composite(backing, ((img.size[0] - ring) // 2, (img.size[1] - ring) // 2))
            img.alpha_composite(logo, ((img.size[0] - target) // 2, (img.size[1] - target) // 2))
        except Exception:  # the emblem is a nicety; never fail QR generation over it
            log.warning("Could not draw the NDI logo on the QR code")
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
