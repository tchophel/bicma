import { useState } from "react";
import { Icon, type IconName } from "../../components/Icon";
import { Loader } from "../../components/Loader";
import { arc, sliceColor } from "../../components/Charts";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../auth";
import { EmptyState, PanelTitle, StatusBadge, fmtDate } from "../../components/ui";
import { type Dashboard, type Meta, type StatItem } from "../../types";
import { useList } from "../../useList";
import "../../styles/Dashboard.css";

function BarList({ title, icon, items, link }: { title: string; icon: IconName; items: StatItem[]; link?: boolean }) {
  const total = items.reduce((n, i) => n + i.count, 0);
  const max = Math.max(1, ...items.map((i) => i.count));
  return (
    <section className="card dash-card" aria-label={title}>
      <PanelTitle icon={icon}>{title}</PanelTitle>
      {items.length === 0 && <EmptyState icon="chart">No data yet.</EmptyState>}
      <ul className="rank-list" tabIndex={items.length > 5 ? 0 : undefined} aria-label={`${title}, scrollable list`}>
        {items.map((i) => {
          const muted = /^(not stated|unknown|none|other)$/i.test(i.label);
          const pct = total ? Math.round((i.count / total) * 100) : 0;
          return (
            <li key={i.label} className={`rank-row${muted ? " muted-row" : ""}`} title={`${i.label}: ${i.count} (${pct}%)`}>
              <div className="rank-top">
                <span className="rank-label">{link && i.query !== undefined ? <Link to={`/staff/complaints?${i.query}`}>{i.label}</Link> : i.label}</span>
                <span className="rank-value"><strong>{i.count}</strong><small>{pct}%</small></span>
              </div>
              <div className="rank-track" aria-hidden="true"><div className="rank-fill" style={{ width: `${Math.max(2, (i.count / max) * 100)}%` }} /></div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

type TrendView = "bar" | "pie" | "table";
const VIEWS: { key: TrendView; label: string; icon: IconName }[] = [{ key: "bar", label: "Bar chart", icon: "chart" }, { key: "pie", label: "Pie chart", icon: "dashboard" }, { key: "table", label: "Table", icon: "complaint" }];

function TrendCard({ items }: { items: StatItem[] }) {
  const [view, setView] = useState<TrendView>("bar");  // always opens on the bar chart; Pie chart and Table are one click away
  const pick = (v: TrendView) => setView(v);
  const total = items.reduce((n, i) => n + i.count, 0);
  const max = Math.max(1, ...items.map((i) => i.count));
  const parts = items.filter((i) => i.count > 0);
  let angle = 0;
  return (
    <section className="card dash-card dash-trend" aria-label="Complaints received by month">
      <div className="trend-head">
        <PanelTitle icon="chart">Complaints received (last 6 months)</PanelTitle>
        <div className="seg" role="group" aria-label="Show as">
          {VIEWS.map((v) => <button type="button" key={v.key} aria-pressed={view === v.key} onClick={() => pick(v.key)}><Icon name={v.icon} size={15} />{v.label}</button>)}
        </div>
      </div>
      {view === "pie" && (total === 0 ? <EmptyState icon="chart">No complaints in these months.</EmptyState> : (
        <div className="trend-pie">
          <svg viewBox="0 0 200 200" role="img" aria-label={`Share of complaints by month: ${parts.map((p) => `${p.label} ${p.count}`).join(", ")}`}>
            {parts.length === 1
              ? <circle cx="100" cy="100" r="92" fill={sliceColor(0, 1)}><title>{`${parts[0].label}: ${parts[0].count} (100%)`}</title></circle>
              : parts.map((p, i) => {
                  const from = angle; angle += (p.count / total) * Math.PI * 2;
                  return <path key={p.label} d={arc(100, 100, 92, from, angle)} fill={sliceColor(i, parts.length)} stroke="var(--c-surface)" strokeWidth="2"><title>{`${p.label}: ${p.count} (${Math.round((p.count / total) * 100)}%)`}</title></path>;
                })}
          </svg>
          <ul className="pie-legend">
            {parts.map((p, i) => <li key={p.label}><span className="pie-swatch" style={{ background: sliceColor(i, parts.length) }} aria-hidden="true" /><span>{p.label}</span><strong>{p.count}</strong><small>{Math.round((p.count / total) * 100)}%</small></li>)}
          </ul>
        </div>
      ))}
      <div className={view === "table" ? "trend-split" : "trend-solo"}>
      {(view === "bar" || view === "table") && (
        <div className="months">
          {items.map((m) => (
            <div key={m.label} title={`${m.label}: ${m.count}`}>
              <b>{m.count}</b>
              <div className="month-bar" style={{ height: `${(m.count / max) * 100}%` }} />
              <small>{m.label.slice(2)}</small>
            </div>
          ))}
        </div>
      )}
      {view === "table" && (
        <div className="table-wrap trend-table"><table>
          <thead><tr><th>Month</th><th>Complaints</th><th>Share</th></tr></thead>
          <tbody>{items.map((m) => <tr key={m.label}><td>{m.label}</td><td><strong>{m.count}</strong></td><td>{total ? `${Math.round((m.count / total) * 100)}%` : "—"}</td></tr>)}</tbody>
          <tfoot><tr><td>Total</td><td><strong>{total}</strong></td><td>{total ? "100%" : "—"}</td></tr></tfoot>
        </table></div>
      )}
      </div>
    </section>
  );
}

const STAT_STYLE: [RegExp, IconName, string][] = [
  [/closed/i, "check", "tone-ok"], [/overdue/i, "alert", "tone-bad"], [/due soon/i, "clock", "tone-warn"],
  [/triage/i, "clock", "tone-warn"], [/resolved/i, "edit", "tone-info"], [/pending/i, "search", "tone-info"],
  [/my assigned/i, "user", ""], [/total/i, "complaint", ""],
];

const statStyle = (label: string): [IconName, string] => { const m = STAT_STYLE.find(([r]) => r.test(label)); return m ? [m[1], m[2]] : ["complaint", ""]; };

export function DashboardPage() {
  const { user } = useAuth();
  const [sp, setSp] = useSearchParams();
  const meta = useList<Meta>("/meta/");
  const { data, err, loading, reload } = useList<Dashboard>(`/dashboard/?${sp.toString()}`);
  if (err) return <p className="error" role="alert">{err}</p>;
  if (!data) return loading ? <Loader /> : null;
  const set = (k: string) => (e: { target: { value: string } }) => { const n = new URLSearchParams(sp); if (e.target.value) n.set(k, e.target.value); else n.delete(k); setSp(n, { replace: true }); };
  return (
    <div className="dashboard-page">
      <header className="dash-hero">
        <div className="dash-hero-copy">
          <span className="dash-hero-eyebrow"><Icon name="dashboard" size={15} />WELCOME BACK{user?.first_name ? `, ${user.first_name.toUpperCase()}` : ""}</span>
          <h1>Dashboard</h1>
          <p>{`Complaints you are permitted to see as ${user?.role_display}. Select any figure to open the matching list.`}</p>
        </div>
        <button type="submit" className="dash-hero-refresh" onClick={reload}><Icon name="refresh" />Refresh</button>
      </header>
      <div className="card filter-bar" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(150px, 100%), 1fr))" }}>
        <label><span>From</span><input type="date" value={sp.get("date_from") ?? ""} onChange={set("date_from")} /></label>
        <label><span>To</span><input type="date" value={sp.get("date_to") ?? ""} onChange={set("date_to")} /></label>
        {user && ["supervisor", "super_admin"].includes(user.base_role) && <label><span>Division</span><select value={sp.get("division") ?? ""} onChange={set("division")}><option value="">All</option>{meta.data?.divisions.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>}
        <label><span>Category</span><select value={sp.get("category") ?? ""} onChange={set("category")}><option value="">All</option>{meta.data?.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label><span>Provider</span><select value={sp.get("provider") ?? ""} onChange={set("provider")}><option value="">All</option>{meta.data?.providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <label><span>Dzongkhag</span><select value={sp.get("dzongkhag") ?? ""} onChange={set("dzongkhag")}><option value="">All</option>{meta.data?.dzongkhags.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label><span>Status</span><select value={sp.get("status") ?? ""} onChange={set("status")}><option value="">All</option>{["received", "triage", "assigned", "investigating", "awaiting_information", "referred", "submitted", "pending_approval", "management_rejected", "resolved", "not_within_mandate", "closed"].map((s) => <option key={s} value={s}>{s === "investigating" ? "under review" : s === "submitted" ? "submitted for approval" : s === "pending_approval" ? "awaiting supervisor approval" : s === "management_rejected" ? "returned by supervisor" : s.replace(/_/g, " ")}</option>)}</select></label>
      </div>
      {data.unassigned_overdue > 0 && <p className="notice" role="status"><Icon name="alert" /> {data.unassigned_overdue} complaint{data.unassigned_overdue === 1 ? " is" : "s are"} still waiting for triage past the response timeline.</p>}
      <div className="stat-grid">
        {data.cards.map((c) => {
          const [icon, tone] = statStyle(c.label);
          return (
            <Link key={c.label} to={`/staff/complaints${c.query ? `?${c.query}` : ""}`} className={`card stat ${tone}`}>
              <span className="stat-icon" aria-hidden="true"><Icon name={icon} size={24} /></span>
              <div><div className="stat-num">{c.count}</div><div className="stat-label">{c.label}</div></div>
            </Link>
          );
        })}
      </div>
      <div className="dash-grid">
        <TrendCard items={data.monthly} />
        <BarList title="By status" icon="clock" items={data.by_status} link />
        <BarList title="By category" icon="category" items={data.by_category} link />
        <BarList title="By division" icon="division" items={data.by_division} link />
        <BarList title="By service provider" icon="users" items={data.by_provider} />
        <BarList title="By Dzongkhag" icon="pin" items={data.by_location} link />
      </div>
      <div className="dash-tables">
      <section style={{ marginTop: 16 }}>
        <PanelTitle icon="alert">Overdue complaints</PanelTitle>
        <div className="table-wrap"><table className="stack-table">
          <thead><tr><th>Reference</th><th>Subject</th><th>Officer</th><th>Due</th></tr></thead>
          <tbody>{data.overdue.map((c) => <tr key={c.id}><td data-label="Reference"><Link className="ref-link" to={`/staff/complaints/${c.id}`}>{c.reference}</Link></td><td data-label="Subject"><span className="cell-subject">{c.subject}</span></td><td data-label="Officer">{c.assigned_to_name ?? "Unassigned"}</td><td data-label="Due">{c.resolution_due_at && fmtDate(c.resolution_due_at)}</td></tr>)}</tbody></table>
          {data.overdue.length === 0 && <EmptyState icon="check">Nothing is overdue.</EmptyState>}
        </div>
      </section>
      <section style={{ marginTop: 16 }}>
        <PanelTitle icon="refresh">Recurring complaints</PanelTitle>
        <div className="table-wrap"><table className="stack-table">
          <thead><tr><th>Category</th><th>Provider</th><th>Location</th><th>Complaints</th></tr></thead>
          <tbody>{data.recurring.map((r, i) => <tr key={i}><td data-label="Category">{r.category}</td><td data-label="Provider">{r.provider}</td><td data-label="Location">{r.location}</td><td data-label="Complaints"><strong>{r.count}</strong></td></tr>)}</tbody></table>
          {data.recurring.length === 0 && <EmptyState icon="chart">No repeated problem areas.</EmptyState>}
        </div>
      </section>
      <section style={{ marginTop: 16 }} className="dash-table-full">
        <PanelTitle icon="complaint">Recent complaints</PanelTitle>
        <div className="table-wrap"><table className="stack-table">
          <thead><tr><th>Reference</th><th>Subject</th><th>Status</th><th>Received</th></tr></thead>
          <tbody>
            {data.recent.map((c) => <tr key={c.id}><td data-label="Reference"><Link className="ref-link" to={`/staff/complaints/${c.id}`}>{c.reference}</Link></td><td data-label="Subject"><span className="cell-subject">{c.subject}</span></td>
              <td data-label="Status"><StatusBadge value={c.internal_status} label={c.internal_status_display} /></td><td data-label="Received">{fmtDate(c.created_at)}</td></tr>)}
          </tbody></table>
          {data.recent.length === 0 && <EmptyState icon="complaint">No complaints yet.</EmptyState>}
        </div>
      </section>
      </div>
    </div>
  );
}
