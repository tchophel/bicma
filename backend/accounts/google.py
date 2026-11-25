"""Sign in with Google. Only people who already have an active account here can sign in: their verified Google email must
match the account email. The Client ID and secret are typed into Settings (kept in SystemConfiguration, secret write-only)."""
import json
import secrets
import urllib.parse
import urllib.request

from django.conf import settings

from core.models import SystemConfiguration

KEY = "google_login"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _cfg():
    row = SystemConfiguration.objects.filter(key=KEY).first()
    try:
        return json.loads(row.value) if row else {}
    except ValueError:
        return {}


def enabled():
    c = _cfg()
    return bool(c.get("client_id") and c.get("client_secret"))


def save(client_id, client_secret):
    c = _cfg()
    c["client_id"] = client_id.strip()
    if client_secret.strip():
        c["client_secret"] = client_secret.strip()
    if not c["client_id"]:
        c = {}
    SystemConfiguration.objects.update_or_create(key=KEY, defaults={"value": json.dumps(c), "description": "Sign in with Google"})


def public():
    c = _cfg()
    return {"client_id": c.get("client_id", ""), "secret_set": bool(c.get("client_secret")), "enabled": enabled()}


def allowed_redirect(redirect_uri, request):
    """The redirect must be this site's own sign-in page (the browser origin of the request or a configured origin)."""
    p = urllib.parse.urlparse(redirect_uri)
    origin = f"{p.scheme}://{p.netloc}"
    ok = {request.headers.get("Origin", ""), *getattr(settings, "CORS_ALLOWED_ORIGINS", [])}
    return p.path == "/staff/login/google" and origin in ok


def start_url(request, redirect_uri):
    state = secrets.token_urlsafe(24)
    request.session["google_state"] = state
    request.session["google_redirect"] = redirect_uri
    q = {"client_id": _cfg()["client_id"], "redirect_uri": redirect_uri, "response_type": "code", "scope": "openid email",
         "state": state, "prompt": "select_account", "access_type": "online"}
    return f"{AUTH_URL}?{urllib.parse.urlencode(q)}"


def _post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=15).read())


def email_for_code(request, code, state):
    """Exchange the code Google sent back and return the verified email, or raise ValueError with a message for the user."""
    expected = request.session.pop("google_state", None)
    redirect = request.session.pop("google_redirect", None)
    if not expected or not redirect or not secrets.compare_digest(str(state), expected):
        raise ValueError("This sign-in request has expired. Please try again.")
    c = _cfg()
    try:
        tok = _post(TOKEN_URL, {"code": code, "client_id": c["client_id"], "client_secret": c["client_secret"],
                                "redirect_uri": redirect, "grant_type": "authorization_code"})
        info = json.loads(urllib.request.urlopen(urllib.request.Request(
            USERINFO_URL, headers={"Authorization": f"Bearer {tok['access_token']}"}), timeout=15).read())
    except Exception:
        raise ValueError("Google sign-in could not be completed. Please try again.")
    if not info.get("email") or not info.get("email_verified"):
        raise ValueError("Your Google email address is not verified.")
    return info["email"].strip().lower()
