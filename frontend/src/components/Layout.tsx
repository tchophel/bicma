import { useEffect, useState } from "react";
import { api } from "../api";
import { Loader } from "./Loader";
import { NavLink, Link, Outlet, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import type { Role } from "../types";
import { Icon, type IconName } from "./Icon";
import css from "../styles/Layout.module.css";
import pub from "../styles/Public.module.css";
import { NotificationBell, UserMenu } from "./Menus";

export function PublicLayout() {
  const [open, setOpen] = useState(false);
  return (
    <div className={`${pub.shell} ${open ? pub.open : ""}`}>
      <a className="skip" href="#main">Skip to content</a>
      <div className={pub.strip} />
      <header className={pub.header}>
        <div className={pub.bar}>
          <Link to="/" className={pub.brand}>
            <img src="/bicma-logo.png" alt="BICMA logo" />
            <span><strong>BICMA Complaint Portal</strong><small>Bhutan InfoComm and Media Authority</small></span>
          </Link>
          <button className={pub.menuBtn} aria-label="Toggle menu" aria-expanded={open} aria-controls="public-nav" onClick={() => setOpen(!open)}><Icon name={open ? "close" : "menu"} /></button>
          <nav id="public-nav" className={pub.nav} aria-label="Public" onClick={() => setOpen(false)}>
            <NavLink to="/" end><Icon name="home" />Home</NavLink>
            <NavLink to="/submit"><Icon name="plus" />Submit a Complaint</NavLink>
            <NavLink to="/track"><Icon name="search" />Track a Complaint</NavLink>
          </nav>
          <Link to="/staff" className={pub.staff}><Icon name="login" />Staff Sign In</Link>
        </div>
      </header>
      <main id="main" className={pub.main}><Outlet /></main>
      <footer className={pub.footer}>
        <div className={pub.footInner}>
          <div className={pub.footBrand}><img src="/bicma-logo.png" alt="BICMA logo" className={pub.footLogo} /><strong>BICMA</strong><span>Bhutan InfoComm and Media Authority</span></div>
          <span className={pub.footCopy}>&copy; {new Date().getFullYear()} BICMA. All rights reserved.</span>
          <span className={pub.footCredit}>Developed by <strong>GovTech Agency</strong></span>
        </div>
      </footer>
    </div>
  );
}

interface NavItem { to: string; label: string; icon: IconName; roles?: Role[]; perm?: string }
const NAV: { heading?: string; items: NavItem[] }[] = [
  { items: [{ to: "/staff/dashboard", label: "Dashboard", icon: "dashboard" }] },
  {
    heading: "Complaints",
    items: [
      { to: "/staff/complaints?scope=triage", label: "Triage queue", icon: "clock", roles: ["focal", "super_admin"] },
      { to: "/staff/complaints?status=pending_approval", label: "Awaiting my approval", icon: "check", roles: ["supervisor"] },
      { to: "/staff/complaints", label: "All complaints", icon: "complaint" },
      { to: "/staff/register", label: "Register complaint", icon: "plus", perm: "register_complaint" },
      { to: "/staff/reports", label: "Reports", icon: "chart", perm: "view_reports" },
    ],
  },
  {
    heading: "Master data",
    items: [
      { to: "/staff/categories", label: "Categories", icon: "category", roles: ["super_admin"] },
      { to: "/staff/roles", label: "Roles", icon: "lock", roles: ["super_admin"] },
      { to: "/staff/divisions", label: "Divisions", icon: "division", roles: ["super_admin"] },
      { to: "/staff/providers", label: "Service providers", icon: "users", roles: ["super_admin"] },
      { to: "/staff/provider-types", label: "Provider types", icon: "category", roles: ["super_admin"] },
      { to: "/staff/priorities", label: "Priorities & timelines", icon: "alert", roles: ["super_admin"] },
      { to: "/staff/outcomes", label: "Outcomes", icon: "check", roles: ["super_admin"] },
      { to: "/staff/closure-reasons", label: "Closure reasons", icon: "close", roles: ["super_admin"] },
      { to: "/staff/dzongkhags", label: "Dzongkhags", icon: "map", roles: ["super_admin"] },
    ],
  },
  {
    heading: "Administration",
    items: [
      { to: "/staff/users", label: "Users", icon: "users", roles: ["super_admin"] },
      { to: "/staff/permissions", label: "Roles & permissions", icon: "lock", roles: ["super_admin"] },
      { to: "/staff/uploads", label: "Uploads", icon: "complaint", roles: ["super_admin"] },
      { to: "/staff/logs", label: "Logs", icon: "history", roles: ["super_admin"] },
      { to: "/staff/help", label: "Upload warning", icon: "help", roles: ["super_admin"] },
      { to: "/staff/workflow", label: "Workflow", icon: "refresh", roles: ["super_admin"] },
      { to: "/staff/settings", label: "Settings", icon: "gear", roles: ["super_admin"] },
    ],
  },
];

export function StaffLayout() {
  const { user, loading } = useAuth();
  const [open, setOpen] = useState(false);
  const { pathname, search } = useLocation();
  // Sidebar groups fold away; the one holding the current page is open, and so is "Complaints".
  const [folded, setFolded] = useState<Record<string, boolean>>(() => {
    try { return JSON.parse(localStorage.getItem("nav-folded") ?? "{}"); } catch { return {}; }
  });
  const toggle = (name: string, isOpen: boolean) => setFolded((f) => {
    const next = { ...f, [name]: isOpen };
    try { localStorage.setItem("nav-folded", JSON.stringify(next)); } catch { /* storage unavailable */ }
    return next;
  });
  // How many complaints this person can see, for the badge on "All complaints". Refreshed on every page change and every 30 s.
  const [total, setTotal] = useState<number | null>(null);
  useEffect(() => {
    if (!user) return;
    const load = () => api<{ count: number }>("/complaints/?page_size=1").then((d) => setTotal(d.count)).catch(() => {});
    load();
    const t = setInterval(() => { if (document.visibilityState === "visible") load(); }, 30000);
    return () => clearInterval(t);
  }, [user, pathname]);
  if (loading) return <div className="page-loader"><Loader /></div>;
  if (!user) return <Navigate to="/staff" replace />;
  const groups = NAV.map((g) => ({ ...g, items: g.items.filter((i) => (!i.roles || i.roles.includes(user.base_role)) && (!i.perm || user.permissions?.includes(i.perm))) })).filter((g) => g.items.length);
  return (
    <div className={css.shell}>
      <a className="skip" href="#main">Skip to content</a>
      <header className={css.top}>
        <button className={css.menuBtn} aria-label="Toggle navigation" aria-expanded={open} aria-controls="sidebar" onClick={() => setOpen(!open)}><Icon name={open ? "close" : "menu"} /></button>
        <Link to="/staff/dashboard" className={css.brand}><img src="/bicma-logo.png" alt="" className={css.logo} />BICMA Complaint Management System</Link>
        <div className={css.actions}><NotificationBell /><UserMenu /></div>
      </header>
      <div className={css.body}>
        {open && <button type="button" className={css.sideBackdrop} aria-label="Close navigation" onClick={() => setOpen(false)} />}
        <nav id="sidebar" aria-label="Staff" className={`${css.side} ${open ? css.sideOpen : ""}`} onClick={(e) => { if ((e.target as HTMLElement).closest("a")) setOpen(false); }}>
          {groups.map((g, i) => {
            const hasCurrent = g.items.some((n) => pathname === n.to.split("?")[0] || pathname.startsWith(n.to.split("?")[0] + "/"));
            const isOpen = !g.heading || hasCurrent || (folded[g.heading] ?? g.heading === "Complaints");
            return (
            <div key={i} className={`${css.group} ${g.heading ? css.navSection : ""}`}>
              {g.heading && (
                <button type="button" className={css.headingBtn} aria-expanded={isOpen} disabled={hasCurrent}
                  onClick={(e) => { e.stopPropagation(); toggle(g.heading!, !isOpen); }}>
                  <span>{g.heading}</span><span className={css.headingMeta}><small>{g.items.length}</small><Icon name="chev" size={12} /></span>
                </button>
              )}
              {isOpen && g.items.map((n) => {
                // Triage queue and All complaints share a path, so tell them apart by the query string.
                if (n.to.startsWith("/staff/complaints")) {
                  const triage = n.to.includes("scope=triage");
                  const active = pathname === "/staff/complaints" && search.includes("scope=triage") === triage;
                  return <Link key={n.to} to={n.to} aria-current={active ? "page" : undefined}><Icon name={n.icon} />{n.label}{!triage && total !== null && <span className={css.navCount} aria-label={`${total} complaints`}>{total}</span>}</Link>;
                }
                return <NavLink key={n.to} to={n.to}><Icon name={n.icon} />{n.label}</NavLink>;
              })}
            </div>
            );
          })}
        </nav>
        <main id="main" className={css.main}><Outlet /></main>
      </div>
    </div>
  );
}
