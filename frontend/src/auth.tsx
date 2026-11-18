import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useToast } from "./components/Toast";
import { api, ensureCsrf, withMinTime } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  setUser: (u: User | null) => void;
  loading: boolean;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // A quick sign-in can finish before this first check does, so never overwrite a user who is already signed in.
    withMinTime(ensureCsrf().then(() => api<User>("/auth/me/")))
      .then((u) => setUser((prev) => prev ?? u))
      .catch(() => { /* not signed in: user stays null */ })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string, rememberMe = false) => {
    await ensureCsrf();
    setUser(await api<User>("/auth/login/", { json: { email, password, remember_me: rememberMe } }));
    toast.success("Signed in successfully.");
    await ensureCsrf(); // CSRF token rotates on login
  }, [toast]);

  const logout = useCallback(async () => {
    await api("/auth/logout/", { method: "POST" });
    setUser(null);
    toast.success("Signed out successfully.");
    await ensureCsrf();
  }, [toast]);

  return <Ctx.Provider value={{ user, setUser, loading, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}
