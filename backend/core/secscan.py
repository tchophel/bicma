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
import urllib.error
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
    items = []
    if bad:  # the actual bugs and vulnerabilities, most serious first, so they can be fixed from the list
        found = _json(f"{base}/api/issues/search?componentKeys={proj}&types=BUG,VULNERABILITY&resolved=false&ps=200&s=SEVERITY&asc=false", h)
        order = {"BLOCKER": 0, "CRITICAL": 1, "MAJOR": 2, "MINOR": 3, "INFO": 4}
        for i in sorted(found.get("issues", []), key=lambda i: order.get(i["severity"], 5)):
            items.append({"severity": i["severity"], "type": i["type"], "file": i["component"].split(":", 1)[-1], "line": i.get("line") or 0,
                          "message": i["message"], "rule": i["rule"], "link": f"{base}/project/issues?id={proj}&open={urllib.parse.quote(i['key'])}"})
    return {"state": "issues" if bad else "ok", "counts": counts, "link": f"{base}/dashboard?id={proj}", "items": items,
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


def solve(check=None):
    """Start the "Auto fix" GitHub workflow, which opens a pull request with the fixes. Returns (ok, message, link)."""
    what = {None: "all", "": "all", "dependencies": "packages", "sonarqube": "code"}.get(check)
    if what is None:
        return False, "This check cannot be fixed automatically. Open its report and fix what it lists.", ""
    repo, token = _env("GITHUB_REPO"), _env("GITHUB_TOKEN")
    if not repo or not token:
        return False, "Enter the GitHub repository and an access token (with Actions: read and write) in the CI pipeline settings first.", ""
    api = f"https://api.github.com/repos/{repo}"
    hdr = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    try:
        branch = _json(api, hdr)["default_branch"]
        body = {"ref": branch, "inputs": {"what": what, "sonar_url": _env("SONARQUBE_URL").rstrip("/"), "sonar_project": _env("SONARQUBE_PROJECT")}}
        urllib.request.urlopen(urllib.request.Request(f"{api}/actions/workflows/auto-fix.yml/dispatches", data=json.dumps(body).encode(),
                                                      headers={**hdr, "Content-Type": "application/json"}, method="POST"), timeout=20)
    except urllib.error.HTTPError as exc:
        why = {401: "the token is not accepted", 403: "the token needs the permission Actions: read and write", 404: "the workflow auto-fix.yml was not found on the default branch (push it first) or the token cannot see the repository", 422: "GitHub refused the request (is auto-fix.yml on the default branch?)"}.get(exc.code, f"GitHub answered {exc.code}")
        return False, f"Could not start the fix: {why}.", ""
    except Exception as exc:
        return False, f"Could not reach GitHub ({type(exc).__name__}).", ""
    return True, "The fix has started. In a few minutes a pull request appears on GitHub. Review it, merge it, then redeploy.", f"https://github.com/{repo}/actions/workflows/auto-fix.yml"


TODO = {
    "ci": "Open the failing run on GitHub (link below), read the red step, fix the code or the test, and push again. The check turns green when the next run passes.",
    "sonarqube": "Open the project in SonarQube (link below), look at the failed conditions of the quality gate (bugs, vulnerabilities, security hotspots), fix those lines in the code and run the analysis again.",
    "zap": "Open the ZAP report (link below), start with the High and Medium alerts, fix each one in the code or the web server settings, and run the ZAP scan again.",
    "dependencies": "Update the packages listed below to the shown version, run the tests, then rebuild and redeploy the images.",
}
ERROR_TODO = "The check could not run. In Settings > Security scan, open Edit settings and check the address, project and token, and make sure the tool is running and reachable from the server."


def report_pdf(by=""):
    """A PDF listing everything that is not clear, and what to update or fix for each item."""
    import html
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from . import depscan
    e = lambda v: html.escape(str(v or ""))
    st = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=st["BodyText"], fontSize=8, leading=10)
    mono = ParagraphStyle("mono", parent=small, fontName="Courier", fontSize=7.5, leading=9.5)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Security report", leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    flow = [Paragraph("BICMA CMS: security report", st["Title"]),
            Paragraph(f"Made {timezone.localtime():%Y-%m-%d %H:%M}" + (f" for {e(by)}" if by else ""), st["Normal"]), Spacer(1, 10)]
    problems = [c for c in overview() if c["state"] in ("issues", "error")]
    if not problems:
        flow.append(Paragraph("Everything that is set up is clear. Nothing needs updating.", st["Heading2"]))
    else:
        rows = [[Paragraph("<b>Check</b>", small), Paragraph("<b>Result</b>", small), Paragraph("<b>What to do</b>", small)]]
        for c in problems:
            rows.append([Paragraph(e(c["label"]), small), Paragraph(e(c["summary"]), small), Paragraph(e(TODO[c["key"]] if c["state"] == "issues" else ERROR_TODO), small)])
        t = Table(rows, colWidths=[90, 150, 300], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flow += [Paragraph("What needs attention", st["Heading2"]), t]
        for c in problems:
            if c["link"]:
                flow.append(Paragraph(f"{e(c['label'])} report: {e(c['link'])}", small))
    sonar = (last("sonarqube") or {}).get("items") or []
    if sonar:
        flow += [Spacer(1, 12), Paragraph("Code issues to fix (SonarQube)", st["Heading2"]),
                 Paragraph(f"{len(sonar)} bugs and vulnerabilities, most serious first. Fix the line shown, then run the check again.", small), Spacer(1, 4)]
        rows = [[Paragraph(f"<b>{h}</b>", small) for h in ("Severity", "File and line", "What is wrong")]]
        for i in sonar[:150]:
            rows.append([Paragraph(f"{e(i['severity'])}<br/>{e(i['type'])}", small), Paragraph(f"{e(i['file'])}:{i['line']}", small), Paragraph(f"{e(i['message'])[:220]}<br/>({e(i['rule'])})", small)])
        t = Table(rows, colWidths=[60, 150, 330], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flow.append(t)
    scan = depscan.last() or {}
    finds = scan.get("findings") or []
    if finds:
        flow += [Spacer(1, 12), Paragraph("Packages to update", st["Heading2"]),
                 Paragraph(f"{len(finds)} known vulnerabilities in {scan.get('packages', '?')} packages. Highest severity first.", small), Spacer(1, 4)]
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        rows = [[Paragraph(f"<b>{h}</b>", small) for h in ("Package", "Severity", "Issue", "Update to")]]
        for f in sorted(finds, key=lambda f: order.get(f["severity"], 4)):
            rows.append([Paragraph(f"{e(f['package'])} {e(f['version'])}<br/>({e(f['ecosystem'])})", small), Paragraph(e(f["severity"]), small),
                         Paragraph(f"{e(f['id'])}<br/>{e(f['summary'])[:200]}", small), Paragraph(e(f["fixed_in"]) or "No fixed version yet", small)])
        t = Table(rows, colWidths=[110, 55, 275, 100], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flow.append(t)
        cmds = list(dict.fromkeys(f["fix"] for f in finds if f.get("fix")))
        if cmds:
            flow += [Spacer(1, 12), Paragraph("Commands to run in the project folder", st["Heading2"]),
                     Paragraph("Run these, then run the tests, rebuild the images and redeploy.", small)]
            flow += [Paragraph(e(c), mono) for c in cmds]
    doc.build(flow)
    return buf.getvalue()
