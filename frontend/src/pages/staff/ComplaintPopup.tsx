import { FocalAssignment } from "../../components/FocalAssignment";
import { Icon, type IconName } from "../../components/Icon";
import { useEffect, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { StatusBadge, fmt } from "../../components/ui";
import { type ComplaintDetail } from "../../types";
import { useList } from "../../useList";
import "./ComplaintPopup.css";

export function ComplaintPanel({ id, onClose, onAssigned }: { id: string; onClose: () => void; onAssigned?: () => void }) {
  const { data: c, err, reload } = useList<ComplaintDetail>(`/complaints/${id}/`);
  const closeBtn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeBtn.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden"; // keep the page behind the popup from scrolling
    return () => { document.body.style.overflow = prev; };
  }, []);
  const words = (t: string) => t.replace(/_/g, " ");
  const prop = (icon: IconName, label: string, value: ReactNode) => (
    <div className="prop"><dt><Icon name={icon} size={16} />{label}</dt><dd>{value}</dd></div>
  );
  return (
    <div className="side-panel" role="dialog" aria-modal="true" aria-label="Complaint details">
      <div className="side-panel-bar">
        <span className="complaint-reference"><Icon name="complaint" size={17} />{c?.reference ?? "Complaint details"}</span>
        <div>
          <Link className="icon-btn" to={`/staff/complaints/${id}`} aria-label="Open full page" title="Open full page"><Icon name="expand" size={18} /></Link>
          <button ref={closeBtn} className="icon-btn" onClick={onClose} aria-label="Close panel" title="Close (Esc)"><Icon name="close" size={18} /></button>
        </div>
      </div>
      {err && <p className="error" style={{ margin: 16 }} role="alert">{err}</p>}
      {!c && !err && <p className="muted" style={{ padding: 16 }}>Loading…</p>}
      {c && (
        <div className="side-panel-body">
          <header className="complaint-popup-hero">
            <span className="icon-tile lg"><Icon name="complaint" size={28} /></span>
            <div><p className="complaint-eyebrow">Complaint details</p><h2 className="side-title">{c.subject}</h2></div>
            <StatusBadge value={c.internal_status} label={c.internal_status_display} />
          </header>
          <section className="complaint-popup-summary" aria-label="Complaint overview">
          <dl className="props">
            {prop("user", "Assignee", c.assigned_to_name ? <span className="cell-user"><span className="avatar-sm" aria-hidden="true">{c.assigned_to_name[0].toUpperCase()}</span>{c.assigned_to_name}</span> : <span className="muted">Unassigned</span>)}
            {prop("division", "Division", c.division_name ?? <span className="muted">Unassigned</span>)}
            {prop("category", "Category", <>{c.category_name}{c.subcategory_name ? ` / ${c.subcategory_name}` : ""}</>)}
            {prop("send", "Received via", c.channel === "portal" ? "Public portal" : words(c.channel).replace(/^./, (letter) => letter.toUpperCase()))}
            {prop("pin", "Location", [c.gewog_name, c.dzongkhag_name].filter(Boolean).join(", ") || "Not provided")}
            {prop("history", "Received", fmt(c.created_at))}
          </dl>
          </section>
          <div className="complaint-popup-grid">
          <div className="complaint-popup-main">
          <section className="complaint-popup-card">
          <h3 className="side-h"><Icon name="complaint" size={18} />Description</h3>
          <div className="desc">{c.description}</div>
          {c.incident_date && <p className="incident-meta"><Icon name="clock" size={16} />Incident date: {new Date(c.incident_date + "T00:00:00").toLocaleDateString()}</p>}
          {c.additional_info && <p className="muted" style={{ marginBottom: 0 }}>{c.additional_info}</p>}
          </section>
          <section className="complaint-popup-card">
          <h3 className="side-h"><Icon name="history" size={16} />Activity</h3>
          <ol className="timeline">
            {c.status_history.map((h, i) => (
              <li key={i}>
                <span className="dot" aria-hidden="true"><Icon name={h.previous_status ? "refresh" : "plus"} size={14} /></span>
                <div className="what"><strong>{words(h.new_status).replace(/\b\w/g, (letter) => letter.toUpperCase())}</strong></div>
                <div className="when">{fmt(h.created_at)} · {h.actor ?? "Complainant"}</div>
                {h.reason && <div className="activity-reason">{h.reason}</div>}
              </li>
            ))}
            {c.status_history.length === 0 && <li className="muted">No activity recorded yet.</li>}
          </ol>
          </section>
          </div>
          <aside className="complaint-popup-card complaint-popup-contact">
          <h3 className="side-h"><Icon name="user" size={16} />Complainant</h3>
          <div className="complainant-identity"><span className="avatar-sm" aria-hidden="true">{c.complainant_name.slice(0, 1).toUpperCase()}</span><div><strong>{c.complainant_name}</strong><span className="muted">Complainant</span></div></div>
          <dl className="kv">
            {c.phone && <><dt>Phone</dt><dd>{c.phone}</dd></>}
            {c.email && <><dt>Email</dt><dd>{c.email}</dd></>}
            <dt>Prefers</dt><dd>{c.preferred_contact === "sms" ? "SMS" : words(c.preferred_contact).replace(/^./, (letter) => letter.toUpperCase())}</dd>
            {c.on_behalf && <><dt>On behalf of</dt><dd>{c.affected_name} ({c.affected_relationship})</dd></>}
          </dl>
          </aside>
          </div>
          <FocalAssignment complaint={c} onAssigned={() => { reload(); onAssigned?.(); }} />
          <footer className="complaint-popup-footer"><span className="muted">Last updated {fmt(c.updated_at)}</span><Link className="btn secondary" to={`/staff/complaints/${id}`}>View full complaint<Icon name="right" size={16} /></Link></footer>
        </div>
      )}
    </div>
  );
}
