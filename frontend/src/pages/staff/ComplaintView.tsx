import { CaseActions } from "../../components/CaseActions";
import { Loader } from "../../components/Loader";
import { Icon } from "../../components/Icon";
import { Link, useParams } from "react-router-dom";
import { Documents } from "../../components/Documents";
import { PanelTitle, StatusBadge, fmt, fmtDate } from "../../components/ui";
import { type ComplaintDetail } from "../../types";
import { useList } from "../../useList";
import "../../styles/ComplaintDetail.css";

const SLA: Record<string, [string, string]> = { overdue: ["bad", "Overdue"], due_soon: ["warn", "Due soon"], paused: ["warn", "Clock paused"], ok: ["ok", "On track"] };

export function ComplaintView() {
  const { id } = useParams();
  const { data: c, err, reload } = useList<ComplaintDetail>(`/complaints/${id}/`);
  if (err) return <p className="error" role="alert">{err}</p>;
  if (!c) return <Loader />;
  const row = (k: string, v: string | null | undefined) => v ? <><dt>{k}</dt><dd>{v}</dd></> : null;
  const words = (t: string) => t.replace(/_/g, " ");
  const sla = SLA[c.sla_state];
  return (
    <div className="case-detail-page">
      <p className="case-back"><Link to="/staff/complaints"><Icon name="left" />All complaints</Link></p>
      <section className="card detail-head" aria-label="Complaint summary">
        <span className="icon-tile lg" aria-hidden="true"><Icon name="complaint" size={30} /></span>
        <div style={{ flex: 1, minWidth: 240 }}>
          <h1>{c.subject}</h1>
          <div className="meta">
            <strong>{c.reference}</strong>
            <StatusBadge value={c.internal_status} label={c.internal_status_display} />
            {c.priority_name && <span className="chip">{c.priority_name} priority</span>}
            {sla && <span className={`badge ${sla[0]}`}>{sla[1]}{c.resolution_due_at && c.sla_state !== "paused" ? ` · due ${fmtDate(c.resolution_due_at)}` : ""}</span>}
            {c.confidential && <span className="badge warn"><Icon name="lock" size={14} />Confidential identity</span>}
            <span className="chip plain">{c.category_name}{c.subcategory_name ? ` / ${c.subcategory_name}` : ""}</span>
            <span className="muted">Received {fmt(c.created_at)}</span>
          </div>
        </div>
      </section>
      <div className="detail-grid">
        <div className="case-main">
          <section className="card"><PanelTitle icon="history">Case history</PanelTitle>
            <ol className="timeline case-history">
              {c.status_history.map((h, i) => (
                <li key={i}>
                  <span className="dot" aria-hidden="true"><Icon name={h.previous_status ? "refresh" : "plus"} size={14} /></span>
                  <div className="what"><StatusBadge value={h.new_status} label={words(h.new_status)} />{h.previous_status && <span className="history-previous">from {words(h.previous_status)}</span>}</div>
                  <div className="when">{fmt(h.created_at)} · {h.actor ?? "Complainant"}</div>
                  {h.reason && <div>{h.reason}</div>}
                </li>
              ))}
            </ol>
          </section>
          <section className="card"><PanelTitle icon="complaint">Complaint</PanelTitle>
            <div className="desc">{c.description}</div>
            <dl className="kv" style={{ marginTop: 14 }}>
              {c.details_display?.map((d) => row(d.label, d.value))}
              {c.complaining_for && c.complaining_for !== "self" && row("Complaining on behalf of", `${words(c.complaining_for)}${c.other_party_name ? `: ${c.other_party_name}` : ""}`)}
              {row("Present address", c.present_address)}
              {row("Remedy sought", c.remedy_sought)}
              {row("Incident", [c.incident_date && fmtDate(c.incident_date), c.incident_time?.slice(0, 5)].filter(Boolean).join(" at "))}
              {row("Provider / company", c.provider_name)}{row("Provider type", c.provider_type_name)}
              {c.already_complained && row("Provider reference", c.provider_reference)}
              {row("Medium of publication", c.medium_of_publication)}
              {row("Date of publication", c.publication_date && fmtDate(c.publication_date))}
              {row("Nature of complaint", c.nature_of_complaint)}
              {row("Post / article link", c.publication_url)}
              {row("Concerned frequency", c.concerned_frequency)}
              {row("Authority referred to", [c.authority_referred_to, c.referral_date && fmtDate(c.referral_date)].filter(Boolean).join(" · "))}
              {row("Location", [c.locality, c.dzongkhag_name].filter(Boolean).join(", "))}
              {row("Area type", c.area_type && c.area_type[0].toUpperCase() + c.area_type.slice(1))}
              {row("Website / social page", c.website_or_social)}
              {row("Additional information", c.additional_info)}
              <dt>Channel</dt><dd>{words(c.channel)}</dd>
              {row("Date received", c.date_received && fmtDate(c.date_received))}
              {row("Registered by", c.registered_by_name)}
              {row("Declaration", c.declaration_accepted ? "Accepted by complainant" : "")}
            </dl>
          </section>
          <CaseActions key={`${c.version}-${c.messages.length}`} c={c} onDone={reload} />
        </div>
        <aside className="case-sidebar">
          <section className="card"><PanelTitle icon="user">Complainant</PanelTitle>
            <dl className="kv">
              <dt>Name</dt><dd>{c.complainant_name}</dd>
              {row(c.complainant_type === "individual" ? "CID" : "Registration / licence no.", c.cid)}{row("Phone", c.phone)}{row("Email", c.email)}
              <dt>Prefers</dt><dd>{c.preferred_contact}</dd>
              {c.on_behalf && <>{row("On behalf of", c.affected_name)}{row("Relationship", c.affected_relationship)}{row("Their contact", c.affected_contact)}</>}
            </dl>
          </section>
          <section className="card"><PanelTitle icon="division">Assignment</PanelTitle>
            <dl className="kv">
              <dt>Division</dt><dd>{c.division_name ?? "Unassigned"}</dd>
              <dt>Officer</dt><dd>{c.assigned_to_name ?? "—"}</dd>
              <dt>Public status</dt><dd>{words(c.public_status)}</dd>
              {row("First response", c.first_response_at && fmt(c.first_response_at))}
              {row("Resolution due", c.resolution_due_at && fmt(c.resolution_due_at))}
              {row("Resolved", c.resolved_at && fmt(c.resolved_at))}
              {row("Closed", c.closed_at && fmt(c.closed_at))}
            </dl>
          </section>
          <Documents c={c} onDone={reload} />
          {c.related.length > 0 && (
            <section className="card"><PanelTitle icon="refresh">Recurring complaints</PanelTitle>
              <p className="muted">Same category, provider and location.</p>
              <ul>{c.related.map((r) => <li key={r.id}><Link to={`/staff/complaints/${r.id}`}>{r.reference}</Link> · {r.status}</li>)}</ul>
            </section>
          )}
          <section className="card"><PanelTitle icon="mail">Emails sent</PanelTitle>
            {c.notifications.length === 0 && <p className="muted">None yet.</p>}
            <ul className="case-emails">{c.notifications.map((n) => <li key={n.id}><span className="case-email-icon"><Icon name="mail" size={17} /></span><div><strong>{n.subject}</strong><span className="case-email-recipient">{n.recipient}</span><div className="case-email-meta"><time>{fmt(n.created_at)}</time><span className={`badge ${n.status === "sent" ? "ok" : "bad"}`}>{n.status}</span></div></div></li>)}</ul>
          </section>
        </aside>
      </div>
    </div>
  );
}
