import { Icon, type IconName } from "../../components/Icon";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth";
import { EmptyState, PageHeader, PanelTitle, StatusBadge, fmtDate } from "../../components/ui";
import { type Dashboard, type StatItem } from "../../types";
import { useList } from "../../useList";
import "./Dashboard.css";

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
  [/resolved/i, "check", "tone-ok"], [/rejected/i, "close", "tone-bad"], [/unassigned/i, "alert", "tone-warn"],
  [/awaiting my approval|findings awaiting/i, "edit", "tone-info"], [/screening/i, "clock", "tone-warn"],
  [/external/i, "send", "tone-warn"], [/pending response/i, "mail", "tone-warn"], [/returned/i, "refresh", "tone-bad"],
  [/investigation/i, "search", "tone-info"], [/my assigned/i, "user", ""], [/division/i, "division", ""], [/total/i, "complaint", ""],
];

const statStyle = (label: string): [IconName, string] => { const m = STAT_STYLE.find(([r]) => r.test(label)); return m ? [m[1], m[2]] : ["complaint", ""]; };

export function DashboardPage() {
  const { user } = useAuth();
  const { data, err, loading, reload } = useList<Dashboard>("/dashboard/");
  if (err) return <p className="error" role="alert">{err}</p>;
  if (!data) return <p>{loading ? "Loading…" : ""}</p>;
  const maxM = Math.max(1, ...data.monthly.map((m) => m.count));
  return (
    <>
      <PageHeader icon="dashboard" title="Dashboard" subtitle={`Complaints you are permitted to see as ${user?.role_display}. Select any figure to open the matching list.`}>
        <button className="btn secondary" onClick={reload}><Icon name="refresh" />Refresh</button>
      </PageHeader>
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
        {data.by_division && <BarList title="By division" icon="division" items={data.by_division} link />}
        {data.by_area && <BarList title="By Dzongkhag (top 10)" icon="pin" items={data.by_area} />}
        {data.by_officer && <BarList title="Open complaints by officer" icon="users" items={data.by_officer} />}
      </div>
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
