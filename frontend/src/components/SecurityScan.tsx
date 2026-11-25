import { useState } from "react";
import { api, ApiError } from "../api";
import { Icon } from "./Icon";
import { useList } from "../useList";
import { useToast } from "./Toast";
import { fmt } from "./ui";

type Finding = { package: string; ecosystem: string; version: string; id: string; aliases: string[]; severity: string; summary: string; fixed_in: string; fix: string };
type Field = { key: string; label: string; secret: boolean; placeholder: string; value: string; set: boolean };
type Item = { severity: string; type: string; file: string; line: number; message: string; rule: string; link: string };
type Check = { items?: Item[]; fields: Field[]; key: string; label: string; about: string; configured: boolean; setup: string; state: string; summary: string; link: string; checked_at: string | null };
const STATE: Record<string, [string, string]> = { ok: ["ok", "All clear"], issues: ["bad", "Issues found"], error: ["warn", "Check failed"], never: ["plain", "Not checked yet"], not_configured: ["plain", "Not set up"] };
type Scan = { scanned_at?: string; packages?: number; frontend_included?: boolean; findings?: Finding[]; counts?: Record<string, number> };
const TONE: Record<string, string> = { CRITICAL: "bad", HIGH: "bad", MEDIUM: "warn", LOW: "plain", UNKNOWN: "plain" };

/** Settings > Security scan: check the packages the system runs on for known vulnerabilities and show how to fix each one. */
export function SecurityScan() {
  const toast = useToast();
  const { data, reload } = useList<Scan>("/admin/security-scan/");
  const checks = useList<{ checks: Check[] }>("/admin/security-checks/");
  const [running, setRunning] = useState("");
  async function runCheck(key: string) {
    setRunning(key || "all");
    try { await api("/admin/security-checks/", { method: "POST", json: key ? { check: key } : {} }); checks.reload(); reload(); }
    catch (e) { setErr((e as ApiError).message); }
    finally { setRunning(""); }
  }
  async function solve(check = "") {
    if (!window.confirm("Solve starts an automatic fix on GitHub. It fixes this problem in a copy of the code and opens a pull request for you to review. Nothing changes on the live system until you merge it and redeploy. Start now?")) return;
    setRunning(check ? `solve-${check}` : "solve"); setErr("");
    try { const r = await api<{ message: string; link: string }>("/admin/security-solve/", { method: "POST", json: { check } }); toast.success(r.message); setSolveLink(r.link); }
    catch (e) { setErr((e as ApiError).message); }
    finally { setRunning(""); }
  }
  const [solveLink, setSolveLink] = useState("");
  const [editing, setEditing] = useState("");
  const [vals, setVals] = useState<Record<string, string>>({});
  async function saveConfig(c: Check) {
    setRunning(c.key); setErr("");
    try {
      await api("/admin/security-checks/config/", { method: "POST", json: { check: c.key, values: vals } });
      toast.success("Saved and checked."); setEditing(""); checks.reload();
    } catch (e) { setErr((e as ApiError).message); }
    finally { setRunning(""); }
  }
  const [scan, setScan] = useState<Scan | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const cur = scan ?? data;
  const findings = cur?.findings ?? [];
  const fixes = [...new Set(findings.map((f) => f.fix).filter(Boolean))];

  async function run() {
    setBusy(true); setErr("");
    try { setScan(await api<Scan>("/admin/security-scan/", { method: "POST", json: {} })); reload(); }
    catch (e) { setErr((e as ApiError).message); }
    finally { setBusy(false); }
  }
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); toast.success("Copied."); } catch { toast.error("Could not copy. Select the text instead."); }
  }

  return (
    <section className="card settings-section" aria-labelledby="settings-scan">
      <header className="settings-section-header"><span className="icon-tile"><Icon name="lock" size={22} /></span>
        <div><span className="settings-eyebrow">SECURITY</span><h2 id="settings-scan">Security scan</h2>
          <p>Checks the packages this system runs on against the public vulnerability database (OSV) and shows how to fix each finding. Only package names and versions are sent.</p></div></header>
      <div className="scan-checks">
        <div className="scan-checks-head"><h3>Automated checks</h3>
          <button type="button" className="btn secondary" disabled={!!running} onClick={() => runCheck("")}><Icon name="refresh" />{running === "all" ? "Checking…" : "Check all now"}</button>
          {(findings.length > 0 || (checks.data?.checks ?? []).some((c) => c.state === "issues" || c.state === "error")) &&
            <button type="button" className="btn" disabled={!!running} onClick={() => void solve()}><Icon name="check" />{running === "solve" ? "Starting…" : "Solve"}</button>}
          {(findings.length > 0 || (checks.data?.checks ?? []).some((c) => c.state === "issues" || c.state === "error")) &&
            <a className="btn secondary" href="/api/admin/security-report/" download><Icon name="send" />Download PDF: what to fix</a>}</div>
        {solveLink && <p role="status" className="notice"><Icon name="check" size={16} /> Fix started. <a href={solveLink} target="_blank" rel="noreferrer">Watch it on GitHub</a>, then open the pull request it creates.</p>}
        <p className="muted">Checked automatically every day. The Administrators get a notification when a check newly finds issues.</p>
        <div className="scan-cards">{checks.data?.checks.map((c) => {
          const [tone, label] = STATE[c.state] ?? STATE.never;
          return (
            <div key={c.key} className="scan-card">
              <div className="scan-card-title"><strong>{c.label}</strong><span className={`badge ${tone}`}>{label}</span></div>
              <p className="muted">{c.about}</p>
              <p>{c.summary}</p>
              {c.checked_at && <small className="muted">Checked {fmt(c.checked_at)}</small>}
              {!!c.items?.length && (
                <details className="scan-items"><summary>Show the {c.items.length} issues to fix</summary>
                  <ul>{c.items.map((i, n) => (
                    <li key={n}><span className={`badge ${i.severity === "BLOCKER" || i.severity === "CRITICAL" ? "bad" : i.severity === "MAJOR" ? "warn" : "plain"}`}>{i.severity.toLowerCase()}</span>{" "}
                      <a href={i.link} target="_blank" rel="noreferrer"><code>{i.file}{i.line ? `:${i.line}` : ""}</code></a><br /><small>{i.message}</small></li>))}</ul>
                </details>)}
              {editing === c.key && (
                <form className="scan-config" onSubmit={(e) => { e.preventDefault(); void saveConfig(c); }}>
                  {c.fields.map((f) => (
                    <label key={f.key}><span>{f.label}</span>
                      <input type={f.secret ? "password" : "text"} autoComplete="off" value={vals[f.key] ?? ""} placeholder={f.secret && f.set ? "Saved. Leave blank to keep it." : f.placeholder}
                        onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })} /></label>
                  ))}
                  <div className="scan-card-actions"><button type="submit" className="btn" disabled={!!running}>{running === c.key ? "Saving…" : "Save and check"}</button>
                    <button type="button" className="linklike" onClick={() => setEditing("")}>Cancel</button></div>
                </form>)}
              <div className="scan-card-actions">
                {c.state === "issues" && (c.key === "dependencies" || c.key === "sonarqube") && <button type="button" className="btn" disabled={!!running} onClick={() => void solve(c.key)}>{running === `solve-${c.key}` ? "Starting…" : "Solve"}</button>}
                {c.configured && <button type="button" className="btn secondary" disabled={!!running} onClick={() => runCheck(c.key)}>{running === c.key ? "Checking…" : "Check now"}</button>}
                {c.fields.length > 0 && editing !== c.key && <button type="button" className={c.configured ? "linklike" : "btn"} onClick={() => { setEditing(editing === c.key ? "" : c.key); setVals(Object.fromEntries(c.fields.map((f) => [f.key, f.value]))); }}>{c.configured ? "Edit settings" : "Set up"}</button>}
                {c.link && <a href={c.link} target="_blank" rel="noreferrer">Open report</a>}
              </div>
            </div>);
        })}</div>
      </div>
      <h3>Dependency details</h3>
      <div className="scan-bar">
        <button type="button" className="btn" disabled={busy} onClick={run}><Icon name="refresh" />{busy ? "Scanning…" : "Scan now"}</button>
        {cur?.scanned_at && <span className="muted">Last scan {fmt(cur.scanned_at)} · {cur.packages} packages{cur.frontend_included ? "" : " (backend only: the frontend package list is not available to this server)"}</span>}
      </div>
      {err && <p className="error" role="alert">{err}</p>}
      {cur?.scanned_at && (findings.length === 0
        ? <p className="notice" role="status"><Icon name="check" size={16} /> No known vulnerabilities found.</p>
        : <>
          <div className="scan-counts">{(["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"] as const).filter((s) => cur.counts?.[s]).map((s) => <span key={s} className={`badge ${TONE[s]}`}>{cur.counts?.[s]} {s.toLowerCase()}</span>)}</div>
          <div className="table-wrap"><table>
            <thead><tr><th>Package</th><th>Severity</th><th>Issue</th><th>Fix</th></tr></thead>
            <tbody>{findings.map((f) => (
              <tr key={`${f.package}-${f.id}`}>
                <td><strong>{f.package}</strong><small className="muted cell-sub">{f.ecosystem} · {f.version}</small></td>
                <td><span className={`badge ${TONE[f.severity] ?? "plain"}`}>{f.severity.toLowerCase()}</span></td>
                <td>{f.summary || f.id}<small className="muted cell-sub">{[f.id, ...f.aliases].join(" · ")}</small></td>
                <td>{f.fix ? <><code>{f.fix}</code> <button type="button" className="linklike" onClick={() => copy(f.fix)}>Copy</button></> : <span className="muted">No fixed version yet</span>}</td>
              </tr>))}</tbody>
          </table></div>
          {fixes.length > 0 && <div className="scan-plan">
            <h3>How to fix</h3>
            <p className="muted">Applying a fix changes the packages the system is built from, so it is done in the code and then redeployed, not on the live server. Run these in the project folder, then rebuild and redeploy the images.</p>
            <pre>{fixes.join("\n")}</pre>
            <button type="button" className="btn secondary" onClick={() => copy(fixes.join("\n"))}><Icon name="check" />Copy all fix commands</button>
          </div>}
        </>)}
    </section>
  );
}
