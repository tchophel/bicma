import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import "./styles/AuthFeedback.css";
import { api, ensureCsrf } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  setUser: (u: User | null) => void;
  loading: boolean;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
  logout: () => Promise<void>;
  /** Accept a user the server has already signed in (for example through Bhutan NDI). */
  acceptUser: (u: User) => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [feedback, setFeedback] = useState<{ kind: "login" | "logout"; id: number } | null>(null);
  useEffect(() => {
    if (!feedback) return;
    const timer = setTimeout(() => setFeedback(null), 2200);
    return () => clearTimeout(timer);
  }, [feedback]);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Never overwrite a user who signed in while this first check was still running.
    // The CSRF cookie and "who am I" do not depend on each other, so ask for both at once.
    Promise.all([ensureCsrf(), api<User>("/auth/me/")])
      .then(([, u]) => setUser((prev) => prev ?? u))
      .catch(() => { /* not signed in: user stays null */ })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string, rememberMe = false) => {
    await ensureCsrf();
    setUser(await api<User>("/auth/login/", { json: { email, password, remember_me: rememberMe } }));
    setFeedback({ kind: "login", id: Date.now() });
    await ensureCsrf(); // CSRF token rotates on login
  }, []);

  const acceptUser = useCallback(async (u: User) => {
    setUser(u);
    setFeedback({ kind: "login", id: Date.now() });
    await ensureCsrf();
  }, []);

  const logout = useCallback(async () => {
    await api("/auth/logout/", { method: "POST" });
    setUser(null);
    setFeedback({ kind: "logout", id: Date.now() });
    await ensureCsrf();
  }, []);

  return <Ctx.Provider value={{ user, setUser, loading, login, logout, acceptUser }}>{children}
    {feedback && createPortal(<div className="auth-feedback" key={feedback.id}>
      <div className="auth-feedback-card" role="status" aria-live="polite">
        <span className={`auth-feedback-animation ${feedback.kind}`} aria-hidden="true">
          <span className="auth-feedback-halo" />
          <svg viewBox="0 0 80 80" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
            <circle className="auth-feedback-ring" cx="40" cy="40" r="33" />
            {feedback.kind === "login" ? <path className="auth-feedback-check" d="m24 40 11 11 22-24" /> : <>
              <path className="auth-feedback-shackle" d="M29 35v-9a11 11 0 0 1 22 0v9" />
              <rect className="auth-feedback-lock" x="24" y="35" width="32" height="25" rx="6" />
              <path className="auth-feedback-key" d="M40 45v6" />
            </>}
          </svg>
        </span>
        <strong>{feedback.kind === "login" ? "Welcome back!" : "See you soon!"}</strong>
        <span>{feedback.kind === "login" ? "You’re signed in." : "You’re signed out."}</span>
        <button type="button" aria-label="Dismiss message" onClick={() => setFeedback(null)}>×</button>
      </div>
    </div>, document.body)}
  </Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}
