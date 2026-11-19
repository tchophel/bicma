import { Icon, type IconName } from "../../components/Icon";
import { Loader } from "../../components/Loader";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../auth";
import { EmptyState, PageHeader, PanelTitle, StatusBadge, fmtDate } from "../../components/ui";
import { type Dashboard, type Meta, type StatItem } from "../../types";
import { useList } from "../../useList";
import "../../styles/Dashboard.css";

function BarList({ title, icon, items, link }: { title: string; icon: IconName; items: StatItem[]; link?: boolean }) {
  const max = Math.max(1, ...items.map((i) => i.count));
  return (
    <section className="card" aria-label={title}>
      <PanelTitle icon={icon}>{title}</PanelTitle>
      {items.length === 0 && <EmptyState icon="chart">No data yet.</EmptyState>}
      {items.map((i) => (
        <div key={i.label} className="bar-row">
          <div>
            <span>{link && i.query !== undefined ? <Link to={`/staff/complaints?${i.query}`}>{i.label}</Link> : i.label}</span>
            <strong>{i.count}</strong>
          </div>
          <div className="bar-track" aria-hidden="true"><div className="bar-fill" style={{ width: `${(i.count / max) * 100}%` }} /></div>
        </div>
      ))}
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
  const maxM = Math.max(1, ...data.monthly.map((m) => m.count));
  const set = (k: string) => (e: { target: { value: string } }) => { const n = new URLSearchParams(sp); if (e.target.value) n.set(k, e.target.value); else n.delete(k); setSp(n, { replace: true }); };
  const hrs = (t: { average: number | null; median: number | null }) => t.average === null ? "No data yet" : `avg ${t.average} h · median ${t.median} h`;
  return (
    <>
      <PageHeader icon="dashboard" title="Dashboard" subtitle={`Complaints you are permitted to see as ${user?.role_display}. Select any figure to open the matching list.`}>
        <button className="btn secondary" onClick={reload}><Icon name="refresh" />Refresh</button>
      </PageHeader>
      <div className="card filter-bar" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
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
        <div className="card stat"><span className="stat-icon" aria-hidden="true"><Icon name="clock" size={24} /></span><div><div className="stat-label">Time to first response</div><strong>{hrs(data.time_to_acknowledge_hours)}</strong></div></div>
        <div className="card stat"><span className="stat-icon" aria-hidden="true"><Icon name="check" size={24} /></span><div><div className="stat-label">Time to resolve</div><strong>{hrs(data.time_to_resolve_hours)}</strong></div></div>
      </div>
      <div className="dash-grid">
        <section className="card" aria-label="Monthly trend">
          <PanelTitle icon="chart">Complaints received (last 6 months)</PanelTitle>
          <div className="months">
            {data.monthly.map((m) => (
              <div key={m.label}>
                <b>{m.count}</b>
                <div className="month-bar" title={`${m.label}: ${m.count}`} style={{ height: `${(m.count / maxM) * 100}%` }} />
                <small>{m.label.slice(2)}</small>
              </div>
            ))}
          </div>
        </section>
        <BarList title="By status" icon="clock" items={data.by_status} link />
        <BarList title="By category" icon="category" items={data.by_category} link />
        <BarList title="By division" icon="division" items={data.by_division} link />
        <BarList title="By service provider" icon="users" items={data.by_provider} />
        <BarList title="By Dzongkhag" icon="pin" items={data.by_location} link />
      </div>
      <section style={{ marginTop: 16 }}>
        <PanelTitle icon="alert">Overdue complaints</PanelTitle>
        <div className="table-wrap"><table>
          <thead><tr><th>Reference</th><th>Subject</th><th>Officer</th><th>Due</th></tr></thead>
          <tbody>{data.overdue.map((c) => <tr key={c.id}><td><Link className="ref-link" to={`/staff/complaints/${c.id}`}>{c.reference}</Link></td><td>{c.subject}</td><td>{c.assigned_to_name ?? "Unassigned"}</td><td>{c.resolution_due_at && fmtDate(c.resolution_due_at)}</td></tr>)}</tbody></table>
          {data.overdue.length === 0 && <EmptyState icon="check">Nothing is overdue.</EmptyState>}
        </div>
      </section>
      <section style={{ marginTop: 16 }}>
        <PanelTitle icon="refresh">Recurring complaints</PanelTitle>
        <div className="table-wrap"><table>
          <thead><tr><th>Category</th><th>Provider</th><th>Location</th><th>Complaints</th></tr></thead>
          <tbody>{data.recurring.map((r, i) => <tr key={i}><td>{r.category}</td><td>{r.provider}</td><td>{r.location}</td><td><strong>{r.count}</strong></td></tr>)}</tbody></table>
          {data.recurring.length === 0 && <EmptyState icon="chart">No repeated problem areas.</EmptyState>}
        </div>
      </section>
      <section style={{ marginTop: 16 }}>
        <PanelTitle icon="complaint">Recent complaints</PanelTitle>
        <div className="table-wrap"><table>
          <thead><tr><th>Reference</th><th>Subject</th><th>Status</th><th>Received</th></tr></thead>
          <tbody>
            {data.recent.map((c) => <tr key={c.id}><td><Link className="ref-link" to={`/staff/complaints/${c.id}`}>{c.reference}</Link></td><td>{c.subject}</td>
              <td><StatusBadge value={c.internal_status} label={c.internal_status_display} /></td><td>{fmtDate(c.created_at)}</td></tr>)}
          </tbody></table>
          {data.recent.length === 0 && <EmptyState icon="complaint">No complaints yet.</EmptyState>}
        </div>
      </section>
    </>
  );
}
