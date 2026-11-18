import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { useAuth } from "../../auth";
import { Field, PageHeader, PanelTitle, fmt } from "../../components/ui";
import { type User } from "../../types";

export function Profile() {
  const { user, setUser } = useAuth();
  const [f, setF] = useState({ first_name: user?.first_name ?? "", last_name: user?.last_name ?? "", phone: user?.phone ?? "" });
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [pmsg, setPmsg] = useState<{ ok?: string; err?: string }>({});
  if (!user) return null;
  async function save(e: FormEvent) {
    e.preventDefault(); setMsg({});
    try { setUser(await api<User>("/auth/me/", { method: "PATCH", json: f })); setMsg({ ok: "Profile updated." }); }
    catch (x) { setMsg({ err: (x as ApiError).message }); }
  }
  async function change(e: FormEvent) {
    e.preventDefault(); setPmsg({});
    if (pw.new_password !== pw.confirm) return setPmsg({ err: "The new passwords do not match." });
    try {
      await api("/auth/change-password/", { json: { current_password: pw.current_password, new_password: pw.new_password } });
      setPw({ current_password: "", new_password: "", confirm: "" }); setPmsg({ ok: "Password changed. Your other sessions were signed out." });
    } catch (x) { setPmsg({ err: (x as ApiError).message }); }
  }
  return (<>
    <PageHeader icon="user" title="My profile" subtitle="Your account details and password." />
    <div style={{ maxWidth: 960 }}>
      <section className="card" style={{ display: "flex", flexWrap: "wrap", gap: 20, alignItems: "center", marginBottom: 16, borderTop: "4px solid var(--c-brand-orange, #f58220)" }} aria-label="Account summary">
        <div aria-hidden="true" style={{ width: 84, height: 84, borderRadius: "50%", background: "var(--c-primary)", color: "#fff", display: "grid", placeItems: "center", fontSize: "2rem", fontWeight: 700 }}>
          {((user.first_name?.[0] ?? user.email[0]) + (user.last_name?.[0] ?? "")).toUpperCase()}
        </div>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h2 style={{ margin: "0 0 4px", fontSize: "1.5rem" }}>{[user.first_name, user.last_name].filter(Boolean).join(" ") || "Add your name below"}</h2>
          <div><span className="badge">{user.role_display}</span> {user.is_active && <span className="badge ok">Active</span>}</div>
        </div>
        <dl className="kv" style={{ gridTemplateColumns: "120px 1fr", minWidth: 280 }}>
          <dt>Email</dt><dd>{user.email}</dd>
          <dt>Division</dt><dd>{user.division_name ?? "Not tied to a division"}</dd>
          <dt>Phone</dt><dd>{user.phone || "—"}</dd>
          <dt>Last sign-in</dt><dd>{user.last_login ? fmt(user.last_login) : "—"}</dd>
        </dl>
      </section>
    <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
      <form className="card" onSubmit={save}>
        <PanelTitle icon="edit">Edit details</PanelTitle>
        <Field label="First name"><input value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} /></Field>
        <Field label="Last name"><input value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} /></Field>
        <Field label="Phone"><input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
        {msg.err && <p className="error" role="alert">{msg.err}</p>}{msg.ok && <p className="notice" role="status">{msg.ok}</p>}
        <button className="btn">Save changes</button>
        <p className="muted" style={{ marginBottom: 0 }}>Role, division and email can only be changed by a Super Administrator.</p>
      </form>
      <form className="card" onSubmit={change}>
        <PanelTitle icon="lock">Change password</PanelTitle>
        <Field label="Current password" required><input required type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
        <Field label="New password" required hint="Minimum 10 characters; not common or numeric only."><input required type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
        <Field label="Confirm new password" required><input required type="password" autoComplete="new-password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /></Field>
        {pmsg.err && <p className="error" role="alert">{pmsg.err}</p>}{pmsg.ok && <p className="notice" role="status">{pmsg.ok}</p>}
        <button className="btn">Change password</button>
      </form>
    </div>
    </div></>);
}
