import { useState } from "react";
import { api, ApiError } from "../api";
import { useList } from "../useList";
import { Icon } from "./Icon";
import { useToast } from "./Toast";
import { fmt } from "./ui";
import "../styles/ApiStatus.css";

interface Point { t: string; ok: boolean; ms: number; status: number; error: string }
interface Incident { from: string; to: string; error: string; recovered_at: string | null }
interface Service {
  service: string; label: string; configured: boolean; state: "up" | "down" | "no_data" | "not_configured";
  last_checked: string | null; last_error: string; checks: number; uptime_pct: number | null; avg_ms: number | null;
  incidents: Incident[]; series: Point[];
}
interface Data { hours: number; services: Service[] }

const STATE: Record<Service["state"], [string, string]> = { up: ["ok", "Up"], down: ["bad", "Down"], no_data: ["warn", "No checks yet"], not_configured: ["warn", "Not configured"] };
const W = 800;

function Strip({ s, from, to }: { s: Service; from: number; to: number }) {
  const span = Math.max(1, to - from);
  return (
    <svg viewBox={`0 0 ${W} 34`} className="apistatus-svg" role="img" aria-label={`${s.label} up and down history`} preserveAspectRatio="none">
      <rect x="0" y="0" width={W} height="34" rx="6" className="apistatus-track" />
      {s.series.map((p, i) => {
        const x = ((new Date(p.t).getTime() - from) / span) * W;
        return <rect key={i} x={Math.min(W - 3, Math.max(0, x))} y="2" width="3" height="30" className={p.ok ? "apistatus-up" : "apistatus-down"}><title>{`${fmt(p.t)}: ${p.ok ? `up, ${p.ms} ms` : `DOWN ${p.error}`}`}</title></rect>;
      })}
    </svg>
  );
}

function Latency({ s, from, to }: { s: Service; from: number; to: number }) {
  const span = Math.max(1, to - from);
  const max = Math.max(100, ...s.series.filter((p) => p.ok).map((p) => p.ms)) * 1.15;
  const H = 150, padL = 44, padB = 22, padT = 8;
  const x = (t: string) => padL + ((new Date(t).getTime() - from) / span) * (W - padL - 8);
  const y = (ms: number) => padT + (1 - ms / max) * (H - padT - padB);
  const ok = s.series.filter((p) => p.ok);
  // Break the line where the API was down, so it never draws a response time that didn't happen.
  const segments: Point[][] = [];
  let run: Point[] = [];
  for (const p of s.series) { if (p.ok) run.push(p); else if (run.length) { segments.push(run); run = []; } }
  if (run.length) segments.push(run);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="apistatus-svg" role="img" aria-label={`${s.label} response time`}>
      {[0, 0.5, 1].map((f) => <g key={f}><line x1={padL} x2={W - 8} y1={y(max * f)} y2={y(max * f)} className="apistatus-grid" /><text x={padL - 6} y={y(max * f) + 4} textAnchor="end" className="apistatus-axis">{Math.round(max * f)} ms</text></g>)}
      {segments.filter((seg) => seg.length > 1).map((seg, i) => <polyline key={i} fill="none" className="apistatus-line" points={seg.map((p) => `${x(p.t)},${y(p.ms)}`).join(" ")} />)}
      {ok.map((p, i) => <circle key={i} cx={x(p.t)} cy={y(p.ms)} r="2.5" className="apistatus-dot"><title>{`${fmt(p.t)}: ${p.ms} ms`}</title></circle>)}
      {s.series.filter((p) => !p.ok).map((p, i) => <g key={`d${i}`}><line x1={x(p.t)} x2={x(p.t)} y1={padT} y2={H - padB} className="apistatus-downline" /><circle cx={x(p.t)} cy={H - padB} r="4" className="apistatus-downdot"><title>{`${fmt(p.t)}: DOWN ${p.error}`}</title></circle></g>)}
      <text x={padL} y={H - 4} className="apistatus-axis">{new Date(from).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}</text>
      <text x={W - 8} y={H - 4} textAnchor="end" className="apistatus-axis">{new Date(to).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}</text>
    </svg>
  );
}

/** Logs > API: is each external API up right now, and when did it go down and come back? */
export function ApiStatus() {
  const [hours, setHours] = useState(24);
  const { data, err, reload } = useList<Data>(`/admin/api-status/?hours=${hours}`);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  async function checkNow() {
    setBusy(true);
    try { await api("/admin/api-status/", { method: "POST" }); reload(); toast.success("API status checked."); }
    catch (x) { toast.error((x as ApiError).message); }
    finally { setBusy(false); }
  }
  const to = Date.now(), from = to - hours * 3600 * 1000;
  return (
    <section className="card" aria-label="API status" style={{ marginBottom: 16 }}>
      <div className="apistatus-head">
        <h2>API status</h2>
        <label className="apistatus-range"><span className="sr-only">Time range</span>
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))}>
            <option value={6}>Last 6 hours</option><option value={24}>Last 24 hours</option><option value={168}>Last 7 days</option><option value={720}>Last 30 days</option>
          </select></label>
        <button type="button" className="btn secondary" disabled={busy} onClick={checkNow}><Icon name="refresh" size={16} />{busy ? "Checking…" : "Check now"}</button>
      </div>
      {err && <p className="error" role="alert">{err}</p>}
      <div className="apistatus-grid-cards">
        {data?.services.map((s) => {
          const [tone, label] = STATE[s.state];
          return (
            <div key={s.service} className="apistatus-card">
              <div className="apistatus-title"><strong>{s.label}</strong><span className={`badge ${tone}`}>{label}</span></div>
              {s.state === "not_configured" ? (
                <p className="muted">Not connected yet. Once its address is set in <code>.env</code> it is checked every few minutes and shown here.</p>
              ) : (
                <>
                  <dl className="apistatus-stats">
                    <div><dt>Uptime</dt><dd>{s.uptime_pct === null ? "—" : `${s.uptime_pct}%`}</dd></div>
                    <div><dt>Average response</dt><dd>{s.avg_ms === null ? "—" : `${s.avg_ms} ms`}</dd></div>
                    <div><dt>Checks</dt><dd>{s.checks}</dd></div>
                    <div><dt>Last checked</dt><dd>{s.last_checked ? fmt(s.last_checked) : "—"}</dd></div>
                  </dl>
                  {s.state === "down" && s.last_error && <p className="error" role="alert">{s.last_error}</p>}
                  {s.series.length > 0 && <><h3>Up and down</h3><Strip s={s} from={from} to={to} /><h3>Response time</h3><Latency s={s} from={from} to={to} /></>}
                  {s.series.length === 0 && <p className="muted">No checks in this time range.</p>}
                  <h3>Outages</h3>
                  {s.incidents.length === 0 ? <p className="muted">None in this time range.</p> : (
                    <ul className="apistatus-incidents">
                      {[...s.incidents].reverse().map((i, n) => (
                        <li key={n}><span className="badge bad">Went down</span> {fmt(i.from)} <span className={`badge ${i.recovered_at ? "ok" : "bad"}`}>{i.recovered_at ? "Back up" : "Still down"}</span> {i.recovered_at ? fmt(i.recovered_at) : ""}
                          {i.error && <small className="muted"> · {i.error}</small>}</li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
