import { useToast } from "../../components/Toast";
import { Icon } from "../../components/Icon";
import { NdiLogin } from "../../components/NdiLogin";
import { GoogleLogin } from "../../components/GoogleLogin";
import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { ApiError } from "../../api";
import { useAuth } from "../../auth";
import "../../styles/Login.css";

const REMEMBERED_EMAIL_KEY = "bicma-remembered-email";

function rememberedEmail() {
  try { return localStorage.getItem(REMEMBERED_EMAIL_KEY) ?? ""; }
  catch { return ""; }
}

export function Login() {
  const { user, login } = useAuth();
  const toast = useToast();
  const [email, setEmail] = useState(rememberedEmail);
  const [p, setP] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(() => !!rememberedEmail());
  function changeRememberMe(checked: boolean) {
    setRememberMe(checked);
    if (!checked) {
      try { localStorage.removeItem(REMEMBERED_EMAIL_KEY); } catch { /* storage unavailable */ }
    }
  }
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/staff/dashboard" replace />;
  async function go(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      await login(email, p, rememberMe);
      try {
        if (rememberMe) localStorage.setItem(REMEMBERED_EMAIL_KEY, email.trim().toLowerCase());
        else localStorage.removeItem(REMEMBERED_EMAIL_KEY);
      } catch { /* sign-in still works when browser storage is unavailable */ }
    } catch (x) { setErr((x as ApiError).message); toast.error((x as ApiError).message); } finally { setBusy(false); }
  }
  return (
    <div className="staff-login-stage">
    <div className="container staff-login">
      <div className="staff-login-heading">
        <img src="/bicma-logo.png" alt="Bhutan InfoComm and Media Authority logo" className="staff-login-logo" />
        <h1>Staff sign in</h1>
        <p className="muted">Bhutan InfoComm and Media Authority</p>
      </div>
      <form className="card staff-login-card" onSubmit={go}>
        <div className="field">
          <label className="login-label" htmlFor="login-email">Email <span className="req" aria-hidden="true">*</span></label>
          <div className="input-icon-wrap">
            <Icon name="mail" />
            <input id="login-email" placeholder="Email address" required type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label className="login-label" htmlFor="login-password">Password <span className="req" aria-hidden="true">*</span></label>
          <div className="input-icon-wrap password-input">
            <Icon name="lock" />
            <input id="login-password" placeholder="Enter your password" required type={showPassword ? "text" : "password"} autoComplete="current-password" value={p} onChange={(e) => setP(e.target.value)} />
            <button className="password-toggle" type="button" aria-label={showPassword ? "Hide password" : "Show password"} aria-controls="login-password" onClick={() => setShowPassword((shown) => !shown)}>
              <Icon name={showPassword ? "eyeOff" : "eye"} />
            </button>
          </div>
        </div>
        <div className="login-options"><label><input type="checkbox" checked={rememberMe} onChange={(e) => changeRememberMe(e.target.checked)} aria-describedby="remember-me-help" />Remember me</label><Link to="/staff/forgot-password">Forgot password?</Link></div>
        <p id="remember-me-help" className="muted" style={{ fontSize: ".75rem", marginTop: -6 }}>Remember your email and stay signed in for 30 days on this device.</p>
        {err && <p className="error" role="alert">{err}</p>}
        <button type="submit" className="btn" disabled={busy} style={{ width: "100%" }}><Icon name="login" />{busy ? "Signing in…" : "Sign in"}</button>
        <div className="login-or" aria-hidden="true"><span>or</span></div>
        <GoogleLogin rememberMe={rememberMe} onError={(m) => { setErr(m); toast.error(m); }} />
        <NdiLogin rememberMe={rememberMe} onError={(m) => { setErr(m); toast.error(m); }} />
      </form>
    </div>
    </div>
  );
}
