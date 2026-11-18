import { useState, type FormEvent } from "react";
import { useLocation } from "react-router-dom";
import { api, ApiError } from "../../api";
import { Field, PageHeader, StatusBadge, fmt } from "../../components/ui";
import { Icon, type IconName } from "../../components/Icon";
import "./Track.css";

interface Tracked { reference: string; public_status: string; public_status_display: string; created_at: string; updated_at: string }

const STAGES: { icon: IconName; label: string }[] = [
  { icon: "complaint", label: "Submitted" }, { icon: "search", label: "Under review" }, { icon: "check", label: "Decision" },
];

function stageOf(status: string): { index: number; end: "" | "ok" | "bad" } {
  if (status === "submitted") return { index: 0, end: "" };
  if (status === "resolved") return { index: 2, end: "ok" };
  if (status === "rejected") return { index: 2, end: "bad" };
  return { index: 1, end: "" };
}

export function Track() {
  const pre = (useLocation().state as { reference?: string } | null)?.reference ?? "";
  const [ref, setRef] = useState(pre);
  const [res, setRes] = useState<Tracked | null>(null);
  const [err, setErr] = useState("");

  async function go(e: FormEvent) {
    e.preventDefault();
    setErr(""); setRes(null);
    try { setRes(await api<Tracked>("/public/track/", { json: { reference: ref } })); }
    catch (x) { setErr((x as ApiError).message); }
  }
  const stage = res ? stageOf(res.public_status) : null;
  return (
    <div className="container track-page">
      <PageHeader icon="search" title="Track a complaint" subtitle="Enter the reference number you received when you submitted." />
      <form className="card track-search-card" onSubmit={go}>
        <Field label="Reference number" required><input required value={ref} onChange={(e) => setRef(e.target.value)} placeholder="BICMA-CMS-2026-000001" /></Field>
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
              const label = i === 2 && stage.end === "bad" ? "Rejected" : i === 2 && stage.end === "ok" ? "Resolved" : s.label;
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
          <footer className="tracking-result-footer"><Icon name="help" size={18} /><span>Keep your reference number to check for updates.</span></footer>
        </section>
      )}
    </div>
  );
}
