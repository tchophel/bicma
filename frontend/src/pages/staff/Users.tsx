import { useConfirm } from "../../components/Confirm";
import { Icon } from "../../components/Icon";
import { IconBtn } from "../../components/IconBtn";
import { Loader } from "../../components/Loader";
import { Modal } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { Field, PageHeader, initials } from "../../components/ui";
import { type Division, type Page, type User } from "../../types";
import { useList } from "../../useList";
import "../../styles/Directory.css";
import "../../styles/Users.css";
import "../../styles/MasterTheme.css";


export function Users() {
  const toast = useToast();
  const ask = useConfirm();
  const { data, err, loading, reload } = useList<Page<User>>("/admin/users/?page_size=100");
  const divs = useList<Page<Division>>("/admin/divisions/");
  const roles = useList<Page<{ id: string; code: string; name: string; base: string; is_active: boolean }>>("/admin/roles/?page_size=200");
  const blank = { cid: "", employee_id: "", designation: "", first_name: "", last_name: "", email: "", phone: "", role: "investigator", division: "" };
  const [form, setForm] = useState(blank);
  const [msg, setMsg] = useState<ApiError | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [editing, setEditing] = useState<User | null>(null);
  const openDialog = () => { setMsg(null); setEditing(null); setForm(blank); dialogRef.current?.showModal(); };
  const openEdit = (u: User) => {
    setMsg(null); setEditing(u);
    setForm({ cid: u.cid ?? "", employee_id: u.employee_id ?? "", designation: u.designation ?? "", first_name: u.first_name ?? "", last_name: u.last_name ?? "", email: u.email, phone: u.phone ?? "", role: u.role, division: u.division ?? "" });
    dialogRef.current?.showModal();
  };
  const closeDialog = () => { dialogRef.current?.close(); };
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const set = (k: string) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  const [looking, setLooking] = useState(false);
  async function lookup() {
    setLooking(true);
    try {
      const r = await api<{ first_name: string; middle_name: string; last_name: string; existing_user: string | null }>("/admin/users/cid-lookup/", { json: { cid: form.cid.trim() } });
      setForm((f) => ({ ...f, first_name: [r.first_name, r.middle_name].filter(Boolean).join(" "), last_name: r.last_name }));
      toast.success(r.existing_user && r.existing_user !== editing?.email ? `Name filled in. Note: ${r.existing_user} already uses this CID.` : "Name filled in from the citizen registry.");
    } catch (x) { toast.error((x as ApiError).message); }
    finally { setLooking(false); }
  }
  async function create(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setMsg(null); setBusy(true);
    try {
      if (editing) {
        await api(`/admin/users/${editing.id}/`, { method: "PATCH", json: { ...form, cid: form.cid.trim(), division: form.division || null } });
        toast.success(`${form.email} was updated.`);
      } else {
        await api("/admin/users/", { json: { ...form, cid: form.cid.trim(), division: form.division || null } });
        toast.success(`Account created. An initial password has been emailed to ${form.email}.`);
      }
      setForm(blank); setEditing(null); reload(); closeDialog();
    } catch (x) { setMsg(x as ApiError); toast.error((x as ApiError).message); }
    finally { setBusy(false); }
  }
  async function toggle(u: User) {
    if (!await ask(u.is_active ? "Deactivate" : "Activate")) return;
    setMsg(null);
    try { await api(`/admin/users/${u.id}/`, { method: "PATCH", json: { is_active: !u.is_active } }); reload(); toast.success(`${u.email} is now ${u.is_active ? "inactive" : "active"}.`); }
    catch (x) { toast.error((x as ApiError).message); }
  }
  const [pwUser, setPwUser] = useState<User | null>(null);
  const [pw, setPw] = useState({ new_password: "", confirm_password: "" });
  const [pwErr, setPwErr] = useState<ApiError | null>(null);
  const [pwBusy, setPwBusy] = useState(false);
  const [pwShow, setPwShow] = useState(false);
  function openPw(u: User) { setPwUser(u); setPw({ new_password: "", confirm_password: "" }); setPwErr(null); setPwShow(false); }
  async function savePw(e: FormEvent) {
    e.preventDefault();
    if (!pwUser || pwBusy) return;
    setPwBusy(true); setPwErr(null);
    try {
      const r = await api<{ detail: string }>(`/admin/users/${pwUser.id}/set-password/`, { json: pw });
      toast.success(r.detail); setPwUser(null);
    } catch (x) { setPwErr(x as ApiError); }
    finally { setPwBusy(false); }
  }
  const chosen = roles.data?.results.find((r) => r.code === form.role);
  const needsDiv = ["focal", "investigator"].includes(chosen?.base ?? form.role);
  const users = data?.results ?? [];
  const visible = users.filter((u) => `${u.email} ${u.first_name} ${u.last_name} ${u.role_display} ${u.division_name ?? ""}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="users-page master-page">
      <PageHeader icon="users" title="Users" subtitle="Create and manage officials who can sign in.">
        <button type="button" className="btn" onClick={openDialog}><Icon name="plus" />Create user</button>
      </PageHeader>
      {err && <p className="error" role="alert">{err}</p>}
      {msg && <p className="error" role="alert">{msg.message}</p>}
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
              <td className="users-actions-cell"><IconBtn icon="edit" onClick={() => openEdit(u)} label={`Edit ${u.email}`} /><IconBtn icon="lock" disabled={!u.is_active} onClick={() => openPw(u)} label={`Set a new password for ${u.email}`} /><IconBtn icon="power" tone={u.is_active ? "danger" : "ok"} onClick={() => toggle(u)} label={`${u.is_active ? "Deactivate" : "Activate"} ${u.email}`} /></td>
            </tr>))}
            {loading && <tr><td colSpan={5}><Loader size={40} label="Loading staff accounts" /></td></tr>}
            {!loading && visible.length === 0 && <tr><td colSpan={5} className="users-empty"><Icon name="users" size={28} /><p>{query ? "No users match your search." : "No staff accounts yet. Create your first user below."}</p></td></tr>}
          </tbody>
        </table></div>
        <div className="users-directory-footer">Showing {visible.length} of {data?.count ?? 0} accounts</div>
      </section>
      <dialog ref={dialogRef} className="users-dialog" aria-labelledby="create-user-title" onClick={(e) => { if (e.target === dialogRef.current && !busy) closeDialog(); }}>
      <section className="card users-create" id="create-user" aria-labelledby="create-user-title">
        <button type="button" className="users-dialog-close icon-btn" aria-label="Close" disabled={busy} onClick={closeDialog}><Icon name="close" size={18} /></button>
        <div className="users-create-intro"><span className="icon-tile"><Icon name="users" size={26} /></span><h2 id="create-user-title">{editing ? "Edit user" : "Create user"}</h2><p>{editing ? "Change this official’s details, role or division." : "Give an official access to the complaint management system."}</p><div className="users-create-note"><Icon name="lock" /><span>Choose their role and division to set the appropriate access.</span></div></div>
        <form onSubmit={create} className="users-create-form" aria-busy={busy}>
          {msg && <p className="error" role="alert">{msg.message}</p>}
          <p className="users-form-note"><span className="req">*</span> Required fields</p>
          <fieldset disabled={busy}>
            <legend><span className="users-section-number">01</span> Personal details</legend>
            <div className="row">
              <Field label="CID" hint="11 digits. Needed to sign in with Bhutan NDI; must match the CID in their NDI wallet.">
                <div style={{ display: "flex", gap: 8 }}><input inputMode="numeric" pattern="\d{11}" maxLength={11} placeholder="11-digit CID" autoComplete="off" value={form.cid} onChange={set("cid")} /><button type="button" className="btn secondary" disabled={looking || !/^\d{11}$/.test(form.cid.trim())} onClick={lookup}>{looking ? "Looking…" : "Look up"}</button></div>
              </Field>
              <Field label="Employee ID" hint="Not used to sign in. Staff sign in with their email and password, or Bhutan NDI."><input placeholder="e.g. EMP001" autoComplete="off" value={form.employee_id} onChange={set("employee_id")} /></Field>
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
              <Field label="Role" required><select required value={form.role} onChange={set("role")}>{roles.data?.results.filter((r) => r.is_active || r.code === editing?.role).map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}</select></Field>
              <Field label="Division" required={needsDiv} hint={needsDiv ? "Required for this role." : "Optional for this role."}><select required={needsDiv} value={form.division} onChange={set("division")}><option value="">{needsDiv ? "Select a division" : "No division"}</option>{divs.data?.results.filter((d) => d.is_active).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
            </div>
            {divs.err && <p className="error" role="alert">Could not load divisions. Refresh the page to try again.</p>}
            {!editing && <div className="users-password-notice"><span className="users-password-icon"><Icon name="lock" size={20} /></span><div><strong>Password delivered by email</strong><p>A secure initial password will be generated automatically and sent to the user’s email address.</p></div></div>}
          </fieldset>
          <div className="users-form-footer"><span className="muted">{editing ? "Review the changes before saving." : "Review the details before creating the account."}</span><div className="users-form-actions"><button type="button" className="btn secondary" disabled={busy} onClick={closeDialog}>Cancel</button><button type="submit" className="btn" disabled={busy}><Icon name={editing ? "check" : "plus"} />{busy ? (editing ? "Saving…" : "Creating…") : (editing ? "Save changes" : "Create user")}</button></div></div>
        </form>
      </section>
      </dialog>
      <Modal open={pwUser !== null} onClose={() => setPwUser(null)} busy={pwBusy} title="Set a new password" icon="lock">
        <form onSubmit={savePw}>
          <p className="muted">Choose a new password for <strong>{pwUser?.email}</strong>. Tell them the password in person; no email is sent. They are signed out of any open session.</p>
          {pwErr && !pwErr.fields.new_password && !pwErr.fields.confirm_password && <p className="error" role="alert">{pwErr.message}</p>}
          <Field label="New password" required error={pwErr?.fields.new_password} hint="At least 10 characters; not a common or all-numeric password.">
            <input required autoFocus type={pwShow ? "text" : "password"} autoComplete="new-password" minLength={10} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
          </Field>
          <Field label="Confirm new password" required error={pwErr?.fields.confirm_password}>
            <input required type={pwShow ? "text" : "password"} autoComplete="new-password" value={pw.confirm_password} onChange={(e) => setPw({ ...pw, confirm_password: e.target.value })} />
          </Field>
          <label style={{ display: "flex", gap: 8, alignItems: "center", margin: "4px 0 14px" }}><input type="checkbox" checked={pwShow} onChange={(e) => setPwShow(e.target.checked)} />Show password</label>
          <div className="modal-actions">
            <button type="button" className="btn secondary" disabled={pwBusy} onClick={() => setPwUser(null)}>Cancel</button>
            <button type="submit" className="btn" disabled={pwBusy}><Icon name="check" />{pwBusy ? "Saving…" : "Set password"}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
