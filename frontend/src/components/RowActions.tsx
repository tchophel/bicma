import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { useList } from "../useList";
import type { ComplaintRow, Meta } from "../types";
import { Field } from "./ui";
import { Icon } from "./Icon";
import { IconBtn } from "./IconBtn";
import { Modal } from "./Modal";
import { useToast } from "./Toast";

type Kind = "assign" | "refer" | null;

/** Quick "Assign to an officer" and "Refer to another division" buttons for one row of the complaints list. */
export function RowActions({ c, onDone }: { c: ComplaintRow; onDone: () => void }) {
  const [kind, setKind] = useState<Kind>(null);
  if (!c.can_assign && !c.can_refer) return null;
  return (
    <>
      {c.can_assign && <IconBtn icon="users" label={`${c.assigned_to ? "Reassign" : "Assign"} ${c.reference} to an Investigating Officer`} onClick={() => setKind("assign")} />}
      {c.can_refer && <IconBtn icon="send" label={`Refer ${c.reference} to another division`} onClick={() => setKind("refer")} />}
      <Modal open={kind !== null} onClose={() => setKind(null)} title={kind === "refer" ? `Refer ${c.reference}` : `${c.assigned_to ? "Reassign" : "Assign"} ${c.reference}`} icon={kind === "refer" ? "send" : "users"}>
        {kind === "assign" && <AssignForm c={c} onClose={() => setKind(null)} onDone={onDone} />}
        {kind === "refer" && <ReferForm c={c} onClose={() => setKind(null)} onDone={onDone} />}
      </Modal>
    </>
  );
}

function useAct(c: ComplaintRow, name: string, onClose: () => void, onDone: () => void, success: string) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  async function run(body: Record<string, unknown>) {
    if (busy) return;
    setBusy(true); setErr(null);
    try { await api(`/complaints/${c.id}/${name}/`, { json: body }); toast.success(success); onClose(); onDone(); }
    catch (x) { setErr(x as ApiError); }
    finally { setBusy(false); }
  }
  return { busy, err, run, f: (k: string) => err?.fields[k] };
}

function AssignForm({ c, onClose, onDone }: { c: ComplaintRow; onClose: () => void; onDone: () => void }) {
  const meta = useList<Meta>("/meta/").data;
  const officers = useList<{ id: string; name: string; role: string }[]>(`/complaints/${c.id}/officers/`);
  const { busy, err, run, f } = useAct(c, "assign", onClose, onDone, "Officer assigned.");
  const [officer, setOfficer] = useState("");
  const [priority, setPriority] = useState(c.priority ?? "");
  const [reason, setReason] = useState("");
  const submit = (e: FormEvent) => { e.preventDefault(); run({ assigned_to: officer, priority, reason }); };
  return (
    <form onSubmit={submit}>
      <p className="muted">The officer is alerted and emailed, and the complaint moves to <strong>Assigned</strong>. Only officers of {c.division_name ?? "this division"} are listed.</p>
      {err && !f("assigned_to") && !f("priority") && !f("reason") && <p className="error" role="alert">{err.message}</p>}
      <Field label="Investigating Officer" required error={f("assigned_to")}>
        <select required autoFocus value={officer} onChange={(e) => setOfficer(e.target.value)}>
          <option value="">{officers.loading ? "Loading…" : officers.data?.length ? "Select officer" : "No officers in this division"}</option>
          {officers.data?.map((o) => <option key={o.id} value={o.id}>{o.name} · {o.role}</option>)}
        </select>
      </Field>
      {!c.priority && (
        <Field label="Priority" required error={f("priority")}>
          <select required value={priority} onChange={(e) => setPriority(e.target.value)}><option value="">Select</option>{meta?.priorities.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
        </Field>
      )}
      <Field label={c.assigned_to ? "Reason for reassigning" : "Note (optional)"} required={!!c.assigned_to} error={f("reason")}><input required={!!c.assigned_to} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      <div className="modal-actions">
        <button type="button" className="btn secondary" disabled={busy} onClick={onClose}>Cancel</button>
        <button className="btn" disabled={busy}><Icon name="users" />{c.assigned_to ? "Reassign" : "Assign"}</button>
      </div>
    </form>
  );
}

function ReferForm({ c, onClose, onDone }: { c: ComplaintRow; onClose: () => void; onDone: () => void }) {
  const meta = useList<Meta>("/meta/").data;
  const { busy, err, run, f } = useAct(c, "refer", onClose, onDone, "Complaint referred.");
  const [division, setDivision] = useState("");
  const [reason, setReason] = useState("");
  const submit = (e: FormEvent) => { e.preventDefault(); run({ division, reason }); };
  return (
    <form onSubmit={submit}>
      <p className="muted">The complaint keeps its reference number and goes to the other division&rsquo;s triage queue. Its Division Head is alerted and emailed.</p>
      {err && !f("division") && !f("reason") && <p className="error" role="alert">{err.message}</p>}
      <Field label="Refer to division" required error={f("division")}>
        <select required autoFocus value={division} onChange={(e) => setDivision(e.target.value)}>
          <option value="">Select division</option>
          {meta?.divisions.filter((d) => d.id !== c.division).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </Field>
      <Field label="Reason" required error={f("reason")}><textarea required rows={2} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      <div className="modal-actions">
        <button type="button" className="btn secondary" disabled={busy} onClick={onClose}>Cancel</button>
        <button className="btn" disabled={busy}><Icon name="send" />Refer</button>
      </div>
    </form>
  );
}
