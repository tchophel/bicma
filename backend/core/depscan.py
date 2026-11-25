"""Dependency security scan for Administrators (Settings > Security scan).

Collects the packages this system runs on, asks the public OSV database (api.osv.dev) which versions have known
vulnerabilities, and turns each finding into a fix: the version to move to and the command that does it.
Only package names and versions are sent. Applying a fix means changing requirements.txt / package.json and
rebuilding the images, so this page tells you exactly what to change instead of changing a live system.
"""
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from importlib import metadata
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import SystemConfiguration

KEY = "security_scan"
OSV = "https://api.osv.dev/v1"
RANK = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "MEDIUM": 2, "LOW": 1}


def frontend_lock_path():
    for p in (os.environ.get("FRONTEND_LOCK"), "/app/frontend-lock.json", "/frontend-lock.json", str(Path(settings.BASE_DIR).parent / "frontend" / "package-lock.json")):
        if p and Path(p).is_file():
            return Path(p)
    return None


def collect():
    """[(ecosystem, name, version, direct_dev_flag)] for the backend's installed packages and the frontend lock file."""
    out, seen = [], set()
    for d in metadata.distributions():
        name, ver = d.metadata["Name"], d.version
        if name and ver and ("PyPI", name.lower()) not in seen:
            seen.add(("PyPI", name.lower())); out.append(("PyPI", name, ver))
    lock = frontend_lock_path()
    if lock:
        for path, info in json.loads(lock.read_text()).get("packages", {}).items():
            if not path or "node_modules/" not in path or not info.get("version"):
                continue
            name = path.rsplit("node_modules/", 1)[1]
            if ("npm", name) not in seen:
                seen.add(("npm", name)); out.append(("npm", name, info["version"]))
    return out, bool(lock)


def _post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())


def _get(url):
    return json.loads(urllib.request.urlopen(url, timeout=25).read())


def _severity(v):
    s = (v.get("database_specific") or {}).get("severity")
    if s:
        return s.upper().replace("MODERATE", "MEDIUM")
    return "UNKNOWN"


def _fixed(v, eco, name):
    out = []
    for a in v.get("affected", []):
        p = a.get("package", {})
        if p.get("ecosystem") == eco and p.get("name", "").lower() == name.lower():
            for r in a.get("ranges", []):
                out += [e["fixed"] for e in r.get("events", []) if "fixed" in e]
    return out


def run():
    pkgs, has_frontend = collect()
    queries = [{"package": {"name": n, "ecosystem": e}, "version": v} for e, n, v in pkgs]
    hits = []  # (pkg, [vuln ids])
    for i in range(0, len(queries), 500):
        res = _post(f"{OSV}/querybatch", {"queries": queries[i:i + 500]})["results"]
        hits += [(pkgs[i + j], [x["id"] for x in r.get("vulns", [])]) for j, r in enumerate(res) if r.get("vulns")]
    ids = sorted({x for _, v in hits for x in v})
    with ThreadPoolExecutor(8) as ex:
        details = dict(zip(ids, ex.map(lambda i: _get(f"{OSV}/vulns/{i}"), ids)))
    findings = []
    for (eco, name, ver), vids in hits:
        kept = set()  # the same issue can be listed under two ids (GHSA and PYSEC): keep the first of each pair
        for vid in vids:
            v = details[vid]
            names = {vid, *v.get("aliases", [])}
            if names & kept:
                continue
            kept |= names
            fixed = _fixed(v, eco, name)
            # the fix: the lowest fixed release above the installed version (best effort, plain string compare per part)
            target = fixed[-1] if fixed else ""
            cmd = (f'pip install "{name}>={target}"' if eco == "PyPI" else f"npm install {name}@{target}") if target else ""
            findings.append({
                "package": name, "ecosystem": eco, "version": ver, "id": vid,
                "aliases": [a for a in v.get("aliases", []) if a.startswith("CVE-")][:2],
                "severity": _severity(v), "summary": (v.get("summary") or "")[:200],
                "fixed_in": target, "fix": cmd,
            })
    # one upgrade per package fixes all its findings: use the highest fixed version
    def vkey(v):
        import re
        return [int(x) for x in re.findall(r"\d+", v)]
    best = {}
    for f in findings:
        if f["fixed_in"] and (f["package"], f["ecosystem"]) not in best or (f["fixed_in"] and vkey(f["fixed_in"]) > vkey(best[(f["package"], f["ecosystem"])]["fixed_in"])):
            best[(f["package"], f["ecosystem"])] = f
    for f in findings:
        b = best.get((f["package"], f["ecosystem"]))
        if b:
            f["fix"], f["fixed_in"] = b["fix"], b["fixed_in"]
    findings.sort(key=lambda f: (-RANK.get(f["severity"], 0), f["package"]))
    result = {"scanned_at": timezone.now().isoformat(), "packages": len(pkgs), "frontend_included": has_frontend, "findings": findings,
              "counts": {s: sum(1 for f in findings if f["severity"] == s) for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")}}
    SystemConfiguration.objects.update_or_create(key=KEY, defaults={"value": json.dumps(result), "description": "Last dependency security scan"})
    return result


def last():
    raw = SystemConfiguration.get(KEY, "")
    return json.loads(raw) if raw else None
