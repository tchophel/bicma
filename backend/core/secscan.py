"""Automated security and quality checks shown in Settings > Security scan.

Each check reads the result of a tool the team already runs and turns it into one state: ok, issues, error or
not_configured. They are re-checked every day by the scheduler, and the Administrators get a notification when a check
newly finds issues. Address and credentials are typed into Settings (.env works as a fallback):

  Dependencies   built in (OSV, see depscan.py), nothing to set up
  CI build       GITHUB_REPO=owner/name   [GITHUB_TOKEN for a private repository]
  SonarQube      SONARQUBE_URL, SONARQUBE_PROJECT, SONARQUBE_TOKEN
  OWASP ZAP      ZAP_URL, ZAP_TARGET (the address ZAP scanned), ZAP_API_KEY
"""
import base64
import json
import os
import urllib.parse
import urllib.request

from django.utils import timezone

from .models import SystemConfiguration

CHECKS = [
    ("dependencies", "Dependency vulnerabilities", "Known vulnerabilities in the packages the system is built from (OSV database)."),
    ("ci", "CI pipeline", "Result of the latest build and test run on GitHub Actions."),
    ("sonarqube", "SonarQube", "Code quality gate, bugs and security hotspots."),
    ("zap", "OWASP ZAP", "Alerts from the latest ZAP scan of the running site."),
]
SETUP = {
    "dependencies": "",
    "ci": "Enter the GitHub repository (and a token if it is private) to turn this check on.",
    "sonarqube": "Enter the SonarQube address, project key and token to turn this check on.",
    "zap": "Enter the ZAP address, the site it scans and the ZAP API key to turn this check on.",
}


# What each check needs: (setting name, label, secret?). Typed into Settings; a value in .env is used when none is saved there.
FIELDS = {
    "ci": [("GITHUB_REPO", "GitHub repository (owner/name)", False, "tchophel/bicma"), ("GITHUB_TOKEN", "Access token (only for a private repository)", True, "")],
    "sonarqube": [("SONARQUBE_URL", "SonarQube address", False, "https://sonar.example.bt"), ("SONARQUBE_PROJECT", "Project key", False, ""), ("SONARQUBE_TOKEN", "Access token", True, "")],
    "zap": [("ZAP_URL", "ZAP address", False, "http://zap:8080"), ("ZAP_TARGET", "Address ZAP scans (the site)", False, "https://cms.example.bt"), ("ZAP_API_KEY", "ZAP API key", True, "")],
}


def _saved():
    raw = SystemConfiguration.get("secscan_config", "")
    return json.loads(raw) if raw else {}


def _env(k):
    return (_saved().get(k) or os.environ.get(k, "")).strip()


def save_config(check, values):
    """Store what the Administrator typed. A blank secret keeps the saved one; other blanks clear the setting."""
    cfg = _saved()
    for name, _label, secret, _ph in FIELDS[check]:
        if name not in values:
            continue
        v = str(values[name]).strip()
        if secret and not v:
            continue
        if v:
            cfg[name] = v
        else:
            cfg.pop(name, None)
    SystemConfiguration.objects.update_or_create(key="secscan_config", defaults={"value": json.dumps(cfg), "description": "Security check settings"})


def fields_for(check):
    cfg = _saved()
    return [{"key": n, "label": l, "secret": sec, "placeholder": ph,
             "value": "" if sec else (cfg.get(n) or os.environ.get(n, "")), "set": bool(cfg.get(n) or os.environ.get(n))}
            for n, l, sec, ph in FIELDS.get(check, [])]


def configured(key):
    return {"dependencies": True, "ci": bool(_env("GITHUB_REPO")), "sonarqube": bool(_env("SONARQUBE_URL") and _env("SONARQUBE_PROJECT")),
            "zap": bool(_env("ZAP_URL") and _env("ZAP_TARGET"))}[key]


def _json(url, headers=None):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=20).read())


def _dependencies():
    from . import depscan
    r = depscan.run()
    n = len(r["findings"])
    return {"state": "issues" if n else "ok", "counts": r["counts"], "link": "",
            "summary": f"{n} known {'vulnerability' if n == 1 else 'vulnerabilities'} in {r['packages']} packages" if n else f"No known vulnerabilities in {r['packages']} packages"}


def _ci():
    h = {"Accept": "application/vnd.github+json"}
    if _env("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {_env('GITHUB_TOKEN')}"
    runs = _json(f"https://api.github.com/repos/{_env('GITHUB_REPO')}/actions/runs?per_page=1", h).get("workflow_runs", [])
    if not runs:
        return {"state": "error", "summary": "No pipeline run found yet", "counts": {}, "link": ""}
    r = runs[0]
    name = f"{r.get('name', 'Pipeline')} on {r.get('head_branch', '')}"
    if r["status"] != "completed":
        return {"state": "ok", "summary": f"{name}: running", "counts": {}, "link": r["html_url"]}
    good = r["conclusion"] == "success"
    return {"state": "ok" if good else "issues", "summary": f"{name}: {r['conclusion']}", "counts": {}, "link": r["html_url"]}


def _sonarqube():
    base, proj = _env("SONARQUBE_URL").rstrip("/"), urllib.parse.quote(_env("SONARQUBE_PROJECT"))
    h = {"Authorization": "Basic " + base64.b64encode(f"{_env('SONARQUBE_TOKEN')}:".encode()).decode()}
    gate = _json(f"{base}/api/qualitygates/project_status?projectKey={proj}", h)["projectStatus"]
    meas = _json(f"{base}/api/measures/component?component={proj}&metricKeys=bugs,vulnerabilities,security_hotspots,code_smells", h)
    counts = {m["metric"]: int(float(m.get("value", 0))) for m in meas["component"]["measures"]}
    bad = gate["status"] != "OK" or counts.get("vulnerabilities", 0) or counts.get("bugs", 0)
    return {"state": "issues" if bad else "ok", "counts": counts, "link": f"{base}/dashboard?id={proj}",
            "summary": f"Quality gate {gate['status'].lower()}: {counts.get('bugs', 0)} bugs, {counts.get('vulnerabilities', 0)} vulnerabilities, {counts.get('security_hotspots', 0)} hotspots"}


def _zap():
    base = _env("ZAP_URL").rstrip("/")
    q = urllib.parse.urlencode({"baseurl": _env("ZAP_TARGET"), "apikey": _env("ZAP_API_KEY")})
    s = _json(f"{base}/JSON/alert/view/alertsSummary/?{q}")["alertsSummary"]
    counts = {k: int(v) for k, v in s.items()}
    serious = counts.get("High", 0) + counts.get("Medium", 0)
    return {"state": "issues" if serious else "ok", "counts": counts, "link": "",
            "summary": f"{counts.get('High', 0)} high, {counts.get('Medium', 0)} medium, {counts.get('Low', 0)} low alerts"}


RUN = {"dependencies": _dependencies, "ci": _ci, "sonarqube": _sonarqube, "zap": _zap}


def last(key):
    raw = SystemConfiguration.get(f"secscan_{key}", "")
    return json.loads(raw) if raw else None


def run(key, notify_admins=True):
    """Run one check, store it, and tell the Administrators when it newly finds issues."""
    if not configured(key):
        return {"state": "not_configured", "summary": SETUP[key], "counts": {}, "link": "", "checked_at": None}
    try:
        res = RUN[key]()
    except Exception as exc:
        res = {"state": "error", "summary": f"Could not run the check ({type(exc).__name__})", "counts": {}, "link": ""}
    res["checked_at"] = timezone.now().isoformat()
    before = last(key)
    SystemConfiguration.objects.update_or_create(key=f"secscan_{key}", defaults={"value": json.dumps(res), "description": f"Last {key} security check"})
    if notify_admins and res["state"] == "issues" and (not before or before.get("state") != "issues" or before.get("counts") != res["counts"]):
        from accounts.models import Role, User, roles_with_base
        from .notifications import notify
        label = next(l for k, l, _ in CHECKS if k == key)
        notify(User.objects.filter(role__in=roles_with_base(Role.SUPER_ADMIN), is_active=True),
               f"Security check: {label} found issues. {res['summary']}"[:300], "/staff/settings")
    return res


def overview():
    out = []
    for key, label, about in CHECKS:
        cur = last(key) if configured(key) else None
        out.append({"key": key, "label": label, "about": about, "configured": configured(key), "setup": SETUP[key], "fields": fields_for(key),
                    **(cur or {"state": "not_configured" if not configured(key) else "never", "summary": SETUP[key] if not configured(key) else "Not checked yet", "counts": {}, "link": "", "checked_at": None})})
    return out


def run_all():
    return {k: run(k) for k, _, _ in CHECKS}
