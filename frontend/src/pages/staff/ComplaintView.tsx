import { FocalAssignment } from "../../components/FocalAssignment";
import { Icon } from "../../components/Icon";
import { Link, useParams } from "react-router-dom";
import { PanelTitle, StatusBadge, fmt, fmtDate } from "../../components/ui";
import { type ComplaintDetail } from "../../types";
import { useList } from "../../useList";
import "./ComplaintDetail.css";

export function ComplaintView() {
  const { id } = useParams();
  const { data: c, err, reload } = useList<ComplaintDetail>(`/complaints/${id}/`);
  if (err) return <p className="error" role="alert">{err}</p>;
  if (!c) return <p>Loading…</p>;
  const row = (k: string, v: string | null | undefined) => v ? <><dt>{k}</dt><dd>{v}</dd></> : null;
  const words = (t: string) => t.replace(/_/g, " ");
  return (
    <>
      <p><Link to="/staff/complaints"><Icon name="left" />All complaints</Link></p>
      <section className="card detail-head" aria-label="Complaint summary">
        <span className="icon-tile lg" aria-hidden="true"><Icon name="complaint" size={30} /></span>
        <div style={{ flex: 1, minWidth: 240 }}>
          <h1>{c.subject}</h1>
          <div className="meta">
            <strong>{c.reference}</strong>
            <StatusBadge value={c.internal_status} label={c.internal_status_display} />
            <span className="chip plain">{c.category_name}{c.subcategory_name ? ` / ${c.subcategory_name}` : ""}</span>
            <span className="muted">Received {fmt(c.created_at)}</span>
          </div>
        </div>
      </section>
      <div className="detail-grid">
        <div style={{ display: "grid", gap: 16 }}>
          <section className="card"><PanelTitle icon="complaint">Complaint</PanelTitle>
            <div className="desc">{c.description}</div>
            <dl className="kv" style={{ marginTop: 14 }}>
              {row("Date of incident", c.incident_date && fmtDate(c.incident_date))}
              {row("Platform / provider", c.platform)}
              {row("Website / social page", c.website_or_social)}
              {row("Additional information", c.additional_info)}
              <dt>Channel</dt><dd>{words(c.channel)}</dd>
              {row("Registered by", c.registered_by_name)}
            </dl>
          </section>
          <section className="card"><PanelTitle icon="history">Status history</PanelTitle>
            <ol className="timeline">
              {c.status_history.map((h, i) => (
                <li key={i}>
                  <span className="dot" aria-hidden="true"><Icon name={h.previous_status ? "refresh" : "plus"} size={14} /></span>
                  <div className="what"><strong>{words(h.new_status)}</strong>{h.previous_status && <span className="muted"> (from {words(h.previous_status)})</span>}</div>
                  <div className="when">{fmt(h.created_at)} · {h.actor ?? "Complainant"}</div>
                  {h.reason && <div>{h.reason}</div>}
                </li>
              ))}
            </ol>
          </section>
        </div>
        <div style={{ display: "grid", gap: 16 }}>
          <section className="card"><PanelTitle icon="user">Complainant</PanelTitle>
            <dl className="kv">
              <dt>Name</dt><dd>{c.complainant_name}</dd>
              {row("Phone", c.phone)}{row("Email", c.email)}
              {row("Location", [c.gewog_name, c.dzongkhag_name].filter(Boolean).join(", "))}
              <dt>Prefers</dt><dd>{c.preferred_contact}</dd>
              {c.on_behalf && <>{row("On behalf of", c.affected_name)}{row("Relationship", c.affected_relationship)}{row("Their contact", c.affected_contact)}</>}
            </dl>
          </section>
          <section className="card"><PanelTitle icon="division">Assignment</PanelTitle>
            <dl className="kv">
              <dt>Division</dt><dd>{c.division_name ?? "Unassigned"}</dd>
              <dt>Officer</dt><dd>{c.assigned_to_name ?? "—"}</dd>
              <dt>Public status</dt><dd>{words(c.public_status)}</dd>
            </dl>
          </section>
        </div>
      </div>
      <FocalAssignment complaint={c} onAssigned={reload} />
    </>
  );
}
