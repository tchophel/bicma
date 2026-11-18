import { Icon } from "../../components/Icon";
import "./Profile.css";
import { useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { useAuth } from "../../auth";
import { Field, PageHeader, PanelTitle, fmt } from "../../components/ui";
import { type Meta, type User } from "../../types";
import { useList } from "../../useList";

export function Profile() {
  const { user, setUser } = useAuth();
  const [f, setF] = useState({ first_name: user?.first_name ?? "", last_name: user?.last_name ?? "", phone: user?.phone ?? "" });
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [pmsg, setPmsg] = useState<{ ok?: string; err?: string }>({});
  const [saving, setSaving] = useState(false);
  const [changing, setChanging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [photoMsg, setPhotoMsg] = useState("");
  const photoInput = useRef<HTMLInputElement>(null);
  const photoKb = useList<Meta>("/meta/").data?.limits.photo_max_kb ?? 5120;
  async function updatePhoto(file?: File, remove = false) {
    if (uploading || (!file && !remove)) return;
    if (file && file.size > photoKb * 1024) { setPhotoMsg(`Choose a photo up to ${photoKb} KB.`); return; }
    setUploading(true); setPhotoMsg("");
    try {
      const form = new FormData();
      if (file) form.append("photo", file);
      setUser(await api<User>("/auth/me/photo/", remove ? { method: "DELETE" } : { form }));
    } catch (x) { setPhotoMsg((x as ApiError).message); }
    finally { setUploading(false); }
  }
  if (!user) return null;
  async function save(e: FormEvent) {
    e.preventDefault(); if (saving) return; setMsg({}); setSaving(true);
    try { setUser(await api<User>("/auth/me/", { method: "PATCH", json: f })); setMsg({ ok: "Profile updated." }); }
    catch (x) { setMsg({ err: (x as ApiError).message }); }
    finally { setSaving(false); }
  }
  async function change(e: FormEvent) {
    e.preventDefault(); setPmsg({});
    if (pw.new_password !== pw.confirm) return setPmsg({ err: "The new passwords do not match." });
    if (changing) return;
    setChanging(true);
    try {
      await api("/auth/change-password/", { json: { current_password: pw.current_password, new_password: pw.new_password } });
      setPw({ current_password: "", new_password: "", confirm: "" }); setPmsg({ ok: "Password changed. Your other sessions were signed out." });
    } catch (x) { setPmsg({ err: (x as ApiError).message }); }
    finally { setChanging(false); }
  }
  return (<>
    <PageHeader icon="user" title="My profile" subtitle="Your account details and password." />
    <div className="profile-page">
      <section className="card profile-summary" aria-label="Account summary">
        <div className="profile-identity">
          <div className="profile-avatar">{user.profile_photo ? <img src={user.profile_photo} alt="Your profile" /> : <span aria-hidden="true">{((user.first_name?.[0] ?? user.email[0]) + (user.last_name?.[0] ?? "")).toUpperCase()}</span>}</div>
          <div className="profile-name"><span className="profile-eyebrow">YOUR ACCOUNT</span><h2>{[user.first_name, user.last_name].filter(Boolean).join(" ") || "Add your name below"}</h2><div className="profile-badges"><span className="badge">{user.role_display}</span><span className={`badge ${user.is_active ? "ok" : "bad"}`}>{user.is_active ? "Active" : "Inactive"}</span></div></div>
        </div>
        <div className="profile-photo-controls"><button type="button" className="profile-photo-upload" disabled={uploading} onClick={() => photoInput.current?.click()}><Icon name="plus" />{uploading ? "Uploading…" : user.profile_photo ? "Change photo" : "Upload profile photo"}</button><input ref={photoInput} hidden style={{ display: "none" }} aria-label="Upload profile photo" type="file" accept="image/jpeg,image/png,image/webp" disabled={uploading} onChange={(e) => { void updatePhoto(e.target.files?.[0]); e.target.value = ""; }} />{user.profile_photo && <button type="button" className="profile-remove" disabled={uploading} onClick={() => updatePhoto(undefined, true)}>Remove</button>}<small>JPG, PNG or WebP · Up to {photoKb >= 1024 ? `${photoKb / 1024} MB` : `${photoKb} KB`}</small>{photoMsg && <p className="error" role="alert">{photoMsg}</p>}</div>
        <dl className="profile-account-details"><div><dt><Icon name="mail" size={15} />Email</dt><dd>{user.email}</dd></div><div><dt><Icon name="division" size={15} />Division</dt><dd>{user.division_name ?? "Not tied to a division"}</dd></div><div><dt>Phone</dt><dd>{user.phone || "—"}</dd></div><div><dt><Icon name="clock" size={15} />Last sign-in</dt><dd>{user.last_login ? fmt(user.last_login) : "—"}</dd></div></dl>
      </section>
    <div className="profile-forms">
      <form className="card profile-form" onSubmit={save} aria-busy={saving}>
        <PanelTitle icon="edit">Personal details</PanelTitle><p className="profile-description">Keep your name and contact information up to date.</p>
        <Field label="First name"><input autoComplete="given-name" placeholder="Enter first name" value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} /></Field>
        <Field label="Last name"><input autoComplete="family-name" placeholder="Enter last name" value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} /></Field>
        <Field label="Phone"><input type="tel" autoComplete="tel" placeholder="Enter phone number" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
        {msg.err && <p className="error" role="alert">{msg.err}</p>}{msg.ok && <p className="notice" role="status">{msg.ok}</p>}
        <button className="btn" disabled={saving}><Icon name="check" />{saving ? "Saving…" : "Save changes"}</button>
        <p className="profile-admin-note">Role, division and email can only be changed by a Super Administrator.</p>
      </form>
      <form className="card profile-form" onSubmit={change} aria-busy={changing}>
        <PanelTitle icon="lock">Change password</PanelTitle><p className="profile-description">Choose a strong password to protect your account.</p>
        <Field label="Current password" required><input required type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
        <Field label="New password" required hint="Minimum 10 characters; not common or numeric only."><input required minLength={10} maxLength={128} type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
        <Field label="Confirm new password" required><input required minLength={10} maxLength={128} type="password" autoComplete="new-password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /></Field>
        {pmsg.err && <p className="error" role="alert">{pmsg.err}</p>}{pmsg.ok && <p className="notice" role="status">{pmsg.ok}</p>}
        <button className="btn" disabled={changing}><Icon name="lock" />{changing ? "Updating…" : "Change password"}</button>
      </form>
    </div>
    </div></>);
}
