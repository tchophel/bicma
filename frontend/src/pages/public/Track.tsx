import { useState, type FormEvent } from "react";
import { useLocation } from "react-router-dom";
import { api, ApiError } from "../../api";
import { Field, StatusBadge, fmt } from "../../components/ui";
import { Icon, type IconName } from "../../components/Icon";
import { WalkingMascot } from "../../components/WalkingMascot";
import "../../styles/Track.css";

interface PublicMessage { kind: string; body: string; from: string; created_at: string }
interface Tracked {
  reference: string; public_status: string; public_status_display: string; created_at: string; updated_at: string;
  verified: boolean; messages?: PublicMessage[]; can_reply?: boolean;
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
  const pre = (useLocation().state as { reference?: string } | null)?.reference ?? "";
  const [ref, setRef] = useState(pre);
  const [res, setRes] = useState<Tracked | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function lookup() {
    if (busy) return;
    setBusy(true); setErr(""); setRes(null);
    try { setRes(await api<Tracked>("/public/track/", { json: { reference: ref.trim() } })); }
    catch (x) { setErr((x as ApiError).message); }
    finally { setBusy(false); }
  }
  const go = (e: FormEvent) => { e.preventDefault(); lookup(); };

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
