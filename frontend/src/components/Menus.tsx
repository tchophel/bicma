import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import type { AppNotification } from "../types";
import { Icon } from "./Icon";
import { Modal } from "./Modal";
import { useToast } from "./Toast";
import css from "../styles/Layout.module.css";

/** Closes on outside click and Escape. */
function usePopover() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const click = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", click);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("mousedown", click); document.removeEventListener("keydown", key); };
  }, [open]);
  return { open, setOpen, ref };
}

function ago(iso: string) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

export function NotificationBell() {
  const { open, setOpen, ref } = usePopover();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState("");
  const nav = useNavigate();
  const toast = useToast();
  const seen = useRef<Set<string> | null>(null);  // ids already shown; null until the first load, so old ones do not pop up
  const load = useCallback(() => {
    api<{ unread_count: number; results: AppNotification[] }>("/notifications/").then((d) => {
      setItems(d.results); setUnread(d.unread_count);
      const fresh = d.results.filter((n) => !n.read && !seen.current?.has(n.id));
      if (seen.current) {  // a new notification arrived while you were working: say so, no refresh needed
        if (fresh.length === 1) toast.info(fresh[0].message);
        else if (fresh.length > 1) toast.info(`${fresh.length} new notifications. The latest: ${fresh[0].message}`);
      }
      seen.current = new Set([...(seen.current ?? []), ...d.results.map((n) => n.id)]);
    }).catch(() => {});
  }, [toast]);
  // Live: check every few seconds while the page is visible, and straight away when you come back to it.
  useEffect(() => {
    load();
    const tick = () => { if (document.visibilityState === "visible") load(); };
    const t = setInterval(tick, 5000);
    document.addEventListener("visibilitychange", tick);
    window.addEventListener("focus", tick);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", tick); window.removeEventListener("focus", tick); };
  }, [load]);

  async function openItem(n: AppNotification) {
    setOpen(false);
    if (!n.read) { await api(`/notifications/${n.id}/read/`, { method: "POST" }).catch(() => {}); load(); }
    if (n.link) nav(n.link);
  }
  async function clearAll() {
    if (clearing) return;
    setClearing(true); setClearError("");
    try {
      await api("/notifications/", { method: "DELETE" });
      setItems([]); setUnread(0);
    } catch { setClearError("Could not clear notifications. Please try again."); }
    finally { setClearing(false); }
  }
  async function readAll() { await api("/notifications/read-all/", { method: "POST" }); load(); }

  return (
    <div className={css.pop} ref={ref}>
      <button type="submit" className={css.iconBtn} aria-label={`Notifications, ${unread} unread`} aria-expanded={open} aria-haspopup="true" onClick={() => { setOpen(!open); if (!open) load(); }}>
        <Icon name="bell" size={20} />
        {unread > 0 && <span className={css.count}>{unread > 99 ? "99+" : unread}</span>}
      </button>
      {open && (
        <div className={`${css.panel} ${css.notificationPanel}`} role="region" aria-label="Notifications">
          <div className={css.notificationHead}>
            <div className={css.notificationTitle}><span className={css.notificationHeadingIcon}><Icon name="bell" size={20} /></span><strong>Notifications</strong>{unread > 0 && <span className={css.unreadCount}>{unread} unread</span>}</div>
            {items.length > 0 && <div className={css.notificationActions}>{unread > 0 && <button type="submit" disabled={clearing} onClick={readAll}><Icon name="check" size={15} />Mark all as read</button>}<button type="submit" disabled={clearing} onClick={clearAll}><Icon name="trash" size={15} />{clearing ? "Clearing…" : "Clear all"}</button></div>}
          </div>
          {clearError && <p className="error" role="alert">{clearError}</p>}
          {items.length === 0 && <div className={css.notificationEmpty}><Icon name="inbox" size={30} /><strong>You're all caught up</strong><p>New complaint updates will appear here.</p></div>}
          <ul className={css.notes}>
            {items.map((n) => (
              <li key={n.id}>
                <button type="submit" className={`${css.note} ${n.read ? "" : css.unread}`} onClick={() => openItem(n)}>
                  <span className={css.noteIcon}><Icon name="complaint" size={19} /></span>
                  <span className={css.noteContent}><span className={css.noteMessage}>{n.message}</span><small><Icon name="clock" size={12} /><time dateTime={n.created_at} title={new Date(n.created_at).toLocaleString()}>{ago(n.created_at)}</time>{!n.read && <span className={css.noteNew}>Unread</span>}</small></span>
                  <Icon name="chev" size={15} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function UserMenu() {
  const { user, logout } = useAuth();
  const [failedPhoto, setFailedPhoto] = useState<string | null>(null);
  const { open, setOpen, ref } = usePopover();
  const nav = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [leaving, setLeaving] = useState(false);
  if (!user) return null;
  async function signOut() {
    setLeaving(true);
    try { await logout(); setConfirming(false); nav("/staff"); }
    finally { setLeaving(false); }
  }
  const name = [user.first_name, user.last_name].filter(Boolean).join(" ") || user.email;
  const initials = (user.first_name?.[0] ?? user.email[0]).toUpperCase() + (user.last_name?.[0] ?? "").toUpperCase();
  const item = (to: string, icon: "user" | "gear" | "refresh", label: ReactNode) => (
    <Link to={to} className={css.menuItem} role="menuitem" onClick={() => setOpen(false)}><Icon name={icon} />{label}</Link>
  );
  return (
    <div className={css.pop} ref={ref}>
      <button type="submit" className={css.userBtn} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className={css.avatar} aria-hidden="true">{user.profile_photo && failedPhoto !== user.profile_photo ? <img src={user.profile_photo} alt="" onError={() => setFailedPhoto(user.profile_photo)} /> : initials}</span>
        <span className={css.who}><strong>{name}</strong><small>{user.role_display}</small></span>
        <Icon name="chev" size={14} />
      </button>
      {open && (
        <div className={css.panel} role="menu" style={{ minWidth: 220 }}>
          <div className={css.panelHead} style={{ display: "block" }}><strong>{name}</strong><br /><small>{user.email}</small></div>
          {item("/staff/profile", "user", "My profile")}
          {user.base_role === "super_admin" && item("/staff/workflow", "refresh", "Workflow")}
          {user.base_role === "super_admin" && item("/staff/settings", "gear", "Settings")}
          <button type="submit" className={css.menuItem} role="menuitem" onClick={() => { setOpen(false); setConfirming(true); }}><Icon name="logout" />Sign out</button>
        </div>
      )}
      <Modal open={confirming} onClose={() => setConfirming(false)} title="Log out" icon="logout" busy={leaving}>
        <p style={{ marginTop: 0 }}>Are you sure you want to log out?</p>
        <div className="modal-actions">
          <button type="button" className="btn secondary" disabled={leaving} onClick={() => setConfirming(false)}>Cancel</button>
          <button type="button" className="btn" disabled={leaving} onClick={signOut} autoFocus><Icon name="logout" />{leaving ? "Logging out…" : "Yes, log out"}</button>
        </div>
      </Modal>
    </div>
  );
}
