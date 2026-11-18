import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { Icon } from "./Icon";
import "../styles/Toast.css";

type Kind = "success" | "error" | "info";
interface Item { id: number; kind: Kind; message: string }
interface Api { success: (m: string) => void; error: (m: string) => void; info: (m: string) => void }

const Ctx = createContext<Api | null>(null);

/** Corner pop-ups that confirm an action or report a problem, then fade away on their own. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const next = useRef(1);
  const dismiss = useCallback((id: number) => setItems((l) => l.filter((t) => t.id !== id)), []);
  const push = useCallback((kind: Kind, message: string) => {
    if (!message) return;
    const id = next.current++;
    setItems((l) => [...l.filter((t) => t.message !== message).slice(-3), { id, kind, message }]);
    setTimeout(() => dismiss(id), kind === "error" ? 8000 : 5000);
  }, [dismiss]);
  const api = useMemo<Api>(() => ({ success: (m) => push("success", m), error: (m) => push("error", m), info: (m) => push("info", m) }), [push]);
  return (
    <Ctx.Provider value={api}>
      {children}
      <div className="toast-region" aria-label="Notifications">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`} role={t.kind === "error" ? "alert" : "status"}>
            <Icon name={t.kind === "success" ? "check" : t.kind === "error" ? "alert" : "help"} size={20} />
            <span className="toast-text">{t.message}</span>
            <button type="button" className="toast-close" aria-label="Dismiss" onClick={() => dismiss(t.id)}><Icon name="close" size={16} /></button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): Api {
  const v = useContext(Ctx);
  if (!v) throw new Error("useToast outside ToastProvider");
  return v;
}
