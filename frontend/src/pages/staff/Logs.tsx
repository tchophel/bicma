import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { PageHeader, fmt } from "../../components/ui";
import { useList } from "../../useList";
import { api, ApiError } from "../../api";
import { Modal } from "../../components/Modal";
import { Field } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { AuditLogs } from "./AuditLogs";
import { ApiStatus } from "../../components/ApiStatus";

type Kind = "audit" | "api" | "email" | "sms";
const TABS: { key: Kind; label: string }[] = [
  { key: "audit", label: "Audit" }, { key: "api", label: "API" }, { key: "email", label: "Email (SMTP)" }, { key: "sms", label: "SMS" },
];
interface Row { id: string; created_at: string; [k: string]: unknown }
interface Data { count: number; page: number; pages: number; results: Row[] }

const statusBadge = (s: number) => <span className={`badge ${s >= 200 && s < 400 ? "ok" : "bad"}`}>{s || "no response"}</span>;
const sendBadge = (s: string) => <span className={`badge ${s === "sent" ? "ok" : "bad"}`}>{s}</span>;

/** Administration > Logs: audit trail, API calls, email (SMTP) and SMS, in one place. */
export function Logs() {
  const [sp, setSp] = useSearchParams();
  const tab = (TABS.find((t) => t.key === sp.get("tab"))?.key ?? "audit") as Kind;
  return (
    <>
      <PageHeader icon="history" title="Logs" subtitle="Audit trail, calls to the external APIs (DCRC and ZESt) with their up and down status, emails sent through SMTP, and SMS. Message bodies, tokens and query values are never stored." />
      <div role="tablist" aria-label="Log type" style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "0 0 16px" }}>
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} type="button" className={tab === t.key ? "btn" : "btn secondary"} onClick={() => setSp({ tab: t.key })}>{t.label}</button>
        ))}
      </div>
      {tab === "audit" ? <AuditLogs embedded /> : tab === "api" ? <><ApiStatus /><LogTable key={tab} kind={tab} /></> : <LogTable key={tab} kind={tab} />}
    </>
  );
}

function LogTable({ kind }: { kind: "api" | "email" | "sms" }) {
  const [q, setQ] = useState("");
  const [result, setResult] = useState("");
  const [service, setService] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const params = new URLSearchParams({ page: String(page), page_size: "25" });
  if (q) params.set("q", q);
  if (result) params.set("result", result);
  if (service && kind === "api") params.set("service", service);
  if (from) params.set("date_from", from);
  if (to) params.set("date_to", to);
  const { data, err, loading, reload } = useList<Data>(`/admin/logs/${kind}/?${params}`);
  const reset = (fn: () => void) => { fn(); setPage(1); };
  const toast = useToast();
  const [fixing, setFixing] = useState<Row | null>(null);   // the failed email whose address is being corrected
  const [address, setAddress] = useState("");
  const [working, setWorking] = useState<string | null>(null);
  const [fixErr, setFixErr] = useState("");
  /** Sends a failed case email again, to the same address or to a corrected one. */
  async function resend(r: Row, to?: string) {
    setWorking(r.id); setFixErr("");
    try {
      const res = await api<{ status: string; recipient: string; error: string }>(`/admin/logs/email/${r.id}/resend/`, { json: to ? { recipient: to } : {} });
      if (res.status === "sent") toast.success(`Sent to ${res.recipient}.`);
      else toast.error(`Still could not send to ${res.recipient}: ${res.error || "the mail server did not accept it"}.`);
      setFixing(null); reload();
    } catch (x) { setFixErr((x as ApiError).message); toast.error((x as ApiError).message); }
    finally { setWorking(null); }
  }
  const cols = kind === "api" ? ["When", "API", "Method", "Address", "Status", "Time", "Note"]
    : kind === "email" ? ["When", "Type", "To", "Subject", "Case", "Status", "Error", "Action"] : ["When", "Type", "To", "Message", "Case", "Status", "Error"];
  return (
    <>
      <div className="card filter-bar" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
        <label><span>Search</span><div className="search-wrap"><Icon name="search" /><input value={q} onChange={(e) => reset(() => setQ(e.target.value))} placeholder={kind === "api" ? "Address or error" : "Recipient, subject or case"} /></div></label>
        {kind === "api" && <label><span>API</span><select value={service} onChange={(e) => reset(() => setService(e.target.value))}><option value="">All</option><option value="dcrc">DCRC (citizen details)</option><option value="zest">ZESt</option></select></label>}
        <label><span>Result</span>
          <select value={result} onChange={(e) => reset(() => setResult(e.target.value))}>
            <option value="">All</option>
            {kind === "api" ? <><option value="ok">Successful</option><option value="errors">Errors</option></> : <><option value="sent">Sent</option><option value="failed">Failed</option></>}
          </select></label>
        <label><span>From</span><input type="date" value={from} onChange={(e) => reset(() => setFrom(e.target.value))} /></label>
        <label><span>To</span><input type="date" value={to} onChange={(e) => reset(() => setTo(e.target.value))} /></label>
      </div>
      {err && <p className="error" role="alert">{err}</p>}
      {kind === "sms" && !loading && data?.count === 0 && <p className="notice"><Icon name="help" size={18} /> SMS is a later phase, so nothing has been sent yet. Messages will appear here once an SMS gateway is connected.</p>}
      <div className="table-wrap"><table>
        <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {data?.results.map((r) => kind === "api" ? (
            <tr key={r.id}><td>{fmt(r.created_at)}</td><td>{String(r.service || "").toUpperCase()}</td><td>{String(r.method)}</td><td><code>{String(r.path)}</code></td><td>{statusBadge(Number(r.status))}</td><td>{String(r.duration_ms)} ms</td><td>{String(r.error || "")}</td></tr>
          ) : (
            <tr key={r.id}><td>{fmt(r.created_at)}</td><td>{String(r.kind).replace(/_/g, " ")}</td><td>{String(r.recipient)}</td><td>{String(kind === "email" ? r.subject : r.message)}</td><td>{String(r.reference || "—")}</td><td>{sendBadge(String(r.status))}</td><td>{String(r.error || "")}</td>{kind === "email" && <td>{r.resendable ? <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}><button type="button" className="btn secondary" disabled={working === r.id} onClick={() => resend(r)}><Icon name="refresh" size={15} />{working === r.id ? "Sending…" : "Resend"}</button><button type="button" className="btn secondary" disabled={working === r.id} onClick={() => { setFixing(r); setAddress(String(r.recipient)); setFixErr(""); }}><Icon name="edit" size={15} />Edit address</button></span> : r.status === "failed" ? <span className="muted" title="This email holds a one-time code or was delivered later. The person can ask for a new one.">Cannot be resent</span> : "—"}</td>}</tr>
          ))}
        </tbody>
      </table>
      {!loading && data?.results.length === 0 && <p className="muted" style={{ padding: 16 }}>No entries match.</p>}</div>
      <Modal open={!!fixing} onClose={() => setFixing(null)} title="Correct the email address" icon="mail" busy={working !== null}>
        {fixing && (
          <form onSubmit={(e) => { e.preventDefault(); void resend(fixing, address.trim()); }}>
            <p className="muted">The email “{String(fixing.subject)}” could not be sent{fixing.error ? ` (${String(fixing.error)})` : ""}. Fix the address and it is sent again straight away. The corrected address is saved on the case.</p>
            {fixErr && <p className="error" role="alert">{fixErr}</p>}
            <Field label="Send to (email address)" required><input type="email" required autoFocus value={address} onChange={(e) => setAddress(e.target.value)} /></Field>
            <button className="btn" disabled={working !== null || !address.trim()}><Icon name="send" />{working ? "Sending…" : "Save and send again"}</button>
          </form>
        )}
      </Modal>
      <div className="pager">
        <span className="muted">{data?.count ?? 0} entr{data?.count === 1 ? "y" : "ies"}</span>
        <div>
          <button className="btn secondary" onClick={reload}><Icon name="refresh" size={16} />Refresh</button>
          <button className="btn secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}><Icon name="left" size={16} />Previous</button>
          <span aria-live="polite">{page} / {data?.pages ?? 1}</span>
          <button className="btn secondary" disabled={!data || page >= data.pages} onClick={() => setPage(page + 1)}>Next<Icon name="right" size={16} /></button>
        </div>
      </div>
    </>
  );
}
