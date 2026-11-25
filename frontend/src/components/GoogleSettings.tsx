import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { Icon } from "./Icon";
import { useToast } from "./Toast";

type Cfg = { client_id: string; secret_set: boolean; enabled: boolean };

/** Settings > Sign in with Google: type the Client ID and secret from Google Cloud Console. */
export function GoogleSettings() {
  const toast = useToast();
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [id, setId] = useState("");
  const [secret, setSecret] = useState("");
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api<Cfg>("/admin/google-login/").then((c) => { setCfg(c); setId(c.client_id); }).catch(() => undefined);
  useEffect(() => { load(); }, []);
  async function save() {
    setBusy(true); setErr("");
    try { setCfg(await api<Cfg>("/admin/google-login/", { json: { client_id: id, client_secret: secret } })); setSecret(""); setOpen(false); toast.success("Saved."); }
    catch (e) { setErr((e as ApiError).message); }
    finally { setBusy(false); }
  }
  const redirect = `${window.location.origin}/staff/login/google`;
  return (
    <section className="card settings-section" aria-labelledby="settings-google">
      <header className="settings-section-header"><span className="icon-tile"><Icon name="login" size={22} /></span><div><span className="settings-eyebrow">STAFF SIGN IN</span><h2 id="settings-google">Sign in with Google</h2><p>Staff can sign in with the Google account that has the same email as their BICMA account.</p></div></header>
      <p><span className={`badge ${cfg?.enabled ? "ok" : "plain"}`}>{cfg?.enabled ? "On" : "Off"}</span>{" "}
        <button type="button" className="btn secondary" onClick={() => setOpen(!open)}>{open ? "Cancel" : cfg?.enabled ? "Edit settings" : "Set up"}</button></p>
      {open && (
        <div className="field-stack">
          <p className="muted">In Google Cloud Console (APIs &amp; Services, Credentials) create an <strong>OAuth client ID</strong> of type <em>Web application</em> and add this as an <strong>Authorized redirect URI</strong>: <code>{redirect}</code></p>
          <label className="login-label">Client ID<input value={id} onChange={(e) => setId(e.target.value)} placeholder="1234-abc.apps.googleusercontent.com" /></label>
          <label className="login-label">Client secret<input type="password" autoComplete="off" value={secret} onChange={(e) => setSecret(e.target.value)} placeholder={cfg?.secret_set ? "Saved. Leave blank to keep it." : ""} /></label>
          {err && <p className="error" role="alert">{err}</p>}
          <button type="button" className="btn" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save"}</button>
        </div>
      )}
    </section>
  );
}
