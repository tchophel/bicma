import { useEffect, useRef, useState, type FormEvent } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../api";
import { Field, StatusBadge, fmt } from "../../components/ui";
import { Icon, type IconName } from "../../components/Icon";
import { WalkingMascot } from "../../components/WalkingMascot";
import { useToast } from "../../components/Toast";
import "../../styles/Track.css";

interface PublicMessage { kind: string; body: string; from: string; created_at: string }
interface Tracked {
  reference: string; public_status: string; public_status_display: string; created_at: string; updated_at: string;
  verified: boolean; messages?: PublicMessage[]; can_reply?: boolean;
  details?: { fields: { label: string; value: string }[]; documents: string[] };
}

const STAGES: { icon: IconName; label: string }[] = [
  { icon: "complaint", label: "Received" }, { icon: "search", label: "Under review" }, { icon: "check", label: "Outcome" },
];

function stageOf(status: string): { index: number; end: "" | "ok" | "bad" } {  // index 3 = finished successfully
  if (status === "received") return { index: 0, end: "" };
  if (status === "closed" || status === "resolved") return { index: 3, end: "ok" };  // past the last step: every step is done
  if (status === "not_within_mandate") return { index: 2, end: "bad" };
  return { index: 1, end: "" };
}

export function Track() {
  const toast = useToast();
  const [sp] = useSearchParams();
  // The "information needed" email links here with ?ref=<reference>&t=<secure token>.
  const pre = sp.get("ref") ?? (useLocation().state as { reference?: string } | null)?.reference ?? "";
  const [token, setToken] = useState(sp.get("t") ?? "");
  const [ref, setRef] = useState(pre);
  const [res, setRes] = useState<Tracked | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [replyErr, setReplyErr] = useState("");
  const [sending, setSending] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  async function lookup(reference = ref, withToken = token) {
    setBusy(true); setErr(""); setRes(null);
    try { setRes(await api<Tracked>("/public/track/", { json: { reference: reference.trim(), ...(withToken ? { token: withToken } : {}) } })); }
    catch (x) { setErr((x as ApiError).message); if (withToken) setToken(""); }
    finally { setBusy(false); }
  }
  useEffect(() => { if (pre) lookup(pre, token); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  // Typing a different reference drops the emailed link's access: status only.
  const go = (e: FormEvent) => { e.preventDefault(); if (busy) return; const t = ref.trim().toUpperCase() === pre.trim().toUpperCase() ? token : ""; lookup(ref, t); };

  async function sendReply(e: FormEvent) {
    e.preventDefault();
    if (sending || !res) return;
    setSending(true); setReplyErr("");
    const fd = new FormData();
    fd.append("reference", res.reference); fd.append("token", token); fd.append("message", reply);
    files.forEach((f) => fd.append("files", f));
    try {
      await api("/public/track/reply/", { form: fd });
      setReply(""); setFiles([]); if (fileInput.current) fileInput.current.value = "";
      toast.success("Your reply and documents have been sent to BICMA.");
      await lookup(res.reference, token);
    } catch (x) { setReplyErr((x as ApiError).message); }
    finally { setSending(false); }
  }

  const stage = res ? stageOf(res.public_status) : null;
  return (
    <div className="container track-page">
      <header className="track-hero">
        <span className="track-eyebrow"><Icon name="search" size={16} />BICMA COMPLAINT PORTAL</span>
        <h1>Track a complaint</h1>
        <p>Enter the reference number you received when you submitted.</p>
      </header>
      <form className="card track-search-card" onSubmit={go}>
        <Field label="Reference number" required hint="Find this in your confirmation email."><input required value={ref} onChange={(e) => setRef(e.target.value)} placeholder="BICMA-CMS-2026-000001" autoComplete="off" spellCheck={false} aria-invalid={!!err} aria-describedby={err ? "track-error" : undefined} /></Field>
        {err && <p id="track-error" className="error" role="alert">{err}</p>}
        <button className="btn" disabled={busy}><Icon name={busy ? "refresh" : "search"} />{busy ? "Checking…" : "Check status"}</button>
      </form>
      {res && stage && (
        <section className="card tracking-result" aria-live="polite" aria-label="Complaint tracking result">
          <header className="tracking-result-header"><span className="icon-tile lg"><Icon name="complaint" size={26} /></span><div><span className="tracking-eyebrow">COMPLAINT REFERENCE</span><h2>{res.reference}</h2></div><StatusBadge value={res.public_status} label={res.public_status_display} /></header>
          <div className="tracking-progress"><h3>Complaint progress</h3>
          <WalkingMascot key={res.reference + res.public_status} stage={stage.index} done={stage.index >= 3} />
          <div className="tracker" role="list" aria-label="Progress">
            {STAGES.map((s, i) => {
              const state = i < stage.index ? "done" : i === stage.index ? `current ${stage.end}` : "";
              const label = i === 2 && stage.end === "bad" ? "Outside jurisdiction" : i === 2 && res.public_status === "closed" ? "Closed" : i === 2 && res.public_status === "resolved" ? "Resolved" : s.label;
              return (
                <div key={s.label} role="listitem" className={`step ${state}`} aria-current={i === stage.index ? "step" : undefined}>
                  <div className="node"><Icon name={i < stage.index ? "check" : i === 2 && stage.end === "bad" ? "close" : s.icon} size={20} /></div><strong>{label}</strong><span className="tracking-step-caption">{i < stage.index ? "Completed" : i === stage.index ? "Current stage" : "Next stage"}</span>
                </div>
              );
            })}
          </div>
          </div>
          {res.details && (
            <div className="tracking-submitted" style={{ marginTop: 18 }}>
              <h3>Your complaint <span className="chip" style={{ marginLeft: 6 }}>View only</span></h3>
              <dl className="kv">
                {res.details.fields.map((x) => <div key={x.label} style={{ display: "contents" }}><dt>{x.label}</dt><dd style={{ whiteSpace: "pre-wrap" }}>{x.value}</dd></div>)}
                {res.details.documents.length > 0 && <><dt>Documents submitted</dt><dd>{res.details.documents.join(", ")}</dd></>}
              </dl>
            </div>
          )}
          {res.verified && !!res.messages?.length && (
            <div style={{ marginTop: 18 }}>
              <h3>Messages</h3>
              <ol className="timeline">
                {res.messages.map((m, i) => (
                  <li key={i}><span className="dot" aria-hidden="true"><Icon name={m.from === "BICMA" ? "mail" : "user"} size={14} /></span>
                    <div className="what"><strong>{m.from}</strong>{m.kind === "info_request" && <span className="badge warn" style={{ marginLeft: 8 }}>Information requested</span>}</div>
                    <div className="when">{fmt(m.created_at)}</div><div style={{ whiteSpace: "pre-wrap" }}>{m.body}</div></li>
                ))}
              </ol>
            </div>
          )}
          {res.can_reply && (
            <form onSubmit={sendReply} style={{ marginTop: 18 }}>
              <h3>Send the information BICMA asked for</h3>
              <Field label="Your reply" required><textarea required rows={4} maxLength={10000} value={reply} onChange={(e) => setReply(e.target.value)} /></Field>
              <Field label="Additional documents" hint="Optional. You can choose several files (photos, PDF and similar).">
                <input ref={fileInput} type="file" multiple onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
              </Field>
              {replyErr && <p className="error" role="alert">{replyErr}</p>}
              <button className="btn" disabled={sending}><Icon name="send" />{sending ? "Sending…" : "Send to BICMA"}</button>
            </form>
          )}
          <dl className="tracking-facts">
            <div><dt><Icon name="complaint" size={17} />Submitted</dt><dd><time dateTime={res.created_at}>{fmt(res.created_at)}</time></dd></div>
            <div><dt><Icon name="history" size={17} />Last updated</dt><dd><time dateTime={res.updated_at}>{fmt(res.updated_at)}</time></dd></div>
          </dl>
          <footer className="tracking-result-footer"><Icon name="help" size={18} /><span>Keep your reference number to check for updates.</span></footer>
        </section>
      )}
    </div>
  );
}
