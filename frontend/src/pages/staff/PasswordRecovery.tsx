import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ensureCsrf, ApiError } from "../../api";
import { Icon } from "../../components/Icon";
import { Field } from "../../components/ui";
import { OtpBoxes } from "../../components/OtpBoxes";
import "../../styles/Login.css";
import "../../styles/PasswordRecovery.css";

/** Two ways in: `reset` is the emailed link (used for new-account invitations); otherwise Forgot password sends a
 *  6-digit one-time code by email, then asks for the code and a new password. */
export function PasswordRecovery({ reset = false }: { reset?: boolean }) {
  const { uid, token } = useParams();
  const [stage, setStage] = useState<"email" | "code" | "done">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const isCode = !reset && stage === "code";

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError("");
    if ((reset || isCode) && password !== confirm) { setError("The passwords do not match."); return; }
    setBusy(true);
    try {
      await ensureCsrf();
      if (reset) {
        const r = await api<{ detail: string }>("/auth/password-reset/confirm/", { json: { uid, token, new_password: password } });
        setMessage(r.detail); setStage("done");
      } else if (isCode) {
        const r = await api<{ detail: string }>("/auth/password-reset/verify/", { json: { email, code, new_password: password } });
        setMessage(r.detail); setStage("done");
      } else {
        const r = await api<{ detail: string }>("/auth/password-reset/", { json: { email } });
        setMessage(r.detail); setStage("code");
      }
      setPassword(""); setConfirm("");
    } catch (x) { setError((x as ApiError).message); }
    finally { setBusy(false); }
  }
  const title = reset ? "Choose a new password" : stage === "code" ? "Enter your code" : "Forgot password?";
  const subtitle = reset ? "Use at least 10 characters." : stage === "code" ? "Enter the 6-digit code we emailed you and choose a new password." : "Enter your staff email and we’ll send a 6-digit code.";
  const passwordFields = (
    <>
      <Field label="New password" required hint="Use at least 10 characters. Avoid common passwords or numbers only."><input required minLength={10} maxLength={128} type={show ? "text" : "password"} autoComplete="new-password" placeholder="Enter a new password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
      <Field label="Confirm password" required><input required minLength={10} maxLength={128} type={show ? "text" : "password"} autoComplete="new-password" placeholder="Re-enter your new password" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>
      <label className="recovery-show"><input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />Show passwords</label>
    </>
  );
  return (
    <div className="container staff-login password-recovery">
      <header className="recovery-heading"><img src="/bicma-logo.png" alt="BICMA logo" className="staff-login-logo" /><h1>{title}</h1><p className="muted">{subtitle}</p></header>
      <div className="card staff-login-card">
        {stage === "done" ? (
          <div role="status" className="recovery-success"><span className="icon-tile"><Icon name="check" /></span><p>{message}</p><Link className="btn" to="/staff">Sign in</Link></div>
        ) : (
          <form onSubmit={submit}>
            {!reset && stage === "email" && <Field label="Email address" required><input required type="email" autoComplete="email" placeholder="Enter your staff email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>}
            {isCode && (
              <>
                <p className="muted" role="status">{message}</p>
                <label className="login-label" style={{ display: "block", textAlign: "center" }}>6-digit code <span className="req" aria-hidden="true">*</span></label>
                <OtpBoxes value={code} onChange={setCode} label="6-digit code" autoFocus invalid={!!error && code.length === 6} />
                {passwordFields}
              </>
            )}
            {reset && passwordFields}
            {error && <p className="error" role="alert">{error}</p>}
            <button type="submit" className="btn" disabled={busy || (isCode && code.length !== 6)}><Icon name={reset || isCode ? "lock" : "mail"} />{busy ? "Please wait…" : reset || isCode ? "Reset password" : "Send code"}</button>
          </form>
        )}
        {isCode && <button type="button" className="recovery-back linklike" onClick={() => { setStage("email"); setCode(""); setError(""); }}>Didn’t get it? Send a new code</button>}
        {reset && stage !== "done" && <Link className="recovery-back" to="/staff/forgot-password">Request a new code</Link>}
        <Link className="recovery-back" to="/staff"><Icon name="left" size={16} />Back to sign in</Link>
      </div>
    </div>
  );
}
