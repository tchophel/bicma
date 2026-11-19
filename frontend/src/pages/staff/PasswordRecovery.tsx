import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ensureCsrf, ApiError } from "../../api";
import { Icon } from "../../components/Icon";
import { Field } from "../../components/ui";
import "../../styles/Login.css";
import "../../styles/PasswordRecovery.css";

export function PasswordRecovery({ reset = false }: { reset?: boolean }) {
  const { uid, token } = useParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError("");
    if (reset && password !== confirm) { setError("The passwords do not match."); return; }
    setBusy(true);
    try {
      await ensureCsrf();
      const result = await api<{ detail: string }>(reset ? "/auth/password-reset/confirm/" : "/auth/password-reset/", {
        json: reset ? { uid, token, new_password: password } : { email },
      });
      setMessage(result.detail); setPassword(""); setConfirm("");
    } catch (x) { setError((x as ApiError).message); }
    finally { setBusy(false); }
  }
  return (
    <div className="container staff-login password-recovery">
      <header className="recovery-heading"><img src="/bicma-logo.png" alt="BICMA logo" className="staff-login-logo" /><h1>{reset ? "Choose a new password" : "Forgot password?"}</h1><p className="muted">{reset ? "Create a secure password for your staff account." : "Enter your staff email and we’ll send a reset link."}</p></header>
      <div className="card staff-login-card">
        {message ? <div role="status" className="recovery-success"><span className="icon-tile"><Icon name="check" /></span><p>{message}</p>{reset && <Link className="btn" to="/staff">Sign in</Link>}</div> : (
          <form onSubmit={submit}>
            {!reset ? <Field label="Email address" required><input required type="email" autoComplete="email" placeholder="Enter your staff email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field> : <>
              <Field label="New password" required hint="Use at least 10 characters. Avoid common passwords or numbers only."><input required minLength={10} maxLength={128} type={show ? "text" : "password"} autoComplete="new-password" placeholder="Enter a new password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
              <Field label="Confirm password" required><input required minLength={10} maxLength={128} type={show ? "text" : "password"} autoComplete="new-password" placeholder="Re-enter your new password" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>
              <label className="recovery-show"><input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />Show passwords</label>
            </>}
            {error && <p className="error" role="alert">{error}</p>}
            <button className="btn" disabled={busy}><Icon name={reset ? "lock" : "mail"} />{busy ? "Please wait…" : reset ? "Reset password" : "Send reset link"}</button>
          </form>
        )}
        {reset && !message && <Link className="recovery-back" to="/staff/forgot-password">Request a new reset link</Link>}
        <Link className="recovery-back" to="/staff"><Icon name="left" size={16} />Back to sign in</Link>
      </div>
    </div>
  );
}
