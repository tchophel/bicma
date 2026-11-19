import { useToast } from "../../components/Toast";
import { Icon } from "../../components/Icon";
import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { api, ApiError } from "../../api";
import { useAuth } from "../../auth";
import "../../styles/Login.css";

export function Login() {
  const { user, login } = useAuth();
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [p, setP] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/staff/dashboard" replace />;
  async function go(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try { await login(email, p, rememberMe); } catch (x) { setErr((x as ApiError).message); toast.error((x as ApiError).message); } finally { setBusy(false); }
  }
  return (
    <div className="container staff-login">
      <div style={{ textAlign: "center", marginBottom: 20 }}>
        <img src="/bicma-logo.png" alt="Bhutan InfoComm and Media Authority logo" className="staff-login-logo" />
        <h1 style={{ margin: 0 }}>Staff sign in</h1>
        <p className="muted" style={{ margin: "4px 0 0" }}>Bhutan InfoComm and Media Authority</p>
      </div>
      <form className="card staff-login-card" onSubmit={go}>
        <div className="field">
          <label className="login-label" htmlFor="login-email">Employee ID or email <span className="req" aria-hidden="true">*</span></label>
          <div className="input-icon-wrap">
            <Icon name="mail" />
            <input id="login-email" placeholder="Employee ID or email address" required type="text" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
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
        <div className="login-options"><label><input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} />Remember me</label><Link to="/staff/forgot-password">Forgot password?</Link></div>
        {err && <p className="error" role="alert">{err}</p>}
        <button className="btn" disabled={busy} style={{ width: "100%" }}><Icon name="login" />{busy ? "Signing in…" : "Sign in"}</button>
        <div className="login-or" aria-hidden="true"><span>or</span></div>
        <button type="button" className="ndi-btn" onClick={async () => { setErr(""); try { const r = await api<{ url?: string }>("/auth/ndi/start/"); if (r.url) window.location.href = r.url; } catch (x) { setErr((x as ApiError).message); } }}>
          <img src="/ndi-logo.png" alt="" width={34} height={34} />
          <span>Login with Bhutan NDI</span>
        </button>
      </form>
    </div>
  );
}
