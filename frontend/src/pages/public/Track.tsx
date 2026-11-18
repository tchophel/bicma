import { useState, type FormEvent } from "react";
import { useLocation } from "react-router-dom";
import { api, ApiError } from "../../api";
import { Field, PageHeader, StatusBadge, fmt } from "../../components/ui";
import { Icon, type IconName } from "../../components/Icon";
import "./Track.css";

interface PublicMessage { kind: string; body: string; from: string; created_at: string }
interface Tracked {
  reference: string; public_status: string; public_status_display: string; created_at: string; updated_at: string;
  verified: boolean; messages?: PublicMessage[]; can_reply?: boolean;
}

const STAGES: { icon: IconName; label: string }[] = [
  { icon: "complaint", label: "Received" }, { icon: "search", label: "Under review" }, { icon: "check", label: "Outcome" },
];

function stageOf(status: string): { index: number; end: "" | "ok" | "bad" } {
  if (status === "received") return { index: 0, end: "" };
  if (status === "closed") return { index: 2, end: "ok" };
  if (status === "not_within_mandate") return { index: 2, end: "bad" };
  return { index: 1, end: "" };
}

export function Track() {
  const pre = (useLocation().state as { reference?: string } | null)?.reference ?? "";
  const [ref, setRef] = useState(pre);
  const [contact, setContact] = useState("");
  const [res, setRes] = useState<Tracked | null>(null);
  const [err, setErr] = useState("");
  const [reply, setReply] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [sent, setSent] = useState("");
  const [busy, setBusy] = useState(false);

  async function lookup() {
    setErr(""); setRes(null);
    try { setRes(await api<Tracked>("/public/track/", { json: { reference: ref, contact: contact || undefined } })); }
    catch (x) { setErr((x as ApiError).message); }
  }
  const go = (e: FormEvent) => { e.preventDefault(); setSent(""); lookup(); };

  async function sendReply(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true); setErr(""); setSent("");
    const fd = new FormData();
    fd.append("reference", ref); fd.append("contact", contact); fd.append("message", reply);
    files.forEach((f) => fd.append("files", f));
    try {
      await api("/public/track/reply/", { form: fd });
      setReply(""); setFiles([]); setSent("Your reply has been sent to BICMA.");
      await lookup();
    } catch (x) { setErr((x as ApiError).message); }
    finally { setBusy(false); }
  }

  const stage = res ? stageOf(res.public_status) : null;
  return (
    <div className="container track-page">
      <PageHeader icon="search" title="Track a complaint" subtitle="Enter the reference number you received when you submitted." />
      <form className="card track-search-card" onSubmit={go}>
        <Field label="Reference number" required><input required value={ref} onChange={(e) => setRef(e.target.value)} placeholder="BICMA-CMS-2026-000001" /></Field>
        <Field label="Email or phone used on the complaint" hint="Optional. Enter it to read BICMA's messages and reply to requests for information.">
          <input value={contact} onChange={(e) => setContact(e.target.value)} placeholder="you@example.com or 17123456" autoComplete="off" />
        </Field>
        {err && <p className="error" role="alert">{err}</p>}
        <button className="btn"><Icon name="search" />Check status</button>
      </form>
      {res && stage && (
        <section className="card tracking-result" aria-live="polite" aria-label="Complaint tracking result">
          <header className="tracking-result-header"><span className="icon-tile lg"><Icon name="complaint" size={26} /></span><div><span className="tracking-eyebrow">COMPLAINT REFERENCE</span><h2>{res.reference}</h2></div><StatusBadge value={res.public_status} label={res.public_status_display} /></header>
          <div className="tracking-progress"><h3>Complaint progress</h3>
          <div className="tracker" role="list" aria-label="Progress">
            {STAGES.map((s, i) => {
              const state = i < stage.index ? "done" : i === stage.index ? `current ${stage.end}` : "";
              const label = i === 2 && stage.end === "bad" ? "Outside jurisdiction" : i === 2 && stage.end === "ok" ? "Closed" : s.label;
              return (
                <div key={s.label} role="listitem" className={`step ${state}`} aria-current={i === stage.index ? "step" : undefined}>
                  <div className="node"><Icon name={i < stage.index ? "check" : i === 2 && stage.end === "bad" ? "close" : s.icon} size={20} /></div><strong>{label}</strong><span className="tracking-step-caption">{i < stage.index ? "Completed" : i === stage.index ? "Current stage" : "Next stage"}</span>
                </div>
              );
            })}
          </div>
          </div>
          <dl className="tracking-facts">
            <div><dt><Icon name="clock" size={17} />Current status</dt><dd><StatusBadge value={res.public_status} label={res.public_status_display} /></dd></div>
            <div><dt><Icon name="complaint" size={17} />Submitted</dt><dd><time dateTime={res.created_at}>{fmt(res.created_at)}</time></dd></div>
            <div><dt><Icon name="history" size={17} />Last updated</dt><dd><time dateTime={res.updated_at}>{fmt(res.updated_at)}</time></dd></div>
          </dl>
          {res.verified && (
            <div style={{ marginTop: 18 }}>
              <h3>Messages</h3>
              {res.messages?.length === 0 && <p className="muted">There are no messages yet.</p>}
              <ol className="timeline">
                {res.messages?.map((m, i) => (
                  <li key={i}><span className="dot" aria-hidden="true"><Icon name={m.from === "BICMA" ? "mail" : "user"} size={14} /></span>
                    <div className="what"><strong>{m.from}</strong>{m.kind === "info_request" && <span className="badge warn" style={{ marginLeft: 8 }}>Information requested</span>}</div>
                    <div className="when">{fmt(m.created_at)}</div><div style={{ whiteSpace: "pre-wrap" }}>{m.body}</div></li>
                ))}
              </ol>
              {res.can_reply && (
                <form onSubmit={sendReply} style={{ marginTop: 16 }}>
                  <Field label="Your reply" required><textarea required rows={4} value={reply} onChange={(e) => setReply(e.target.value)} /></Field>
                  <Field label="Attach documents" hint="Optional. Large files may be rejected; try 5 MB or less per file."><input type="file" multiple onChange={(e) => setFiles(Array.from(e.target.files ?? []))} /></Field>
                  <button className="btn" disabled={busy}><Icon name="send" />{busy ? "Sending…" : "Send reply"}</button>
                </form>
              )}
              {sent && <p className="notice" role="status">{sent}</p>}
            </div>
          )}
          <footer className="tracking-result-footer"><Icon name="help" size={18} /><span>Keep your reference number to check for updates.</span></footer>
        </section>
      )}
    </div>
  );
}
