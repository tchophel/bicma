import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError, ensureCsrf } from "../../api";
import { useAuth } from "../../auth";
import type { User } from "../../types";
import { Loader } from "../../components/Loader";
import "../../styles/Login.css";

/** Where Google sends the person back: swap the code for a session, then open the dashboard. */
export function GoogleCallback() {
  const [q] = useSearchParams();
  const { acceptUser } = useAuth();
  const nav = useNavigate();
  const [err, setErr] = useState("");
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const code = q.get("code"), state = q.get("state");
    if (!code || !state) { setErr(q.get("error") === "access_denied" ? "Google sign-in was cancelled." : "Google sign-in did not complete."); return; }
    api<User>("/auth/google/callback/", { json: { code, state } })
      .then(async (u) => { await acceptUser(u); await ensureCsrf(); nav("/staff/dashboard", { replace: true }); })
      .catch((x) => setErr((x as ApiError).message));
  }, [q, acceptUser, nav]);
  return (
    <div className="container staff-login">
      <div className="card staff-login-card" style={{ textAlign: "center" }}>
        {err ? <><p className="error" role="alert">{err}</p><Link className="btn" to="/staff">Back to sign in</Link></> : <Loader label="Signing you in with Google" />}
      </div>
    </div>
  );
}
