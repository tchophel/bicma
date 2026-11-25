import { Icon } from "../../components/Icon";
import { useToast } from "../../components/Toast";
import "../../styles/Profile.css";
import { useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { useAuth } from "../../auth";
import { Field, PageHeader, PanelTitle, fmt, humanKb } from "../../components/ui";
import { type Meta, type User } from "../../types";
import { useList } from "../../useList";
import { THEMES } from "../../theme";

export function Profile() {
  const toast = useToast();
  const { user, setUser } = useAuth();
  const [f, setF] = useState({ first_name: user?.first_name ?? "", last_name: user?.last_name ?? "", phone: user?.phone ?? "", designation: user?.designation ?? "" });
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [visiblePasswords, setVisiblePasswords] = useState({ current_password: false, new_password: false, confirm: false });
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
    if (file && file.size > photoKb * 1024) { setPhotoMsg(`Choose a photo up to ${humanKb(photoKb)}.`); return; }
    setUploading(true); setPhotoMsg("");
    try {
      const form = new FormData();
      if (file) form.append("photo", file);
      setUser(await api<User>("/auth/me/photo/", remove ? { method: "DELETE" } : { form }));
      toast.success(remove ? "Profile photo removed." : "Profile photo updated.");
    } catch (x) { setPhotoMsg((x as ApiError).message); toast.error((x as ApiError).message); }
    finally { setUploading(false); }
  }
  const [themeBusy, setThemeBusy] = useState(false);
  async function pickTheme(key: string) {
    if (themeBusy || !user || (user.theme ?? "orange") === key) return;
    const before = user;
    setUser({ ...user, theme: key });  // shows the colour straight away
    setThemeBusy(true);
    try { setUser(await api<User>("/auth/me/", { method: "PATCH", json: { theme: key } })); toast.success("Dashboard colour saved."); }
    catch (x) { setUser(before); toast.error((x as ApiError).message); }
    finally { setThemeBusy(false); }
  }
  if (!user) return null;
  async function save(e: FormEvent) {
    e.preventDefault(); if (saving) return; setMsg({}); setSaving(true);
    try { setUser(await api<User>("/auth/me/", { method: "PATCH", json: f })); toast.success("Profile updated."); }
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
      setPw({ current_password: "", new_password: "", confirm: "" }); setVisiblePasswords({ current_password: false, new_password: false, confirm: false }); toast.success("Password changed. Your other sessions were signed out.");
    } catch (x) { setPmsg({ err: (x as ApiError).message }); }
    finally { setChanging(false); }
  }
  return (<div className="profile-screen">
    <PageHeader icon="user" title="My profile" subtitle="Your account details and password." />
    <div className="profile-page">
      <section className="card profile-summary" aria-label="Account summary">
        <div className="profile-identity">
          <div className="profile-avatar">{user.profile_photo ? <img src={user.profile_photo} alt="Your profile" /> : <span aria-hidden="true">{((user.first_name?.[0] ?? user.email[0]) + (user.last_name?.[0] ?? "")).toUpperCase()}</span>}</div>
          <div className="profile-name"><span className="profile-eyebrow">YOUR ACCOUNT</span><h2>{[user.first_name, user.last_name].filter(Boolean).join(" ") || "Complete your profile"}</h2><div className="profile-badges"><span className="badge">{user.role_display}</span><span className={`badge ${user.is_active ? "ok" : "bad"}`}>{user.is_active ? "Active" : "Inactive"}</span></div></div>
        </div>
        <div className="profile-photo-controls"><button type="button" className="profile-photo-upload" disabled={uploading} onClick={() => photoInput.current?.click()}><Icon name="plus" />{uploading ? "Uploading…" : user.profile_photo ? "Change photo" : "Upload profile photo"}</button><input ref={photoInput} hidden style={{ display: "none" }} aria-label="Upload profile photo" type="file" accept="image/jpeg,image/png,image/webp" disabled={uploading} onChange={(e) => { void updatePhoto(e.target.files?.[0]); e.target.value = ""; }} />{user.profile_photo && <button type="button" className="profile-remove" disabled={uploading} onClick={() => updatePhoto(undefined, true)}>Remove</button>}<small>JPG, PNG or WebP · Up to {humanKb(photoKb)}</small>{photoMsg && <p className="error" role="alert">{photoMsg}</p>}</div>
        <dl className="profile-account-details"><div><dt><Icon name="phone" size={15} />Phone</dt><dd>{user.phone || "—"}</dd></div><div><dt><Icon name="clock" size={15} />Last sign-in</dt><dd>{user.last_login ? fmt(user.last_login) : "—"}</dd></div></dl>
      </section>
    <div className="profile-forms">
      <form className="card profile-form profile-personal-form" onSubmit={save} aria-busy={saving}>
        <PanelTitle icon="edit">Personal details</PanelTitle><p className="profile-description">Keep your name and contact information up to date.</p>
        <div className="profile-name-fields">
        <Field label="First name"><span className="profile-input-icon"><Icon name="user" size={17} /><input autoComplete="given-name" placeholder="Enter first name" value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} /></span></Field>
        <Field label="Last name"><span className="profile-input-icon"><Icon name="user" size={17} /><input autoComplete="family-name" placeholder="Enter last name" value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} /></span></Field>
        </div>
        <Field label="Designation" hint="Your job title, for example Senior Officer."><span className="profile-input-icon"><Icon name="division" size={17} /><input maxLength={120} placeholder="e.g. Senior Officer" value={f.designation} onChange={(e) => setF({ ...f, designation: e.target.value })} /></span></Field>
        <Field label="Phone"><span className="profile-input-icon"><Icon name="phone" size={17} /><input type="tel" autoComplete="tel" placeholder="Enter phone number" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></span></Field>
        <div className="profile-name-fields">
          {user.employee_id && <Field label="Employee ID"><input value={user.employee_id} readOnly disabled /></Field>}
          <Field label="Role"><input value={user.role_display} readOnly disabled /></Field>
        </div>
        <Field label="Email address"><input value={user.email} readOnly disabled /></Field>
        <Field label="Division"><input value={user.division_name ?? "Not tied to a division"} readOnly disabled /></Field>
        {msg.err && <p className="error" role="alert">{msg.err}</p>}{msg.ok && <p className="notice" role="status">{msg.ok}</p>}
        <button type="submit" className="btn" disabled={saving}><Icon name="check" />{saving ? "Saving…" : "Save changes"}</button>
        <p className="profile-admin-note"><Icon name="lock" size={16} /><span>Contact a Super Administrator to change your role, division or email.</span></p>
      </form>
      <div className="profile-side-col">
      <section className="card profile-theme" aria-label="Dashboard colour">
        <div className="profile-theme-heading"><PanelTitle icon="gear">Dashboard colour</PanelTitle><p className="profile-description">Choose your dashboard’s accent colour. This preference applies only to your account.</p></div>
        <div className="theme-swatches" role="group" aria-label="Dashboard colour">
          {THEMES.map((t) => (
            <button type="button" key={t.key} className="theme-swatch" aria-pressed={(user.theme ?? "orange") === t.key} disabled={themeBusy} onClick={() => pickTheme(t.key)} title={t.label}>
              <span className="theme-dot" style={{ background: `linear-gradient(135deg, ${t.primary} 50%, ${t.brand} 50%)` }}>{(user.theme ?? "orange") === t.key && <Icon name="check" size={16} />}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </div>
      </section>
      <form className="card profile-form profile-password-form" onSubmit={change} aria-busy={changing}>
        <PanelTitle icon="lock">Change password</PanelTitle><p className="profile-description">Choose a strong password to protect your account.</p>
        <Field label="Current password" required><span className="profile-input-icon profile-password-input"><Icon name="lock" size={17} /><input required id="profile-current_password" type={visiblePasswords.current_password ? "text" : "password"} disabled={changing} autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /><button type="button" className="profile-password-toggle" aria-label={(visiblePasswords.current_password ? "Hide" : "Show") + " current password"} aria-pressed={visiblePasswords.current_password} aria-controls="profile-current_password" disabled={changing} onClick={() => setVisiblePasswords((previous) => ({ ...previous, current_password: !previous.current_password }))}><Icon name={visiblePasswords.current_password ? "eyeOff" : "eye"} size={19} /></button></span></Field>
        <Field label="New password" required hint="Minimum 10 characters; not common or numeric only."><span className="profile-input-icon profile-password-input"><Icon name="lock" size={17} /><input required minLength={10} maxLength={128} id="profile-new_password" type={visiblePasswords.new_password ? "text" : "password"} disabled={changing} autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /><button type="button" className="profile-password-toggle" aria-label={(visiblePasswords.new_password ? "Hide" : "Show") + " new password"} aria-pressed={visiblePasswords.new_password} aria-controls="profile-new_password" disabled={changing} onClick={() => setVisiblePasswords((previous) => ({ ...previous, new_password: !previous.new_password }))}><Icon name={visiblePasswords.new_password ? "eyeOff" : "eye"} size={19} /></button></span></Field>
        <Field label="Confirm new password" required><span className="profile-input-icon profile-password-input"><Icon name="lock" size={17} /><input required minLength={10} maxLength={128} id="profile-confirm" type={visiblePasswords.confirm ? "text" : "password"} disabled={changing} autoComplete="new-password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /><button type="button" className="profile-password-toggle" aria-label={(visiblePasswords.confirm ? "Hide" : "Show") + " confirm new password"} aria-pressed={visiblePasswords.confirm} aria-controls="profile-confirm" disabled={changing} onClick={() => setVisiblePasswords((previous) => ({ ...previous, confirm: !previous.confirm }))}><Icon name={visiblePasswords.confirm ? "eyeOff" : "eye"} size={19} /></button></span></Field>
        {pmsg.err && <p className="error" role="alert">{pmsg.err}</p>}{pmsg.ok && <p className="notice" role="status">{pmsg.ok}</p>}
        <button type="submit" className="btn secondary" disabled={changing}><Icon name="lock" />{changing ? "Updating…" : "Change password"}</button>
        <p className="profile-security-note"><Icon name="help" size={16} /><span>Changing your password signs out your other sessions.</span></p>
      </form>
      </div>
    </div>
    </div></div>);
}
