"""The complaint workflow an Administrator can configure: which steps are on, and their order.

Steps: triage (Division Head), investigation (Investigating Officer), supervisor (Supervisor approval) and closure
(Division Head closes the case). Investigation and closure are always on. Turning triage off sends every new complaint
straight to the Investigating Officer of its division with the fewest open cases. Turning supervisor approval off
removes the "send to Supervisor" option so the Division Head closes the case directly.
The status rules in complaints/services.py stay the safety net, so only orders that fit them are accepted.
"""
import json
import time

from .models import SystemConfiguration

KEY = "workflow_steps"
STEPS = {
    "triage": {"label": "Division Head triage", "detail": "The Division Head checks the category and priority and picks the officer. Off: new complaints go straight to an Investigating Officer, chosen by lowest workload.", "locked": False},
    "investigation": {"label": "Investigating Officer", "detail": "The officer investigates and records findings. Always on.", "locked": True},
    "supervisor": {"label": "Supervisor approval", "detail": "The Division Head may send submitted findings to the Supervisor. Off: the Division Head approves and closes directly.", "locked": False},
    "closure": {"label": "Division Head closure", "detail": "The Division Head approves the resolution and closes the case. Always on, always last.", "locked": True},
}
DEFAULT = [{"key": k, "enabled": True} for k in ("triage", "investigation", "supervisor", "closure")]
_cache = {"at": 0.0, "steps": None}
_TTL = 10  # seconds a worker process keeps the setting; saving clears it at once


def _valid_order(keys):
    pos = {k: i for i, k in enumerate(keys)}
    return pos["triage"] < pos["investigation"] < pos["supervisor"] < pos["closure"]


def validate(steps):
    """Return (clean_steps, error)."""
    if not isinstance(steps, list) or any(not isinstance(s, dict) for s in steps):
        return None, "Send the steps as a list."
    keys = [s.get("key") for s in steps]
    if sorted(map(str, keys)) != sorted(STEPS):
        return None, "The workflow must contain each step exactly once."
    clean = [{"key": s["key"], "enabled": bool(s.get("enabled", True))} for s in steps]
    for s in clean:
        if STEPS[s["key"]]["locked"] and not s["enabled"]:
            return None, f"{STEPS[s['key']]['label']} cannot be switched off."
    if not _valid_order(keys):
        return None, "That order does not work: triage comes first, then the Investigating Officer, then Supervisor approval, and the Division Head closes last."
    return clean, None


def get_steps():
    now = time.monotonic()
    if _cache["steps"] is None or now - _cache["at"] > _TTL:
        try:
            clean, error = validate(json.loads(SystemConfiguration.get(KEY, "") or "null"))
        except ValueError:
            clean, error = None, "bad"
        _cache.update(at=now, steps=clean if not error else [dict(s) for s in DEFAULT])
    return _cache["steps"]


def enabled(key):
    return any(s["key"] == key and s["enabled"] for s in get_steps())


def save_steps(steps):
    SystemConfiguration.objects.update_or_create(
        key=KEY, defaults={"value": json.dumps(steps), "description": "Complaint workflow steps (Workflow screen)"})
    _cache.update(at=0.0, steps=None)


def describe(steps=None):
    return [{**s, "label": STEPS[s["key"]]["label"], "detail": STEPS[s["key"]]["detail"], "locked": STEPS[s["key"]]["locked"]}
            for s in (steps or get_steps())]
