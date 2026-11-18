import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { Icon } from "../../components/Icon";
import { PanelTitle } from "../../components/ui";
import type { Division } from "../../types";
import "./FocalRegistration.css";

type Row = { email: string; first_name: string; last_name: string };
type Result = { created: number; invites_sent: number; results: { email: string; division: string; invite_sent: boolean }[] };
const empty: Row = { email: "", first_name: "", last_name: "" };

/** Register the Division Head of every division that does not have one yet, in one step. */
export function FocalRegistration({ divisions, onDone }: { divisions: Division[]; onDone: () => void }) {
  const pending = divisions.filter((d) => d.is_active && !d.focal);
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [rowErrors, setRowErrors] = useState<Record<string, Record<string, string>>>({});
  const [result, setResult] = useState<Result | null>(null);

  const get = (id: string): Row => rows[id] ?? empty;
  const set = (id: string, k: keyof Row, v: string) => setRows((r) => ({ ...r, [id]: { ...get(id), [k]: v } }));
  const filled = pending.filter((d) => get(d.id).email.trim());

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || !filled.length) return;
    setBusy(true); setError(""); setRowErrors({}); setResult(null);
    try {
      const res = await api<Result>("/admin/divisions/register-focals/", {
        json: { focals: filled.map((d) => ({ division: d.id, email: get(d.id).email.trim(), first_name: get(d.id).first_name.trim(), last_name: get(d.id).last_name.trim() })) },
      });
      setResult(res); setRows({}); onDone();
    } catch (x) {
      const body = ((x as ApiError).body as { rows?: Record<string, string[]>[] } | null)?.rows;
      setError((x as ApiError).message);
      if (body) {
        const next: Record<string, Record<string, string>> = {};
        body.forEach((r, i) => { if (Object.keys(r).length) next[filled[i].id] = Object.fromEntries(Object.entries(r).map(([k, v]) => [k, v.join(" ")])); });
        setRowErrors(next);
      }
    } finally { setBusy(false); }
  }

  return (
    <section className="card focal-register" aria-labelledby="focal-register-title">
      <PanelTitle icon="users"><span id="focal-register-title">Division Heads</span></PanelTitle>
      {result && (
        <div className="users-success" role="status"><Icon name="check" />
          <div>Registered {result.created} focal{result.created === 1 ? "" : "s"}. Invitation emails sent: {result.invites_sent} of {result.created}.
            {result.results.filter((r) => !r.invite_sent).map((r) => <div key={r.email} className="muted">Email to {r.email} could not be sent. Ask them to use “Forgot password” on the sign-in page.</div>)}
          </div>
        </div>
      )}
      {pending.length === 0 ? (
        <p className="focal-done"><Icon name="check" size={18} />Every active division has a Division Head.</p>
      ) : (
        <form onSubmit={submit} aria-busy={busy}>
          <p className="muted">{pending.length} division{pending.length === 1 ? " has" : "s have"} no Division Head. Enter the focal for each one and register them all at once. Leave a row empty to skip it. Each person gets an email with a link to choose their own password.</p>
          {error && <p className="error" role="alert">{error}</p>}
          <div className="focal-grid" role="group" aria-label="Divisional focals to register">
            <div className="focal-head" aria-hidden="true"><span>Division</span><span>Email *</span><span>First name</span><span>Last name</span></div>
            {pending.map((d) => {
              const re = rowErrors[d.id] ?? {};
              return (
                <div className="focal-row" key={d.id}>
                  <div className="focal-division"><span className="icon-tile"><Icon name="division" size={16} /></span><strong>{d.name}</strong></div>
                  <div><input type="email" disabled={busy} placeholder="focal@example.org" aria-label={`Email of the focal for ${d.name}`} aria-invalid={!!re.email} value={get(d.id).email} onChange={(e) => set(d.id, "email", e.target.value)} />{re.email && <small className="focal-error" role="alert">{re.email}</small>}</div>
                  <div><input disabled={busy} placeholder="First name" aria-label={`First name of the focal for ${d.name}`} value={get(d.id).first_name} onChange={(e) => set(d.id, "first_name", e.target.value)} /></div>
                  <div><input disabled={busy} placeholder="Last name" aria-label={`Last name of the focal for ${d.name}`} value={get(d.id).last_name} onChange={(e) => set(d.id, "last_name", e.target.value)} />{re.division && <small className="focal-error" role="alert">{re.division}</small>}</div>
                </div>
              );
            })}
          </div>
          <div className="focal-actions">
            <span className="muted">{filled.length} of {pending.length} ready to register</span>
            <button className="btn" disabled={busy || !filled.length}><Icon name="users" />{busy ? "Registering…" : `Register ${filled.length || "all"} focal${filled.length === 1 ? "" : "s"}`}</button>
          </div>
        </form>
      )}
    </section>
  );
}
