import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Modal } from "./Modal";

type Ask = (action?: string) => Promise<boolean>;
const Context = createContext<Ask | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [action, setAction] = useState<string | null>(null);
  const pending = useRef<((answer: boolean) => void) | null>(null);
  useEffect(() => () => { pending.current?.(false); }, []);
  const answer = (value: boolean) => {
    pending.current?.(value);
    pending.current = null;
    setAction(null);
  };
  const ask: Ask = (label = "Confirm") => new Promise((resolve) => {
    pending.current?.(false);
    pending.current = resolve;
    setAction(label);
  });
  return <Context.Provider value={ask}>{children}
    <Modal open={action !== null} onClose={() => answer(false)} title="Are you sure?" icon="alert">
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button type="button" className="btn secondary" autoFocus onClick={() => answer(false)}>Cancel</button>
        <button type="button" className="btn" onClick={() => answer(true)}>{action}</button>
      </div>
    </Modal>
  </Context.Provider>;
}

export function useConfirm(): Ask {
  const ask = useContext(Context);
  if (!ask) throw new Error("useConfirm outside ConfirmProvider");
  return ask;
}
