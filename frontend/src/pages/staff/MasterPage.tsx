import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { Icon, type IconName } from "../../components/Icon";
import { EmptyState, Field, PageHeader, PanelTitle } from "../../components/ui";
import type { Page } from "../../types";
import { useList } from "../../useList";

export interface FieldDef {
  key: string; label: string; type?: "text" | "number" | "date" | "email" | "textarea" | "select";
  required?: boolean; options?: { value: string; label: string }[]; hint?: string; min?: number;
}
type Row = { id: string; is_active: boolean } & Record<string, unknown>;

/** One generic admin screen for the simple master lists (BRD 5.1): add, edit with a reason, activate/deactivate. */
export function MasterPage({ title, subtitle, icon, path, fields }: { title: string; subtitle: string; icon: IconName; path: string; fields: FieldDef[] }) {
  const [q, setQ] = useState("");
  const { data, err, loading, reload } = useList<Page<Row>>(`/admin/${path}/?page_size=200${q ? `&search=${encodeURIComponent(q)}` : ""}`);
  const [status, setStatus] = useState<"" | "active" | "inactive">("");
  const blank = Object.fromEntries(fields.map((f) => [f.key, ""]));
  const [form, setForm] = useState<Record<string, string>>(blank);
  const [editing, setEditing] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState<ApiError | null>(null);
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  const label = (f: FieldDef, v: unknown) => f.type === "select" ? f.options?.find((o) => o.value === String(v ?? ""))?.label ?? "—" : String(v ?? "") || "—";

  async function save(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true); setMsg(null); setOk("");
    const body: Record<string, unknown> = { reason };
    for (const f of fields) { const v = form[f.key]; body[f.key] = v === "" && f.type !== "text" && f.type !== "textarea" ? null : f.type === "number" ? Number(v) : v; }
    try {
      if (editing) await api(`/admin/${path}/${editing}/`, { method: "PATCH", json: body });
      else await api(`/admin/${path}/`, { json: body });
      setOk(editing ? "Changes saved." : "Added."); setForm(blank); setEditing(null); setReason(""); reload();
    } catch (x) { setMsg(x as ApiError); }
    finally { setBusy(false); }
  }
  async function toggle(r: Row) {
    const why = prompt(`${r.is_active ? "Deactivate" : "Activate"} this record. Reason for the change:`);
    if (why === null) return;
    setMsg(null); setOk("");
    try { await api(`/admin/${path}/${r.id}/`, { method: "PATCH", json: { is_active: !r.is_active, reason: why } }); reload(); }
    catch (x) { setMsg(x as ApiError); }
  }
  function edit(r: Row) {
    setEditing(r.id);
    setForm(Object.fromEntries(fields.map((f) => [f.key, String(r[f.key] ?? "")])));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  const rows = (data?.results ?? []).filter((r) => !status || (status === "active") === r.is_active);
  return (
    <div className="users-page">
      <PageHeader icon={icon} title={title} subtitle={subtitle} />
      {err && <p className="error" role="alert">{err}</p>}
      {msg && <p className="error" role="alert">{msg.message}</p>}
      {ok && <p className="notice" role="status">{ok}</p>}
      <form className="card" onSubmit={save} style={{ marginBottom: 16 }}>
        <PanelTitle icon={editing ? "edit" : "plus"}>{editing ? "Edit record" : "Add record"}</PanelTitle>
        <div className="row">
          {fields.map((f) => (
            <Field key={f.key} label={f.label} required={f.required} hint={f.hint} error={msg?.fields[f.key]}>
              {f.type === "textarea" ? <textarea rows={4} required={f.required} value={form[f.key]} onChange={set(f.key)} />
                : f.type === "select" ? <select required={f.required} value={form[f.key]} onChange={set(f.key)}><option value="">{f.required ? "Select" : "None"}</option>{f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
                : <input type={f.type ?? "text"} min={f.min} required={f.required} value={form[f.key]} onChange={set(f.key)} />}
            </Field>
          ))}
          {editing && <Field label="Reason for the change" hint="Kept in the audit trail with the before and after values."><input value={reason} onChange={(e) => setReason(e.target.value)} /></Field>}
        </div>
        <button className="btn" disabled={busy}><Icon name={editing ? "check" : "plus"} />{editing ? "Save changes" : "Add"}</button>
        {editing && <button type="button" className="btn secondary" style={{ marginLeft: 8 }} onClick={() => { setEditing(null); setForm(blank); }}>Cancel</button>}
      </form>
      <section className="card">
        <div className="filter-bar" style={{ gridTemplateColumns: "2fr 1fr", padding: 0, boxShadow: "none", border: 0 }}>
          <label><span>Search</span><div className="search-wrap"><Icon name="search" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name" /></div></label>
          <label><span>Status</span><select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}><option value="">All</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label>
        </div>
        <div className="table-wrap"><table>
          <thead><tr>{fields.filter((f) => f.type !== "textarea").map((f) => <th key={f.key}>{f.label}</th>)}<th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                {fields.filter((f) => f.type !== "textarea").map((f) => <td key={f.key}>{label(f, r[f.key])}</td>)}
                <td><span className={`badge ${r.is_active ? "ok" : "bad"}`}>{r.is_active ? "Active" : "Inactive"}</span></td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <button className="btn secondary" onClick={() => edit(r)}><Icon name="edit" />Edit</button>{" "}
                  <button className="btn secondary" onClick={() => toggle(r)}><Icon name="power" />{r.is_active ? "Deactivate" : "Activate"}</button>
                </td>
              </tr>
            ))}
            {loading && <tr><td colSpan={fields.length + 2} className="muted">Loading…</td></tr>}
          </tbody>
        </table>
        {!loading && rows.length === 0 && <EmptyState icon="search">No records.</EmptyState>}
        </div>
        <p className="muted">Records in use are deactivated, never deleted, so historical complaints stay intact.</p>
      </section>
    </div>
  );
}

const opts = (rows?: { id: string; name: string }[]) => rows?.map((r) => ({ value: r.id, label: r.name })) ?? [];

export function ProviderTypes() { return <MasterPage title="Provider / party types" subtitle="Types such as telecom operator, ISP or broadcaster." icon="category" path="provider-types" fields={[{ key: "name", label: "Name", required: true }]} />; }
export function Outcomes() { return <MasterPage title="Outcomes" subtitle="Outcomes an officer records when resolving a complaint." icon="check" path="outcomes" fields={[{ key: "name", label: "Name", required: true }]} />; }
export function ClosureReasons() { return <MasterPage title="Closure reasons" subtitle="Standard reasons for closing a complaint." icon="close" path="closure-reasons" fields={[{ key: "name", label: "Name", required: true }]} />; }
export function Holidays() { return <MasterPage title="Public holiday calendar" subtitle="Working days exclude weekends and these dates when response timelines are calculated." icon="clock" path="holidays" fields={[{ key: "date", label: "Date", type: "date", required: true }, { key: "name", label: "Holiday", required: true }]} />; }
export function Priorities() {
  return <MasterPage title="Priorities and timelines" subtitle="Response and resolution timelines, in working days, applied to each priority." icon="alert" path="priorities"
    fields={[{ key: "name", label: "Priority", required: true }, { key: "rank", label: "Rank", type: "number", required: true, hint: "Higher is more urgent.", min: 1 }, { key: "response_days", label: "Response (working days)", type: "number", required: true, min: 0 }, { key: "resolution_days", label: "Resolution (working days)", type: "number", required: true, min: 1 }]} />;
}
export function EmailTemplates() {
  return <MasterPage title="Email templates" subtitle="Wording for each notification event. Placeholders: {reference} {subject} {status} {category} {provider} {message} {division} {officer} {tracking_url}." icon="mail" path="email-templates"
    fields={[{ key: "event", label: "Event key", required: true, hint: "acknowledgement, status_change, info_request, closure, not_within_mandate, stakeholder_review" }, { key: "name", label: "Name", required: true }, { key: "recipient", label: "Recipient", hint: "complainant, provider, officer" }, { key: "subject", label: "Subject", required: true }, { key: "body", label: "Body", type: "textarea", required: true }]} />;
}
export function Providers() {
  const types = useList<Page<{ id: string; name: string }>>("/admin/provider-types/?page_size=200");
  return <MasterPage title="Service providers / licensees" subtitle="Providers a complaint can name. The contact email receives the stakeholder notice after initial review." icon="users" path="providers"
    fields={[{ key: "name", label: "Name", required: true }, { key: "provider_type", label: "Type", type: "select", options: opts(types.data?.results) }, { key: "licence_number", label: "Licence number" }, { key: "contact_email", label: "Contact email", type: "email" }]} />;
}
