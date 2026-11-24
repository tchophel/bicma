import { WalkingMascot } from "../../components/WalkingMascot";
import { CaseActions } from "../../components/CaseActions";
import { Loader } from "../../components/Loader";
import { Icon } from "../../components/Icon";
import { FileLink } from "../../components/FileLink";
import { Link, useParams } from "react-router-dom";
import { Documents } from "../../components/Documents";
import { PanelTitle, StatusBadge, fmt, fmtDate } from "../../components/ui";
import { type ComplaintDetail } from "../../types";
import { useList } from "../../useList";
import "../../styles/ComplaintDetail.css";

const SLA: Record<string, [string, string]> = { overdue: ["bad", "Overdue"], due_soon: ["warn", "Due soon"], paused: ["warn", "Clock paused"], ok: ["ok", "On track"] };

/** What each logged email was for, so the list says who got what. */
const EMAIL_KINDS: Record<string, string> = {
  acknowledgement: "Receipt to complainant", status_change: "Status update to complainant", info_request: "Information request to complainant",
  resolution: "Resolution to complainant", closure: "Closure to complainant", not_within_mandate: "Outside-mandate notice to complainant",
  stakeholder_review: "Provider notice", assignment: "To assigned officer", referral: "To Division Head", returned: "To Division Head",
  resolution_submitted: "To Division Head", resolution_rejected: "To officer", approval_requested: "To Supervisor", management_rejected: "To Division Head",
  info_reply: "To officer", followup_added: "To officer",
};

export function ComplaintView() {
  const { id } = useParams();
  const { data: c, err, reload } = useList<ComplaintDetail>(`/complaints/${id}/`);
  if (err) return <p className="error" role="alert">{err}</p>;
  if (!c) return <Loader />;
  const row = (k: string, v: string | null | undefined) => v ? <><dt>{k}</dt><dd>{v}</dd></> : null;
  // Phone and Email always show: the address as a mail link, or why there is none
  const contact = (k: string, v: string | null | undefined, mail = false) => (
    <><dt>{k}</dt><dd>{v ? (mail ? <a href={`mailto:${v}`}>{v}</a> : v) : <span className="muted">{c.confidential ? "Hidden (confidential)" : "Not provided"}</span>}</dd></>
  );
  const words = (t: string) => t.replace(/_/g, " ");
  const sla = SLA[c.sla_state];
  return (
    <div className="case-detail-page">
      <p className="case-back"><Link to="/staff/complaints"><Icon name="left" />All complaints</Link></p>
      <section className="card detail-head" aria-label="Complaint summary">
        <div className="case-summary-overview">
        <span className="icon-tile lg" aria-hidden="true"><Icon name="complaint" size={30} /></span>
        <div className="case-heading-copy">
          <span className="case-summary-eyebrow">COMPLAINT OVERVIEW</span>
          <h1>{c.subject.startsWith(`${c.category_name}: `) ? c.subject.slice(c.category_name.length + 2) : c.subject}</h1>
          <div className="meta">
            <strong>{c.reference}</strong>
            <StatusBadge value={c.internal_status} label={c.internal_status_display} />
            {c.priority_name && <span className="chip">{c.priority_name} priority</span>}
            {sla && <span className={`badge ${sla[0]}`}>{sla[1]}{c.resolution_due_at && c.sla_state !== "paused" ? ` · due ${fmtDate(c.resolution_due_at)}` : ""}</span>}
            {c.confidential && <span className="badge warn"><Icon name="lock" size={14} />Confidential identity</span>}
            <span className="chip plain">{c.category_name}{c.subcategory_name ? ` / ${c.subcategory_name}` : ""}</span>
            <span className="received-at">
              <span className="muted">Received</span>
              <time dateTime={c.created_at} className="stamp"><Icon name="calendar" size={15} />{new Date(c.created_at).toLocaleDateString()}</time>
              <time dateTime={c.created_at} className="stamp"><Icon name="clock" size={15} />{new Date(c.created_at).toLocaleTimeString()}</time>
            </span>
          </div>
        </div>
        </div>
        <div className="head-history" aria-label="Case history">
          <h2><Icon name="history" size={17} />Complaint progress</h2>
          <div className="case-history-walk">
          <WalkingMascot key={`${c.id}-${c.status_history.length}`} stage={Math.max(0, c.status_history.length - 1)} steps={Math.max(1, c.status_history.length)} durationMs={16000} speech={c.internal_status_display} speechStatus={c.internal_status} done={c.internal_status === "closed" || c.internal_status === "resolved"} />
          </div>
          <ol className="case-status-steps" aria-label="Complaint status progress">
            {c.status_history.map((h, i) => <li key={i} data-status={h.new_status} aria-current={i === c.status_history.length - 1 ? "step" : undefined}><span className="case-status-node"><Icon name={i === c.status_history.length - 1 ? "complaint" : "check"} size={14} /></span><strong>{h.new_status === c.internal_status ? c.internal_status_display : words(h.new_status)}</strong></li>)}
          </ol>
        </div>
      </section>
      <div className="detail-grid">
        <div className="case-main">
          <section className="card"><PanelTitle icon="complaint">Complaint</PanelTitle>
            <div className="desc">{c.description}</div>
            <dl className="kv" style={{ marginTop: 14 }}>
              {c.details_display?.map((d) => row(d.label, d.value))}
              {c.complaining_for && c.complaining_for !== "self" && row("Complaining on behalf of", `${words(c.complaining_for)}${c.other_party_name ? `: ${c.other_party_name}` : ""}`)}
              {c.complaining_for && c.complaining_for !== "self" && <>{row("Complainant's relationship / designation", c.affected_relationship)}{row("Their contact details", c.affected_contact)}{c.authorised_to_act && <><dt>Authorised to act for them</dt><dd>{c.authorised_to_act === "yes" ? "Yes" : <strong style={{ color: "var(--c-accent)" }}>No: ask for proof of authority</strong>}</dd></>}</>}
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
              {row(c.complainant_type === "individual" ? "CID" : "Registration / licence no.", c.cid)}{contact("Phone", c.phone)}{contact("Email", c.email, true)}
              <dt>Prefers</dt><dd>{c.preferred_contact}</dd>
              {c.on_behalf && <>{row("On behalf of", c.affected_name)}{row("Relationship", c.affected_relationship)}{row("Their contact", c.affected_contact)}</>}
            </dl>
          </section>
          <section className="card"><PanelTitle icon="division">Assignment</PanelTitle>
            <dl className="kv">
              <dt>Division</dt><dd>{c.division_name ?? "Unassigned"}</dd>
              <dt>Main officer</dt><dd>{c.assigned_to_name ?? "—"}</dd>
              {c.joined_officers.length > 0 && <><dt>Joined officers</dt><dd>{c.joined_officers.map((o) => o.name).join(", ")}</dd></>}
              <dt>Public status</dt><dd><StatusBadge value={c.public_status} label={words(c.public_status)} /></dd>
              {row("First response", c.first_response_at && fmt(c.first_response_at))}
              {row("Resolution due", c.resolution_due_at && fmt(c.resolution_due_at))}
              {row("Resolved", c.resolved_at && fmt(c.resolved_at))}
              {row("Closed", c.closed_at && fmt(c.closed_at))}
            </dl>
          </section>
          <details className="card case-sidebar-disclosure">
            <summary><Icon name="complaint" size={19} /><strong>Documents</strong><span>{c.attachments.length} files</span><Icon name="chev" size={16} /></summary>
            <Documents c={c} onDone={reload} />
          </details>
          {c.follow_ups.length > 0 && (
            <details className="card case-sidebar-disclosure">
              <summary><Icon name="mail" size={19} /><strong>Additional information</strong><span>{c.follow_ups.length} from complainant</span><Icon name="chev" size={16} /></summary>
              <ol className="timeline">
                {c.follow_ups.map((f) => (
                  <li key={f.id}><span className="dot" aria-hidden="true"><Icon name="user" size={14} /></span>
                    <div className="when">{fmt(f.created_at)}</div>
                    {f.body && <div style={{ whiteSpace: "pre-wrap" }}>{f.body}</div>}
                    {f.files.map((x) => <div key={x.id}><FileLink href={`/api/complaints/${c.id}/followup-files/${x.id}/`} name={x.original_name} icon /></div>)}
                  </li>
                ))}
              </ol>
            </details>
          )}
          {c.related.length > 0 && (
            <section className="card"><PanelTitle icon="refresh">Recurring complaints</PanelTitle>
              <p className="muted">Same category, provider and location.</p>
              <ul>{c.related.map((r) => <li key={r.id}><Link to={`/staff/complaints/${r.id}`}>{r.reference}</Link> · {r.status}</li>)}</ul>
            </section>
          )}
          <details className="card case-sidebar-disclosure">
            <summary><Icon name="mail" size={19} /><strong>Emails sent</strong><span>{c.notifications.length} emails</span><Icon name="chev" size={16} /></summary>
            {c.notifications.length === 0 && <p className="muted">None yet.</p>}
            <ul className="case-emails">{c.notifications.map((n) => (
              <li key={n.id}><span className="case-email-icon"><Icon name="mail" size={17} /></span>
                <div>
                  <span className="case-email-kind">{EMAIL_KINDS[n.event] ?? words(n.event)}</span>
                  <strong>{n.subject}</strong>
                  <span className="case-email-recipient"><b>To:</b> {n.recipient}</span>
                  <div className="case-email-meta"><span>{n.status === "sent" ? "Sent" : "Not delivered"} <time>{fmt(n.created_at)}</time></span><span className={`badge ${n.status === "sent" ? "ok" : "bad"}`}>{n.status}</span></div>
                </div></li>))}</ul>
          </details>
        </aside>
      </div>
    </div>
  );
}
