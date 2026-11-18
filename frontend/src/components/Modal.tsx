import { useEffect, useRef, type ReactNode } from "react";
import { Icon, type IconName } from "./Icon";
import "./Modal.css";

/** Popup dialog for create/edit forms. Closes on Esc, the close button or a click outside (unless `busy`). */
export function Modal({ open, onClose, title, icon = "plus", busy = false, wide = false, children }: {
  open: boolean; onClose: () => void; title: string; icon?: IconName; busy?: boolean; wide?: boolean; children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className={`modal ${wide ? "wide" : ""}`} aria-labelledby="modal-title"
      onCancel={(e) => { e.preventDefault(); if (!busy) onClose(); }}
      onClick={(e) => { if (e.target === ref.current && !busy) onClose(); }}>
      {open && (
        <div className="modal-card">
          <header className="modal-head">
            <span className="icon-tile" aria-hidden="true"><Icon name={icon} size={20} /></span>
            <h2 id="modal-title">{title}</h2>
            <button type="button" className="icon-btn" aria-label="Close" disabled={busy} onClick={onClose}><Icon name="close" size={18} /></button>
          </header>
          <div className="modal-body">{children}</div>
        </div>
      )}
    </dialog>
  );
}
