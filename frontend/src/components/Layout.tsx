import { useState } from "react";
import { NavLink, Link, Outlet, Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import type { Role } from "../types";
import { Icon, type IconName } from "./Icon";
import css from "./Layout.module.css";
import pub from "./Public.module.css";
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
          <div className={pub.footBrand}><strong>BICMA</strong><span>Bhutan InfoComm and Media Authority</span></div>
          <span>&copy; {new Date().getFullYear()} BICMA. All rights reserved.</span>
        </div>
      </footer>
    </div>
  );
}

interface NavItem { to: string; label: string; icon: IconName; roles?: Role[] }
const NAV: { heading?: string; items: NavItem[] }[] = [
  { items: [{ to: "/staff/dashboard", label: "Dashboard", icon: "dashboard" }] },
  {
    heading: "Complaints",
    items: [
      { to: "/staff/complaints", label: "All complaints", icon: "complaint" },
      { to: "/staff/register", label: "Register complaint", icon: "plus", roles: ["focal", "investigator", "super_admin"] },
    ],
  },
  {
    heading: "Master data",
    items: [
      { to: "/staff/dzongkhags", label: "Dzongkhags", icon: "map", roles: ["super_admin"] },
      { to: "/staff/gewogs", label: "Gewogs", icon: "pin", roles: ["super_admin"] },
      { to: "/staff/divisions", label: "Divisions", icon: "division", roles: ["super_admin"] },
      { to: "/staff/categories", label: "Categories", icon: "category", roles: ["super_admin"] },
    ],
  },
  {
    heading: "Administration",
    items: [
      { to: "/staff/users", label: "Users", icon: "users", roles: ["super_admin"] },
      { to: "/staff/audit", label: "Audit logs", icon: "history", roles: ["super_admin"] },
      { to: "/staff/help", label: "Help & FAQ", icon: "help", roles: ["super_admin"] },
      { to: "/staff/settings", label: "Settings", icon: "gear", roles: ["super_admin"] },
    ],
  },
];

export function StaffLayout() {
  const { user, loading } = useAuth();
  const [open, setOpen] = useState(false);
  if (loading) return <p className="container">Loading…</p>;
  if (!user) return <Navigate to="/staff" replace />;
  const groups = NAV.map((g) => ({ ...g, items: g.items.filter((i) => !i.roles || i.roles.includes(user.role)) })).filter((g) => g.items.length);
  return (
    <div className={css.shell}>
      <a className="skip" href="#main">Skip to content</a>
      <header className={css.top}>
        <button className={css.menuBtn} aria-label="Toggle navigation" aria-expanded={open} aria-controls="sidebar" onClick={() => setOpen(!open)}><Icon name={open ? "close" : "menu"} /></button>
        <Link to="/staff/dashboard" className={css.brand}><img src="/bicma-logo.png" alt="" className={css.logo} />BICMA Complaint Management System</Link>
        <div className={css.actions}><NotificationBell /><UserMenu /></div>
      </header>
      <div className={css.body}>
        <nav id="sidebar" aria-label="Staff" className={`${css.side} ${open ? css.sideOpen : ""}`} onClick={() => setOpen(false)}>
          {groups.map((g, i) => (
            <div key={i} className={css.group}>
              {g.heading && <div className={css.heading}>{g.heading}</div>}
              {g.items.map((n) => <NavLink key={n.to} to={n.to} end={n.to === "/staff/complaints"}><Icon name={n.icon} />{n.label}</NavLink>)}
            </div>
          ))}
        </nav>
        <main id="main" className={css.main}><Outlet /></main>
      </div>
    </div>
  );
}
