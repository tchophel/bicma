"""Self-hosted image CAPTCHA (no third-party service, no external keys).

A challenge is a random code rendered as a distorted SVG. The server keeps no state except a
one-time-use marker: the signed token carries a keyed hash of the code, expires after 10 minutes and
can be used once. For stronger bot protection, a provider such as Cloudflare Turnstile or hCaptcha
can replace this module without changing the API shape.
"""
import hashlib
import hmac
import html
import random
import secrets
from dataclasses import dataclass

from django.conf import settings
from django.core import signing
from django.core.cache import cache

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I
LENGTH = 5
MAX_AGE = 600
SALT = "bicma.captcha"


@dataclass
class Challenge:
    token: str
    svg: str
    code: str  # never sent to clients; used by tests


def _digest(nonce: str, code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"{nonce}:{code}".encode(), hashlib.sha256).hexdigest()


def _render(code: str) -> str:
    rnd = random.SystemRandom()
    w, h = 170, 60
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
             f'<rect width="{w}" height="{h}" fill="#f6efe4"/>']
    for _ in range(6):
        parts.append(f'<path d="M{rnd.randint(0, w)} {rnd.randint(0, h)} Q{rnd.randint(0, w)} {rnd.randint(0, h)} '
                     f'{rnd.randint(0, w)} {rnd.randint(0, h)}" stroke="#{rnd.choice(["b08968", "8d6e63", "a1887f", "c9a27e"])}" '
                     f'stroke-width="{rnd.choice([1, 1.5, 2])}" fill="none"/>')
    step = (w - 24) / LENGTH
    for i, ch in enumerate(code):
        x = 14 + i * step + rnd.randint(-2, 2)
        y = 40 + rnd.randint(-5, 5)
        parts.append(f'<text x="{x:.1f}" y="{y}" font-size="{rnd.randint(28, 34)}" font-weight="700" '
                     f'font-family="Georgia, serif" fill="#{rnd.choice(["5d2a0b", "803007", "3b2a1a", "1f4e5f"])}" '
                     f'transform="rotate({rnd.randint(-22, 22)} {x:.1f} {y})">{html.escape(ch)}</text>')
    for _ in range(35):
        parts.append(f'<circle cx="{rnd.randint(0, w)}" cy="{rnd.randint(0, h)}" r="{rnd.choice([0.8, 1.2])}" fill="#8d6e63" opacity=".6"/>')
    parts.append("</svg>")
    return "".join(parts)


def new_challenge() -> Challenge:
    code = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
    nonce = secrets.token_urlsafe(9)
    token = signing.dumps({"n": nonce, "h": _digest(nonce, code)}, salt=SALT)
    return Challenge(token=token, svg=_render(code), code=code)


def verify(token: str, answer: str) -> bool:
    """True only for a correct answer to an unexpired, never-before-attempted challenge."""
    try:
        data = signing.loads(str(token or ""), salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        return False
    if not cache.add(f"captcha_used:{data['n']}", 1, MAX_AGE + 60):  # one attempt per challenge
        return False
    given = "".join(str(answer or "").split()).upper()
    return hmac.compare_digest(data["h"], _digest(data["n"], given))
