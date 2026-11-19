import { useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { useList } from "../useList";
import type { ComplaintDetail, Meta } from "../types";
import { Field, PanelTitle } from "./ui";
import { Icon } from "./Icon";
import { useToast } from "./Toast";
import { Modal } from "./Modal";

const DONE: Record<string, string> = {
  triage: "Triage confirmed.", assign: "Officer assigned.", refer: "Complaint referred.", "not-in-mandate": "Closed as not within BICMA jurisdiction.",
  start: "Investigation started.", "save-findings": "Findings saved.", "request-info": "Information requested from the complainant.", resume: "Investigation resumed.", return: "Returned to the Division Head. It is no longer in your list.",
  resolve: "Findings sent to the Division Head.", "send-to-management": "Sent to the Management Viewer for approval.", "mgmt-approve": "Accepted. The case is Resolved and goes to the Division Head to close.", "mgmt-reject": "Returned to the Division Head to decide the next step.", "send-back": "Sent back to the Investigating Officer.", approve: "Complaint approved and closed.", reject: "Returned to the officer.", reopen: "Complaint reopened.",
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
  const [division, setDivision] = useState(c.division ?? "");
  const [confCase, setConfCase] = useState(c.confidential_case);
  const [officer, setOfficer] = useState("");
  const [reason, setReason] = useState("");
  const [refTo, setRefTo] = useState("");
  const [authority, setAuthority] = useState("");
  const officers = useList<{ id: string; name: string; role: string }[]>(`/complaints/${c.id}/officers/`);
  const cat = meta.categories.find((x) => x.id === category);
  const act = (name: string, body: Record<string, unknown>) => (e: FormEvent) => { e.preventDefault(); run(name, body); };
  return (
    <Block icon="division" title="Triage and assignment">
      <p className="muted">Suggested division: {c.suggested_division_name ?? "none"}. Response due {c.response_due_at ? new Date(c.response_due_at).toLocaleDateString() : "once a priority is set"}.</p>
      <Err e={err} />
      {p.triage && (
        <form onSubmit={act("triage", { category, subcategory, division, priority, confidential_case: confCase })}>
          <div className="row">
            <Field label="Category" required error={f("category")}><select required value={category} onChange={(e) => { setCategory(e.target.value); setSubcategory(""); }}>{meta.categories.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
            <Field label="Sub-category" error={f("subcategory")}><select value={subcategory} onChange={(e) => setSubcategory(e.target.value)}><option value="">None</option>{cat?.subcategories.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
            {p.assign && <Field label="Division" error={f("division")}><select value={division} onChange={(e) => setDivision(e.target.value)}>{meta.divisions.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>}
            <Field label="Priority" required error={f("priority")}><select required value={priority} onChange={(e) => setPriority(e.target.value)}><option value="">Select</option>{meta.priorities.map((x) => <option key={x.id} value={x.id}>{x.name} ({x.resolution_days} working days)</option>)}</select></Field>
          </div>
          <label className="on-behalf"><input type="checkbox" checked={confCase} onChange={(e) => setConfCase(e.target.checked)} /><span><strong>Confidential case</strong><small>Restrict visibility to the named officer and Division Head.</small></span></label>
          <button className="btn secondary" disabled={busy}><Icon name="check" />Confirm triage</button>
        </form>
      )}
      {p.assign && (
        <form onSubmit={act("assign", { assigned_to: officer, priority, reason })} style={{ marginTop: 16 }}>
          <h3>{c.assigned_to_name ? `Reassign (now ${c.assigned_to_name})` : "Assign an officer"}</h3>
          <div className="row">
            <Field label="Officer" required error={f("assigned_to")}><select required value={officer} onChange={(e) => setOfficer(e.target.value)}><option value="">Select officer</option>{officers.data?.map((o) => <option key={o.id} value={o.id}>{o.name} · {o.role}</option>)}</select></Field>
            {!c.priority && <Field label="Priority" required error={f("priority")}><select required value={priority} onChange={(e) => setPriority(e.target.value)}><option value="">Select</option>{meta.priorities.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>}
            <Field label={c.assigned_to ? "Reason for reassigning" : "Note"} required={!!c.assigned_to} error={f("reason")}><input value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          </div>
          <button className="btn" disabled={busy}><Icon name="users" />{c.assigned_to ? "Reassign" : "Assign"}</button>
        </form>
      )}
      {p.refer && (
        <form onSubmit={act("refer", { division: refTo, reason })} style={{ marginTop: 16 }}>
          <h3>Refer to another division</h3>
          <div className="row">
            <Field label="Division" required error={f("division")}><select required value={refTo} onChange={(e) => setRefTo(e.target.value)}><option value="">Select</option>{meta.divisions.filter((d) => d.id !== c.division).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
            <Field label="Reason" required error={f("reason")}><input required value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          </div>
          <button className="btn secondary" disabled={busy}><Icon name="send" />Refer</button>
        </form>
      )}
      {p.not_in_mandate && (
        <form onSubmit={act("not-in-mandate", { reason, authority_referred_to: authority })} style={{ marginTop: 16 }}>
          <h3>Not within BICMA jurisdiction</h3>
          <Field label="Reason (the complainant is emailed)" required error={f("reason")}><textarea required rows={2} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          <Field label="Authority referred to" hint="Optional: the agency the complainant is directed to." error={f("authority_referred_to")}><input value={authority} onChange={(e) => setAuthority(e.target.value)} /></Field>
          <button className="btn secondary" disabled={busy} onClick={(e) => { if (!confirm("Close this complaint as outside BICMA's jurisdiction?")) e.preventDefault(); }}><Icon name="close" />Close as not within mandate</button>
        </form>
      )}
    </Block>
  );
}

function Investigation({ c, meta, onDone }: { c: ComplaintDetail; meta: Meta; onDone: () => void }) {
  const p = c.permissions;
  const { busy, err, run, f } = useDo(c, onDone);
  const [v, setV] = useState({ investigation_findings: c.investigation_findings, action_taken: c.action_taken, recommendation: c.recommendation, outcome: c.outcome ?? "", authority_referred_to: c.authority_referred_to ?? "", referral_date: c.referral_date ?? "" });
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
          <Field label="Outcome" required error={f("outcome")}><select value={v.outcome} onChange={set("outcome")}><option value="">Select outcome</option>{meta.outcomes.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></Field>
          {/referred/i.test(meta.outcomes.find((o) => o.id === v.outcome)?.name ?? "") && (
            <div className="row">
              <Field label="Authority referred to" required error={f("authority_referred_to")} hint="Content matters amounting to criminal offences are only recorded and referred."><input value={v.authority_referred_to} onChange={set("authority_referred_to")} /></Field>
              <Field label="Date of referral" error={f("referral_date")}><input type="date" max={new Date().toISOString().slice(0, 10)} value={v.referral_date} onChange={set("referral_date")} /></Field>
            </div>
          )}
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
  return (
    <Block icon="check" title={p.reopen ? "Closed case" : "Division Head decision"}>
      <Err e={err} />
      {p.approve && (
        <>
          <p>The officer has submitted the findings. Choose one: <strong>accept</strong> them (closes the case), <strong>send them to the Management Viewer</strong> for approval, or <strong>return</strong> them to the officer.</p>
          <form onSubmit={(e) => { e.preventDefault(); run("approve", { closure_reason: closure, public_message: pub }); }}>
            <Field label="Closure reason" required error={f("closure_reason")}><textarea required rows={2} value={closure} onChange={(e) => setClosure(e.target.value)} /></Field>
            <Field label="Message to complainant (optional)"><textarea rows={2} value={pub} onChange={(e) => setPub(e.target.value)} /></Field>
            <button className="btn" disabled={busy}><Icon name="check" />Accept and close</button>
          </form>
          {p.send_to_management && (
            <form onSubmit={(e) => { e.preventDefault(); run("send-to-management", { note }); }} style={{ marginTop: 16 }}>
              <Field label="Send to Management Viewer: note (optional)"><input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Anything they should look at" /></Field>
              <button className="btn secondary" disabled={busy}><Icon name="send" />Send to Management Viewer</button>
            </form>
          )}
          <form onSubmit={(e) => { e.preventDefault(); run("reject", { reason }); }} style={{ marginTop: 16 }}>
            <Field label="Reject: what must be done?" required error={f("reason")}><textarea required rows={2} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            <button className="btn secondary" disabled={busy}><Icon name="refresh" />Return to officer</button>
          </form>
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

/** Where the officer's findings stand with management: submitted, accepted or rejected, with who and when. Read-only. */
export function ManagementTrail({ c }: { c: ComplaintDetail }) {
  const h = c.status_history;
  let last = -1;
  h.forEach((x, i) => { if (x.new_status === "pending_approval") last = i; });
  if (last < 0) return null;
  const sent = h[last];
  const after = h.slice(last + 1).find((x) => x.new_status === "resolved" || x.new_status === "management_rejected");
  const waiting = !after && c.internal_status === "pending_approval";
  const clean = (r: string) => r.replace(/^(Accepted|Rejected) by management:?\s*/, "");
  return (
    <Block icon={waiting ? "clock" : after?.new_status === "resolved" ? "check" : "alert"} title="Management approval">
      <ol className="timeline">
        <li><span className="dot" aria-hidden="true"><Icon name="send" size={14} /></span>
          <div className="what"><strong>Sent to the Management Viewer for approval</strong></div>
          <div className="when">{new Date(sent.created_at).toLocaleString()} · sent by {sent.actor ?? "the Division Head"}</div></li>
        {waiting && <li><span className="dot" aria-hidden="true"><Icon name="clock" size={14} /></span>
          <div className="what"><strong>Waiting for the Management Viewer</strong></div>
          <div className="when">You will be alerted as soon as they accept or reject the findings.</div></li>}
        {after?.new_status === "resolved" && <li><span className="dot" aria-hidden="true"><Icon name="check" size={14} /></span>
          <div className="what"><strong>Accepted by management</strong></div>
          <div className="when">{new Date(after.created_at).toLocaleString()} · {after.actor ?? "Management Viewer"}</div>
          {clean(after.reason) && <div>{clean(after.reason)}</div>}</li>}
        {after?.new_status === "management_rejected" && <li><span className="dot" aria-hidden="true"><Icon name="close" size={14} /></span>
          <div className="what"><strong>Rejected by management</strong></div>
          <div className="when">{new Date(after.created_at).toLocaleString()} · {after.actor ?? "Management Viewer"}</div>
          {clean(after.reason) && <div>{clean(after.reason)}</div>}</li>}
      </ol>
    </Block>
  );
}

/** Management Viewer: accept the officer's findings (case becomes Resolved) or reject them (the Division Head decides next). */
function ManagementDecision({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const { busy, err, run, f } = useDo(c, onDone);
  const [remarks, setRemarks] = useState("");
  const [reason, setReason] = useState("");
  return (
    <Block icon="check" title="Management approval">
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

/** Division Head, after management rejected the findings: send it back to the same officer (or use Assign above to change the officer). */
function ReturnedByManagement({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const { busy, err, run, f } = useDo(c, onDone);
  const [reason, setReason] = useState("");
  const why = [...c.messages].reverse().find((m) => m.body.startsWith("Returned by management:"))?.body.replace("Returned by management: ", "");
  return (
    <Block icon="alert" title="Returned by management">
      <Err e={err} />
      <p>Management did not accept the findings{why ? <>: <em>{why}</em></> : "."} Decide what happens next: send the case back to {c.assigned_to_name ?? "the officer"}, or choose a different Investigating Officer in <strong>Assign</strong>.</p>
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
            {m.attachments.map((a) => <div key={a.id}><a href={`/api/complaints/${c.id}/attachments/${a.id}/`}><Icon name="complaint" size={14} /> {a.original_name}</a></div>)}
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
  const { busy, err, run } = useDo(c, onDone);
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState(false);
  return (
    <Block icon="send" title="Notify the provider">
      <p className="muted">Sends the approved stakeholder email to {c.platform || c.provider_name || "the provider"} after initial review. The complainant's identity is never included.</p>
      <Err e={err} />
      <Field label="Additional message"><textarea rows={2} value={msg} onChange={(e) => setMsg(e.target.value)} /></Field>
      <button className="btn secondary" disabled={busy} onClick={async () => setOk(await run("stakeholder-review", { message: msg }))}><Icon name="mail" />Send notice</button>
      {ok && <p className="notice" role="status">Notice sent.</p>}
    </Block>
  );
}

export function CaseActions({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const meta = useList<Meta>("/meta/").data;
  const p = c.permissions;
  if (!meta) return null;
  const showTriage = p.triage || p.assign || p.refer || p.not_in_mandate;
  const showInv = p.start || p.return || p.resume || p.save_findings || p.request_info || p.resolve || !!c.investigation_findings;
  return (
    <div style={{ display: "grid", gap: 16 }}>
      {showTriage && <Triage c={c} meta={meta} onDone={onDone} />}
      {showInv && <Investigation c={c} meta={meta} onDone={onDone} />}
      {!p.mgmt_approve && <ManagementTrail c={c} />}
      {p.mgmt_approve && <ManagementDecision c={c} onDone={onDone} />}
      {p.send_back && <ReturnedByManagement c={c} onDone={onDone} />}
      {(p.approve || p.reopen) && <Approval c={c} onDone={onDone} />}
      <Messages c={c} onDone={onDone} />
      {p.stakeholder_review && <Stakeholder c={c} onDone={onDone} />}
    </div>
  );
}
