import { Icon } from "../../components/Icon";
import { useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { Field, PageHeader, initials } from "../../components/ui";
import { type Division, type Page, type User } from "../../types";
import { useList } from "../../useList";
import "./Directory.css";
import "./Users.css";


export function Users() {
  const { data, err, loading, reload } = useList<Page<User>>("/admin/users/?page_size=100");
  const divs = useList<Page<Division>>("/admin/divisions/");
  const roles = useList<Page<{ id: string; code: string; name: string; base: string; is_active: boolean }>>("/admin/roles/?page_size=200");
  const blank = { employee_id: "", designation: "", first_name: "", last_name: "", email: "", phone: "", role: "investigator", division: "" };
  const [form, setForm] = useState(blank);
  const [msg, setMsg] = useState<ApiError | null>(null);
  const [success, setSuccess] = useState("");
  const dialogRef = useRef<HTMLDialogElement>(null);
  const openDialog = () => { setMsg(null); dialogRef.current?.showModal(); };
  const closeDialog = () => { dialogRef.current?.close(); };
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const set = (k: string) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  async function create(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setMsg(null); setSuccess(""); setBusy(true);
    try {
      await api("/admin/users/", { json: { ...form, division: form.division || null } });
      setSuccess(`Account created. An initial password has been emailed to ${form.email}.`);
      setForm(blank); reload(); closeDialog();
    } catch (x) { setMsg(x as ApiError); }
    finally { setBusy(false); }
  }
  async function toggle(u: User) {
    if (!confirm(`${u.is_active ? "Deactivate" : "Activate"} ${u.email}?`)) return;
    setMsg(null); setSuccess("");
    try { await api(`/admin/users/${u.id}/`, { method: "PATCH", json: { is_active: !u.is_active } }); reload(); }
    catch (x) { setMsg(x as ApiError); }
  }
  const chosen = roles.data?.results.find((r) => r.code === form.role);
  const needsDiv = ["focal", "investigator"].includes(chosen?.base ?? form.role);
  const users = data?.results ?? [];
  const visible = users.filter((u) => `${u.email} ${u.first_name} ${u.last_name} ${u.role_display} ${u.division_name ?? ""}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="users-page">
      <PageHeader icon="users" title="Users" subtitle="Create and manage officials who can sign in.">
        <button type="button" className="btn" onClick={openDialog}><Icon name="plus" />Create user</button>
      </PageHeader>
      {err && <p className="error" role="alert">{err}</p>}
      {msg && <p className="error" role="alert">{msg.message}</p>}
      {success && <p className="users-success" role="status"><Icon name="check" />{success}</p>}
      <section className="card users-directory" aria-labelledby="directory-title">
        <div className="users-toolbar">
          <div><h2 id="directory-title">Staff directory <span className="chip">{data?.count ?? "—"}</span></h2><p className="muted">Manage account access and responsibilities.</p></div>
          <label className="users-search"><span className="sr-only">Search loaded users</span><Icon name="search" /><input type="search" placeholder="Search name, email or role…" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
        </div>
        <div className="table-wrap"><table>
          <thead><tr><th>Official</th><th>Role</th><th>Division</th><th>Status</th><th className="users-actions-cell">Actions</th></tr></thead>
          <tbody>{visible.map((u) => (
            <tr key={u.id}>
              <td><div className="cell-user"><span className="avatar-sm" aria-hidden="true">{initials(u.first_name, u.last_name, u.email)}</span><div><strong>{[u.first_name, u.last_name].filter(Boolean).join(" ") || "Staff account"}</strong><span className="users-email">{u.employee_id ? `${u.employee_id} · ` : ""}{u.email}</span></div></div></td>
              <td><span className="chip">{u.role_display}</span></td>
              <td><span className={u.division_name ? "" : "muted"}>{u.division_name ?? "No division"}</span></td>
              <td><span className={`badge ${u.is_active ? "ok" : "bad"}`}><span className="status-dot" />{u.is_active ? "Active" : "Inactive"}</span></td>
              <td className="users-actions-cell"><button className="btn secondary" onClick={() => toggle(u)} aria-label={`${u.is_active ? "Deactivate" : "Activate"} ${u.email}`}><Icon name="power" />{u.is_active ? "Deactivate" : "Activate"}</button></td>
            </tr>))}
            {loading && <tr><td colSpan={5} className="users-empty">Loading staff accounts…</td></tr>}
            {!loading && visible.length === 0 && <tr><td colSpan={5} className="users-empty"><Icon name="users" size={28} /><p>{query ? "No users match your search." : "No staff accounts yet. Create your first user below."}</p></td></tr>}
          </tbody>
        </table></div>
        <div className="users-directory-footer">Showing {visible.length} of {data?.count ?? 0} accounts</div>
      </section>
      <dialog ref={dialogRef} className="users-dialog" aria-labelledby="create-user-title" onClick={(e) => { if (e.target === dialogRef.current && !busy) closeDialog(); }}>
      <section className="card users-create" id="create-user" aria-labelledby="create-user-title">
        <button type="button" className="users-dialog-close icon-btn" aria-label="Close" disabled={busy} onClick={closeDialog}><Icon name="close" size={18} /></button>
        <div className="users-create-intro"><span className="icon-tile"><Icon name="users" size={26} /></span><h2 id="create-user-title">Create user</h2><p>Give an official access to the complaint management system.</p><div className="users-create-note"><Icon name="lock" /><span>Choose their role and division to set the appropriate access.</span></div></div>
        <form onSubmit={create} className="users-create-form" aria-busy={busy}>
          {msg && <p className="error" role="alert">{msg.message}</p>}
          <p className="users-form-note"><span className="req">*</span> Required fields</p>
          <fieldset disabled={busy}>
            <legend><span className="users-section-number">01</span> Personal details</legend>
            <div className="row">
              <Field label="Employee ID" hint="Becomes the username. Staff can also sign in with their email."><input placeholder="e.g. EMP001" autoComplete="off" value={form.employee_id} onChange={set("employee_id")} /></Field>
              <Field label="Designation"><input placeholder="e.g. Senior Officer" value={form.designation} onChange={set("designation")} /></Field>
              <Field label="First name"><input placeholder="Enter first name" autoComplete="given-name" value={form.first_name} onChange={set("first_name")} /></Field>
              <Field label="Last name"><input placeholder="Enter last name" autoComplete="family-name" value={form.last_name} onChange={set("last_name")} /></Field>
              <Field label="Email address" required hint="Used to sign in."><input required type="email" placeholder="official@example.org" autoComplete="off" value={form.email} onChange={set("email")} /></Field>
              <Field label="Contact number" hint="8 digits"><input type="tel" placeholder="17123456" autoComplete="off" value={form.phone} onChange={set("phone")} /></Field>
            </div>
          </fieldset>
          <fieldset disabled={busy}>
            <legend><span className="users-section-number">02</span> Account access</legend>
            <div className="row">
              <Field label="Role" required><select required value={form.role} onChange={set("role")}>{roles.data?.results.filter((r) => r.is_active).map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}</select></Field>
              <Field label="Division" required={needsDiv} hint={needsDiv ? "Required for this role." : "Optional for this role."}><select required={needsDiv} value={form.division} onChange={set("division")}><option value="">{needsDiv ? "Select a division" : "No division"}</option>{divs.data?.results.filter((d) => d.is_active).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
            </div>
            {divs.err && <p className="error" role="alert">Could not load divisions. Refresh the page to try again.</p>}
            <div className="users-password-notice"><span className="users-password-icon"><Icon name="lock" size={20} /></span><div><strong>Password delivered by email</strong><p>A secure initial password will be generated automatically and sent to the user’s email address.</p></div></div>
          </fieldset>
          <div className="users-form-footer"><span className="muted">Review the details before creating the account.</span><div className="users-form-actions"><button type="button" className="btn secondary" disabled={busy} onClick={closeDialog}>Cancel</button><button className="btn" disabled={busy}><Icon name="plus" />{busy ? "Creating…" : "Create user"}</button></div></div>
        </form>
      </section>
      </dialog>
    </div>
  );
}
