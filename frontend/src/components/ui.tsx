import { Icon, type IconName } from "./Icon";
import type { ReactNode } from "react";
import "./ui.css";

export function Field({ label, required, hint, error, children }: {
  label: string; required?: boolean; hint?: string; error?: string; children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}{required && <span className="req" aria-hidden="true"> *</span>}</span>
      {children}
      {hint && <small>{hint}</small>}
      {error && <small role="alert" style={{ color: "var(--c-accent)" }}>{error}</small>}
    </label>
  );
}

const TONE: Record<string, string> = {
  resolved: "ok", closed: "ok", rejected: "bad", on_hold: "warn", pending_response: "warn", pending_external_action: "warn",
};
export function StatusBadge({ value, label }: { value: string; label: string }) {
  return <span className={`badge ${TONE[value] ?? ""}`}><Icon name={TONE[value] === "ok" ? "check" : TONE[value] === "bad" ? "close" : TONE[value] === "warn" ? "clock" : "complaint"} size={14} />{label}</span>;
}

export const fmt = (iso: string) => new Date(iso).toLocaleString();
export const fmtDate = (iso: string) => new Date(iso).toLocaleDateString();

export function PageHeader({ icon, title, subtitle, children }: { icon: IconName; title: ReactNode; subtitle?: ReactNode; children?: ReactNode }) {
  return (
    <header className="page-head">
      <span className="icon-tile" aria-hidden="true"><Icon name={icon} size={26} /></span>
      <div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>
      {children && <div className="page-head-actions">{children}</div>}
    </header>
  );
}

export function PanelTitle({ icon, children }: { icon: IconName; children: ReactNode }) {
  return <h2 className="panel-title"><span className="icon-tile" aria-hidden="true"><Icon name={icon} size={18} /></span>{children}</h2>;
}

export function EmptyState({ icon = "complaint", children }: { icon?: IconName; children: ReactNode }) {
  return <div className="empty-state"><span className="icon-tile lg" aria-hidden="true"><Icon name={icon} size={28} /></span><p>{children}</p></div>;
}

export const initials = (first: string, last: string, email: string) => ((first?.[0] ?? email[0]) + (last?.[0] ?? "")).toUpperCase();
