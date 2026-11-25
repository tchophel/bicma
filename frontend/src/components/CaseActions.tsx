import { useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { useList } from "../useList";
import type { ComplaintDetail, Meta } from "../types";
import { Field, PanelTitle } from "./ui";
import { Icon } from "./Icon";
import { useToast } from "./Toast";
import { Modal } from "./Modal";
import { SimilarComplaints } from "./SimilarComplaints";
import { FileLink } from "./FileLink";
import { UploadDocuments } from "./Documents";
import { EmailChips } from "./EmailChips";

const DONE: Record<string, string> = {
  join: "Joined officers updated.", triage: "Triage confirmed.", assign: "Officer assigned.", refer: "Complaint referred.", "not-in-mandate": "Closed as not within BICMA jurisdiction.",
  start: "Investigation started.", "save-findings": "Findings saved.", "request-info": "Information requested from the complainant.", resume: "Investigation resumed.", return: "Returned to the Division Head. It is no longer in your list.",
  resolve: "Findings sent to the Division Head.", "send-to-management": "Sent to the Supervisor for approval.", "mgmt-approve": "Accepted. The case is Resolved and goes to the Division Head to close.", "mgmt-reject": "Returned to the Division Head to decide the next step.", "send-back": "Sent back to the Investigating Officer.", approve: "Complaint approved and closed.", reject: "Returned to the officer.", reopen: "Complaint reopened.",
  "public-message": "Message sent to the complainant.", "internal-note": "Note added.", "stakeholder-review": "Notice sent to the provider.",
};

function useDo(c: ComplaintDetail, onDone: () => void) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const toast = useToast();
  const navigate = useNavigate();
  async function run(name: string, body: Record<string, unknown> | FormData) {
    if (busy) return false;
    setBusy(true); setErr(null);
    try {
      const path = `/complaints/${c.id}/${name}/`;
      await (body instanceof FormData ? api(path, { form: body }) : api(path, { json: body }));
      if (name === "return") {  // the case is no longer this officer's, so leave its page instead of reloading it
        toast.success(DONE[name]);
        navigate("/staff/complaints", { replace: true });
        return true;
      }
      onDone();
      toast.success(DONE[name] ?? "Done.");
      return true;
    } catch (x) { setErr(x as ApiError); toast.error((x as ApiError).message); return false; }
    finally { setBusy(false); }
  }
  return { busy, err, run, f: (k: string) => err?.fields[k] };
}

const Err = ({ e }: { e: ApiError | null }) => (e ? <p className="error" role="alert">{e.message}</p> : null);

function Block({ icon, title, children }: { icon: Parameters<typeof PanelTitle>[0]["icon"]; title: string; children: ReactNode }) {
  return <section className="card"><PanelTitle icon={icon}>{title}</PanelTitle>{children}</section>;
}

/** Triage, assignment, referral and "not within mandate". */
function Triage({ c, meta, onDone }: { c: ComplaintDetail; meta: Meta; onDone: () => void }) {
  const p = c.permissions;
  const { busy, err, run, f } = useDo(c, onDone);
  const [priority, setPriority] = useState(c.priority ?? "");
  const [category, setCategory] = useState(c.category ?? "");
  const [subcategory, setSubcategory] = useState(c.subcategory ?? "");
  const division = c.division ?? "";  // kept as is: triage no longer edits the division
  const [confCase, setConfCase] = useState(c.confidential_case);
  const [officer, setOfficer] = useState(c.assigned_to ?? "");  // starts on whoever is assigned now; change it only to reassign
  const [routing, setRouting] = useState<"assign" | "refer" | "join">(p.assign ? "assign" : p.refer ? "refer" : "join");
  const [joined, setJoined] = useState<string[]>(c.joined_officers.map((o) => o.id));
  const [assignNote, setAssignNote] = useState("");  // each form keeps its own text
  const [referReason, setReferReason] = useState("");
  const [mandateReason, setMandateReason] = useState("");
  const [refTo, setRefTo] = useState("");
  const [authority, setAuthority] = useState("");
  const officers = useList<{ id: string; name: string; role: string }[]>(`/complaints/${c.id}/officers/`);
  const team = useList<{ heads: { id: string; name: string; role: string }[]; assigned: { id: string; name: string; role: string } | null; officers: { id: string; name: string; role: string }[] }>(`/complaints/${c.id}/team/`);
  // Only the categories that belong to the division this complaint is in (plus its current category, so it is never lost).
  const inDivision = (x: Meta["categories"][number]) => !!c.division && [x.default_division, x.urban_division, x.rural_division].includes(c.division);
  const divCats = meta.categories.some(inDivision) ? meta.categories.filter((x) => inDivision(x) || x.id === c.category) : meta.categories;
  async function saveReview(changes: { category?: string; subcategory?: string; priority?: string; confidential_case?: boolean }) {
    const next = { category, subcategory, division, priority, confidential_case: confCase, ...changes };
    if (changes.category !== undefined) { setCategory(changes.category); setSubcategory(""); }
    if (changes.priority !== undefined) setPriority(changes.priority);
    if (changes.confidential_case !== undefined) setConfCase(changes.confidential_case);
    const ok = await run("triage", next);
    if (!ok) { setCategory(category); setSubcategory(subcategory); setPriority(priority); setConfCase(confCase); }
  }
  const act = (name: string, body: Record<string, unknown>) => (e: FormEvent) => { e.preventDefault(); run(name, body); };
  return (
    <Block icon="division" title="Triage and assignment">
      <div className="case-triage-context"><div><span>Suggested division</span><strong>{c.suggested_division_name ?? "Not suggested"}</strong></div><div><span>Response due</span><strong>{c.response_due_at ? new Date(c.response_due_at).toLocaleDateString() : "Set a priority"}</strong></div></div>
      <Err e={err} />
      {p.triage && (
        <div className="case-triage-form" aria-busy={busy}>
          <div className="case-step-title"><span>1</span><div><h3>Review complaint</h3><p>Changes to category, priority and confidentiality save automatically.</p></div></div>
          <div className="row">
            <Field label="Category" required error={f("category")}><select required disabled={busy} value={category} onChange={(e) => void saveReview({ category: e.target.value, subcategory: "" })}>{divCats.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
            <Field label="Priority" required error={f("priority")}><select required disabled={busy} value={priority} onChange={(e) => void saveReview({ priority: e.target.value })}><option value="">Select</option>{meta.priorities.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
          </div>
          <label className="on-behalf"><input type="checkbox" disabled={busy} checked={confCase} onChange={(e) => void saveReview({ confidential_case: e.target.checked })} /><span><strong>Confidential case</strong><small>Restrict visibility to the named officer and Division Head.</small></span></label>
          {busy && <p className="muted" role="status">Saving changes…</p>}
        </div>
      )}
      {(p.assign || p.refer || p.join) && <div className="case-routing-choice">
        <div className="case-step-title"><span>{p.triage ? "2" : "1"}</span><div><h3>Choose how to proceed</h3><p>Assign an officer, refer to another division, or add officers to work together.</p></div></div>
        <div className="case-routing-options" aria-label="Handling action">
          {p.assign && <button type="button" aria-pressed={routing === "assign"} onClick={() => setRouting("assign")}><Icon name="users" size={20} /><span><strong>Assign officer</strong><small>Handle in this division</small></span><Icon name="check" size={18} /></button>}
          {p.refer && <button type="button" aria-pressed={routing === "refer"} onClick={() => setRouting("refer")}><Icon name="send" size={20} /><span><strong>Refer complaint</strong><small>Send to another division</small></span><Icon name="check" size={18} /></button>}
          {p.join && <button type="button" aria-pressed={routing === "join"} onClick={() => setRouting("join")}><Icon name="users" size={20} /><span><strong>Join officers</strong><small>Work together on this complaint</small></span><Icon name="check" size={18} /></button>}
        </div>
      </div>}
      {p.join && routing === "join" && <form className="case-routing-form" aria-label="Join officers" onSubmit={act("join", { officers: joined })}>
        <div className="case-routing-heading"><span className="icon-tile"><Icon name="users" size={20} /></span><div><h3>Join officers to this complaint</h3><p>Joined officers can view the case, add notes, message the complainant and work on findings. The main officer keeps responsibility for the case.</p></div></div>
        <fieldset className="case-join-fieldset"><legend>Officers</legend><p className="muted">The Division Head and the assigned officer already have access. Tick an Investigating Officer to give them access; untick to remove it.</p>{f("officers") && <p className="error" role="alert">{f("officers")}</p>}
          <span className="case-join-list" role="group" aria-label="Officers working together">
            {team.loading ? <span>Loading officers…</span> : team.err ? <span role="alert">{team.err}</span> : <>
              {team.data?.heads.map((h) => <span className="case-join-option case-join-fixed" key={h.id}><Icon name="check" size={18} /><span>{h.name}<small>{h.role} · full access to every case in this division</small></span></span>)}
              {team.data?.assigned && <span className="case-join-option case-join-fixed"><Icon name="check" size={18} /><span>{team.data.assigned.name}<small>{team.data.assigned.role} · assigned officer</small></span></span>}
              {team.data?.officers.length ? team.data.officers.map((o) => <label className="case-join-option" key={o.id}><input type="checkbox" aria-label={o.name} disabled={busy} checked={joined.includes(o.id)} onChange={(e) => setJoined((prev) => e.target.checked ? [...prev, o.id] : prev.filter((id) => id !== o.id))} /><span>{o.name}<small>{o.role} · tick to give access</small></span></label>) : <span className="muted">No other Investigating Officers are registered in this division.</span>}
            </>}
          </span>
        </fieldset>
        <button className="btn" disabled={busy || team.loading || !!team.err}><Icon name="users" />{busy ? "Saving…" : "Save joined officers"}</button>
      </form>}
      {p.assign && routing === "assign" && (
        <form className="case-routing-form" aria-label="Assign officer" onSubmit={act("assign", { assigned_to: officer, priority, reason: assignNote })}>
          <div className="case-routing-heading"><span className="icon-tile"><Icon name="users" size={20} /></span><div><h3>{c.assigned_to_name ? "Reassign officer" : "Assign an officer"}</h3><p>{c.assigned_to_name ? `Currently assigned to ${c.assigned_to_name}. Choose another officer in this division.` : "Keep the complaint in this division and choose an officer to handle it."}</p></div></div>
          <div className="case-routing-row">
            <Field label="Officer" required error={f("assigned_to")}><select required value={officer} onChange={(e) => setOfficer(e.target.value)}><option value="">Select officer</option>{officers.data?.map((o) => <option key={o.id} value={o.id}>{o.name} · {o.role}</option>)}</select></Field>
            <Field label={c.assigned_to ? "Reason for reassigning" : "Note"} required={!!c.assigned_to} error={f("reason")}><input required={!!c.assigned_to} placeholder={c.assigned_to ? "Why are you reassigning?" : "Optional instructions for the officer"} value={assignNote} onChange={(e) => setAssignNote(e.target.value)} /></Field>
          <button className="btn" disabled={busy}><Icon name="users" />{c.assigned_to ? "Reassign officer" : "Assign officer"}</button>
          </div>
        </form>
      )}
      {p.refer && routing === "refer" && (
        <form className="case-routing-form case-routing-referral" aria-label="Refer to another division" onSubmit={act("refer", { division: refTo, reason: referReason })}>
          <div className="case-routing-heading"><span className="icon-tile"><Icon name="send" size={20} /></span><div><h3>Refer to another division</h3><p>Transfer the complaint to a different division for handling.</p></div></div>
          <div className="case-routing-row">
            <Field label="Division" required error={f("division")}><select required value={refTo} onChange={(e) => setRefTo(e.target.value)}><option value="">Select division</option>{meta.divisions.filter((d) => d.id !== c.division).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
            <Field label="Reason" required error={f("reason")}><input required placeholder="Why should this division handle it?" value={referReason} onChange={(e) => setReferReason(e.target.value)} /></Field>
          <button className="btn secondary" disabled={busy}><Icon name="send" />Refer complaint</button>
          </div>
        </form>
      )}
      {(p.note || p.message) && <details className="case-action-disclosure"><summary><Icon name="plus" size={19} /><div><strong>Add supporting documents</strong><small>Upload files and choose who can view them</small></div><Icon name="chev" size={17} /></summary><div className="case-disclosure-content"><UploadDocuments c={c} onDone={onDone} /></div></details>}
      {p.not_in_mandate && (
        <details className="case-action-disclosure case-closure-disclosure"><summary><Icon name="close" size={19} /><div><strong>Outside BICMA jurisdiction</strong><small>Close this complaint and notify the complainant</small></div><Icon name="chev" size={17} /></summary>
        <form className="case-disclosure-content" onSubmit={act("not-in-mandate", { reason: mandateReason, authority_referred_to: authority })}>
          <Field label="Reason (the complainant is emailed)" required error={f("reason")}><textarea required rows={2} value={mandateReason} onChange={(e) => setMandateReason(e.target.value)} /></Field>
          <Field label="Authority referred to" hint="Optional: the agency the complainant is directed to." error={f("authority_referred_to")}><input value={authority} onChange={(e) => setAuthority(e.target.value)} /></Field>
          <button className="btn secondary" disabled={busy} onClick={(e) => { if (!confirm("Close this complaint as outside BICMA's jurisdiction?")) e.preventDefault(); }}><Icon name="close" />Close as not within mandate</button>
        </form>
        </details>
      )}
    </Block>
  );
}

function Investigation({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const p = c.permissions;
  const { busy, err, run, f } = useDo(c, onDone);
  const [v, setV] = useState({ investigation_findings: c.investigation_findings, action_taken: c.action_taken, recommendation: c.recommendation });
  const [ask, setAsk] = useState("");
  const [back, setBack] = useState("");
  const [showBack, setShowBack] = useState(false);
  const [confirmReturn, setConfirmReturn] = useState(false);
  const started = c.internal_status !== "assigned";  // before the investigation starts, only "Start investigation" is offered
  const set = (k: string) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });
  const editable = p.save_findings || p.resolve;
  return (
    <Block icon="search" title="Investigation">
      <Err e={err} />
      {p.start && <button className="btn" disabled={busy} onClick={() => run("start", {})}><Icon name="search" />Start investigation</button>}
      {p.resume && <button className="btn" disabled={busy} onClick={() => run("resume", {})}><Icon name="refresh" />Resume investigation</button>}
      {editable ? (
        <form onSubmit={(e) => { e.preventDefault(); run("save-findings", v); }} style={{ marginTop: 10 }}>
          <Field label="Investigation findings" required error={f("investigation_findings")}><textarea rows={4} value={v.investigation_findings} onChange={set("investigation_findings")} /></Field>
          <Field label="Action taken" required error={f("action_taken")}><textarea rows={3} value={v.action_taken} onChange={set("action_taken")} /></Field>
          <Field label="Recommendation"><textarea rows={2} value={v.recommendation} onChange={set("recommendation")} /></Field>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn secondary" disabled={busy}><Icon name="edit" />Save draft</button>
            {p.resolve && <button type="button" className="btn" disabled={busy} onClick={() => run("resolve", v)}><Icon name="check" />Submit for Division Head approval</button>}
          </div>
        </form>
      ) : (
        (c.investigation_findings || c.action_taken) && <dl className="kv" style={{ marginTop: 10 }}>
          <dt>Findings</dt><dd style={{ whiteSpace: "pre-wrap" }}>{c.investigation_findings}</dd>
          <dt>Action taken</dt><dd style={{ whiteSpace: "pre-wrap" }}>{c.action_taken}</dd>
          {c.recommendation && <><dt>Recommendation</dt><dd style={{ whiteSpace: "pre-wrap" }}>{c.recommendation}</dd></>}
          {c.outcome_name && <><dt>Outcome</dt><dd>{c.outcome_name}</dd></>}
          {c.closure_reason && <><dt>Closure reason</dt><dd>{c.closure_reason}</dd></>}
        </dl>
      )}
      {p.request_info && (
        <form onSubmit={(e) => { e.preventDefault(); run("request-info", { message: ask }).then((ok) => ok && setAsk("")); }} style={{ marginTop: 16 }}>
          <h3>Request information</h3>
          <p className="muted">Pauses the response clock until the complainant replies.</p>
          <Field label="What do you need?" required error={f("message")}><textarea required rows={2} value={ask} onChange={(e) => setAsk(e.target.value)} /></Field>
          <button className="btn secondary" disabled={busy}><Icon name="mail" />Request information</button>
        </form>
      )}
      {p.return && !started && !showBack && <button type="button" className="btn secondary" style={{ marginLeft: 8 }} onClick={() => setShowBack(true)}><Icon name="refresh" />Return to Division Head</button>}
      {p.return && (started || showBack) && (
        <form onSubmit={(e) => { e.preventDefault(); setConfirmReturn(true); }} style={{ marginTop: 16 }}>
          <h3>Return to Division Head</h3>
          <p className="muted">Use this if the complaint is outside your division or you cannot proceed. The Division Head is alerted and reassigns or redirects it.</p>
          <Field label="Reason for returning" required error={f("reason")}><textarea required rows={2} value={back} onChange={(e) => setBack(e.target.value)} /></Field>
          <button className="btn secondary" disabled={busy}><Icon name="refresh" />Return to Division Head</button>
        </form>
      )}
      <Modal open={confirmReturn} onClose={() => setConfirmReturn(false)} busy={busy} title="Return to Division Head?" icon="refresh">
        <p>Return this complaint to the Division Head?</p>
        <p className="muted">The Division Head will be alerted to reassign or redirect it. The complaint will leave your assigned list.</p>
        <p><strong>Reason for returning</strong></p>
        <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{back}</p>
        <Err e={err} />
        <div className="modal-actions">
          <button type="button" className="btn secondary" autoFocus disabled={busy} onClick={() => setConfirmReturn(false)}>Cancel</button>
          <button type="button" className="btn" disabled={busy} onClick={async () => { if (await run("return", { reason: back })) setConfirmReturn(false); }}><Icon name="refresh" />{busy ? "Returning…" : "Return to Division Head"}</button>
        </div>
      </Modal>
    </Block>
  );
}

function Approval({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const p = c.permissions;
  const { busy, err, run, f } = useDo(c, onDone);
  const [closure, setClosure] = useState("");
  const [pub, setPub] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [decision, setDecision] = useState<"approve" | "supervisor" | "return">("approve");
  return (
    <Block icon="check" title={p.reopen ? "Closed case" : "Division Head decision"}>
      <Err e={err} />
      {p.approve && (
        <>
          <div className="case-decision-intro"><Icon name="complaint" size={20} /><p>The officer’s findings are ready for review. Choose the next step for this complaint.</p></div>
          <div className="case-decision-options" aria-label="Decision on officer findings">
            <button type="button" className="case-decision-accept" aria-pressed={decision === "approve"} disabled={busy} onClick={() => setDecision("approve")}><Icon name="check" size={23} /><strong>Accept and close</strong><small>Approve the findings and close the case</small></button>
            {p.send_to_management && <button type="button" className="case-decision-supervisor" aria-pressed={decision === "supervisor"} disabled={busy} onClick={() => setDecision("supervisor")}><Icon name="send" size={23} /><strong>Send to Supervisor</strong><small>Request the Supervisor’s approval</small></button>}
            {p.reject && <button type="button" className="case-decision-return" aria-pressed={decision === "return"} disabled={busy} onClick={() => setDecision("return")}><Icon name="refresh" size={23} /><strong>Return to officer</strong><small>Ask the officer for further work</small></button>}
          </div>
          <div className="case-decision-form">
          {decision === "approve" && <form className="decision-card" onSubmit={(e) => { e.preventDefault(); run("approve", { closure_reason: closure, public_message: pub }); }}>
            <h4><Icon name="check" size={16} />Accept and close</h4>
            <Field label="Closure reason" required error={f("closure_reason")}><textarea required rows={3} placeholder="Summarize why this complaint is being closed" value={closure} onChange={(e) => setClosure(e.target.value)} /></Field>
            <Field label="Message to complainant (optional)"><textarea rows={3} placeholder="Add a message for the complainant, if needed" value={pub} onChange={(e) => setPub(e.target.value)} /></Field>
            <button className="btn" disabled={busy}><Icon name="check" />Accept and close</button>
          </form>}
          {p.send_to_management && decision === "supervisor" && (
            <form className="decision-card" onSubmit={(e) => { e.preventDefault(); run("send-to-management", { note }); }}>
              <h4><Icon name="send" size={16} />Send to Supervisor</h4>
              <Field label="Note (optional)"><input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Anything they should look at" /></Field>
              <button className="btn secondary" disabled={busy}><Icon name="send" />Send to Supervisor</button>
            </form>
          )}
          {p.reject && decision === "return" && <form className="decision-card" onSubmit={(e) => { e.preventDefault(); run("reject", { reason }); }}>
            <h4><Icon name="refresh" size={16} />Return to officer</h4>
            <Field label="What must be done?" required error={f("reason")}><textarea required rows={3} placeholder="Describe what needs to be checked or completed" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            <button className="btn secondary" disabled={busy}><Icon name="refresh" />Return to officer</button>
          </form>}
          </div>
        </>
      )}
      {p.reopen && (
        <form onSubmit={(e) => { e.preventDefault(); run("reopen", { reason }); }}>
          <Field label="Reason for reopening" required error={f("reason")}><textarea required rows={2} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          <button className="btn secondary" disabled={busy}><Icon name="refresh" />Reopen</button>
        </form>
      )}
    </Block>
  );
}

/** Where the officer's findings stand with the Supervisor: submitted, accepted or rejected, with who and when. Read-only. */
export function ManagementTrail({ c }: { c: ComplaintDetail }) {
  const h = c.status_history;
  let last = -1;
  h.forEach((x, i) => { if (x.new_status === "pending_approval") last = i; });
  if (last < 0) return null;
  const sent = h[last];
  const after = h.slice(last + 1).find((x) => x.new_status === "resolved" || x.new_status === "management_rejected");
  const waiting = !after && c.internal_status === "pending_approval";
  const clean = (r: string) => r.replace(/^(Accepted|Rejected) by (supervisor|management):?\s*/, "");
  return (
    <Block icon={waiting ? "clock" : after?.new_status === "resolved" ? "check" : "alert"} title="Supervisor approval">
      <ol className="timeline">
        <li><span className="dot" aria-hidden="true"><Icon name="send" size={14} /></span>
          <div className="what"><strong>Sent to the Supervisor for approval</strong></div>
          <div className="when">{new Date(sent.created_at).toLocaleString()} · sent by {sent.actor ?? "the Division Head"}</div></li>
        {waiting && <li><span className="dot" aria-hidden="true"><Icon name="clock" size={14} /></span>
          <div className="what"><strong>Waiting for the Supervisor</strong></div>
          <div className="when">You will be alerted as soon as they accept or reject the findings.</div></li>}
        {after?.new_status === "resolved" && <li><span className="dot" aria-hidden="true"><Icon name="check" size={14} /></span>
          <div className="what"><strong>Accepted by supervisor</strong></div>
          <div className="when">{new Date(after.created_at).toLocaleString()} · {after.actor ?? "Supervisor"}</div>
          {clean(after.reason) && <div>{clean(after.reason)}</div>}</li>}
        {after?.new_status === "management_rejected" && <li><span className="dot" aria-hidden="true"><Icon name="close" size={14} /></span>
          <div className="what"><strong>Rejected by supervisor</strong></div>
          <div className="when">{new Date(after.created_at).toLocaleString()} · {after.actor ?? "Supervisor"}</div>
          {clean(after.reason) && <div>{clean(after.reason)}</div>}</li>}
      </ol>
    </Block>
  );
}

/** Supervisor: accept the officer's findings (case becomes Resolved) or reject them (the Division Head decides next). */
function ManagementDecision({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const { busy, err, run, f } = useDo(c, onDone);
  const [remarks, setRemarks] = useState("");
  const [reason, setReason] = useState("");
  return (
    <Block icon="check" title="Supervisor approval">
      <Err e={err} />
      <p>The Investigating Officer has submitted the findings below. Accept them to mark the case <strong>Resolved</strong>, or reject them and the Division Head will decide what happens next.</p>
      {(c.investigation_findings || c.action_taken) && <dl className="kv">
        <dt>Findings</dt><dd style={{ whiteSpace: "pre-wrap" }}>{c.investigation_findings}</dd>
        <dt>Action taken</dt><dd style={{ whiteSpace: "pre-wrap" }}>{c.action_taken}</dd>
        {c.recommendation && <><dt>Recommendation</dt><dd style={{ whiteSpace: "pre-wrap" }}>{c.recommendation}</dd></>}
        {c.outcome_name && <><dt>Outcome</dt><dd>{c.outcome_name}</dd></>}
      </dl>}
      <form onSubmit={(e) => { e.preventDefault(); run("mgmt-approve", { remarks }); }} style={{ marginTop: 12 }}>
        <Field label="Remarks (optional)"><input value={remarks} onChange={(e) => setRemarks(e.target.value)} /></Field>
        <button className="btn" disabled={busy}><Icon name="check" />Accept</button>
      </form>
      <form onSubmit={(e) => { e.preventDefault(); run("mgmt-reject", { reason }); }} style={{ marginTop: 16 }}>
        <Field label="Reject: why are the findings not accepted?" required error={f("reason")}><textarea required rows={2} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <button className="btn secondary" disabled={busy}><Icon name="close" />Reject</button>
      </form>
    </Block>
  );
}

/** Division Head, after the Supervisor rejected the findings: send it back to the same officer (or use Assign above to change the officer). */
function ReturnedByManagement({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const { busy, err, run, f } = useDo(c, onDone);
  const [reason, setReason] = useState("");
  const why = [...c.messages].reverse().find((m) => /^Returned by (supervisor|management):/.test(m.body))?.body.replace(/^Returned by (supervisor|management): /, "");
  return (
    <Block icon="alert" title="Returned by supervisor">
      <Err e={err} />
      <p>The Supervisor did not accept the findings{why ? <>: <em>{why}</em></> : "."} Decide what happens next: send the case back to {c.assigned_to_name ?? "the officer"}, or choose a different Investigating Officer in <strong>Assign</strong>.</p>
      <form onSubmit={(e) => { e.preventDefault(); run("send-back", { reason }); }}>
        <Field label={`Instructions for ${c.assigned_to_name ?? "the officer"}`} required error={f("reason")}><textarea required rows={2} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <button className="btn" disabled={busy || !c.assigned_to}><Icon name="refresh" />Send back to the same officer</button>
      </form>
    </Block>
  );
}

function Messages({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const p = c.permissions;
  const { busy, err, run, f } = useDo(c, onDone);
  const [kind, setKind] = useState<"public-message" | "internal-note">("internal-note");
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const can = p.message || p.note;
  async function send(e: FormEvent) {
    e.preventDefault();
    const fd = new FormData();
    fd.append("body", body);
    files.forEach((x) => fd.append("files", x));
    if (await run(kind, fd)) { setBody(""); setFiles([]); }
  }
  return (
    <Block icon="mail" title="Messages and notes">
      <ol className="timeline">
        {c.messages.map((m) => (
          <li key={m.id}><span className="dot" aria-hidden="true"><Icon name={m.visibility === "public" ? "mail" : "lock"} size={14} /></span>
            <div className="what"><strong>{m.author_name}</strong> <span className={`badge ${m.visibility === "public" ? "" : "warn"}`}>{m.visibility === "public" ? "Shown to complainant" : "Internal only"}</span>{m.kind === "info_request" && <span className="badge warn" style={{ marginLeft: 6 }}>Information request</span>}</div>
            <div className="when">{new Date(m.created_at).toLocaleString()}</div>
            <div style={{ whiteSpace: "pre-wrap" }}>{m.body}</div>
            {m.attachments.map((a) => <div key={a.id}><FileLink href={`/api/complaints/${c.id}/attachments/${a.id}/`} name={a.original_name} icon /></div>)}
          </li>
        ))}
        {c.messages.length === 0 && <li className="muted">No messages yet.</li>}
      </ol>
      {can && (
        <form onSubmit={send}>
          <Err e={err} />
          <div className="row">
            <Field label="Type"><select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
              <option value="internal-note">Internal note (never shown to the public)</option>
              {p.message && <option value="public-message">Public message (shown to the complainant)</option>}
            </select></Field>
          </div>
          <Field label="Message" required error={f("body")}><textarea required rows={3} value={body} onChange={(e) => setBody(e.target.value)} /></Field>
          <Field label="Attachments"><input type="file" multiple onChange={(e) => setFiles(Array.from(e.target.files ?? []))} /></Field>
          <button className="btn" disabled={busy}><Icon name="send" />{kind === "public-message" ? "Send" : "Save note"}</button>
        </form>
      )}
    </Block>
  );
}

function Stakeholder({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const { busy, err, run, f } = useDo(c, onDone);
  const [msg, setMsg] = useState("");
  const [to, setTo] = useState<string[]>(c.provider_contact_email ? [c.provider_contact_email.toLowerCase()] : []);  // starts with the provider's contact email; change, remove or add more
  const [ok, setOk] = useState(false);
  return (
    <Block icon="send" title="Notify the provider">
      <p className="muted">Sends the approved stakeholder email to the address below ({c.platform || c.provider_name || "the provider"}) after initial review. The complainant's identity is never included.</p>
      <Err e={err} />
      <Field label="Send to (email addresses)" required error={f("recipients")} hint={`${c.provider_contact_email ? "Starts with the provider's contact email. " : ""}Type or paste an address and press Enter to add it. You can send to up to 5 addresses at once.`}>
        <EmailChips value={to} onChange={(list) => { setTo(list); setOk(false); }} />
      </Field>
      <Field label="Additional message" required><textarea required rows={2} value={msg} onChange={(e) => setMsg(e.target.value)} /></Field>
      <button className="btn secondary" disabled={busy || to.length === 0 || !msg.trim()} onClick={async () => setOk(await run("stakeholder-review", { message: msg, recipients: to }))}><Icon name="mail" />{to.length > 1 ? `Send notice to ${to.length} addresses` : "Send notice"}</button>
      {ok && <p className="notice" role="status">Notice sent.</p>}
    </Block>
  );
}

export function CaseActions({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const meta = useList<Meta>("/meta/").data;
  const p = c.permissions;
  const showTriage = p.triage || p.assign || p.refer || p.join || p.not_in_mandate;
  const showInv = p.start || p.return || p.resume || p.save_findings || p.request_info || p.resolve || !!c.investigation_findings;
  const hasDecision = p.mgmt_approve || p.send_back || p.approve || p.reopen;
  const tabs = [
    ...(hasDecision ? [{ key: "decision", label: "Next action" }] : []),
    ...(showInv ? [{ key: "investigation", label: "Investigation" }] : []),
    ...(showTriage ? [{ key: "assignment", label: "Assignment" }] : []),
    { key: "messages", label: `Messages${c.messages.length ? ` (${c.messages.length})` : ""}` },
    ...(p.stakeholder_review ? [{ key: "provider", label: "Provider notice" }] : []),
  ];
  const [selected, setSelected] = useState(tabs[0].key);
  const active = tabs.some((tab) => tab.key === selected) ? selected : tabs[0].key;
  if (!meta) return null;
  return (
    <div className="case-workspace">
      {(p.save_findings || p.assign) && <SimilarComplaints c={c} onDone={onDone} />}
      <nav className="case-workspace-tabs" aria-label="Case workspace">
        {tabs.map((tab) => <button type="button" key={tab.key} aria-pressed={active === tab.key} onClick={() => setSelected(tab.key)}>{tab.label}</button>)}
      </nav>
      {hasDecision && <div hidden={active !== "decision"} className="case-workspace-panel">
        {p.mgmt_approve && <ManagementDecision c={c} onDone={onDone} />}
        {p.send_back && <ReturnedByManagement c={c} onDone={onDone} />}
        {(p.approve || p.reopen) && <Approval c={c} onDone={onDone} />}
      </div>}
      {showInv && <div hidden={active !== "investigation"} className="case-workspace-panel">
        <Investigation key={`${c.investigation_findings}|${c.action_taken}`} c={c} onDone={onDone} />
        {!p.mgmt_approve && <ManagementTrail c={c} />}
      </div>}
      {showTriage && <div hidden={active !== "assignment"}><Triage c={c} meta={meta} onDone={onDone} /></div>}
      <div hidden={active !== "messages"}><Messages c={c} onDone={onDone} /></div>
      {p.stakeholder_review && <div hidden={active !== "provider"}><Stakeholder c={c} onDone={onDone} /></div>}
    </div>
  );
}
