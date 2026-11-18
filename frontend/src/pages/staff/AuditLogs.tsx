import { Icon } from "../../components/Icon";
import { useState } from "react";
import { PageHeader, fmt } from "../../components/ui";
import { type AuditEntry, type Page } from "../../types";
import { useList } from "../../useList";

export function AuditLogs() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const { data, err, loading } = useList<Page<AuditEntry>>(`/admin/audit-logs/?page=${page}&page_size=10&${action ? `action=${encodeURIComponent(action)}` : ""}`);
  return (<>
    <PageHeader icon="history" title="Audit logs" subtitle="Append-only record of security and business events." />
    <div className="card filter-bar" style={{ gridTemplateColumns: "1fr" }}><label><span>Action prefix</span><div className="search-wrap"><Icon name="search" /><input value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} placeholder="e.g. auth. or complaint." /></div></label></div>
    {err && <p className="error">{err}</p>}
    <div className="table-wrap"><table><thead><tr><th>When</th><th>User</th><th>Action</th><th>Entity</th><th>Detail</th><th>IP</th></tr></thead>
      <tbody>{data?.results.map((a) => <tr key={a.id}><td>{fmt(a.created_at)}</td><td>{a.actor_email || "—"}</td><td>{a.action}</td><td>{a.entity_type} {a.entity_id}</td><td><code>{JSON.stringify(a.detail)}</code></td><td>{a.ip_address}</td></tr>)}
        {loading && <tr><td colSpan={6}>Loading…</td></tr>}
        {!loading && data?.results.length === 0 && <tr><td colSpan={6} className="muted">No audit entries match.</td></tr>}</tbody></table></div>
    <div className="pager">
      <span className="muted">{data?.count ? `Showing ${(page - 1) * 10 + 1}–${(page - 1) * 10 + data.results.length} of ${data.count} entries` : "0 entries"}</span>
      <div>
        <button className="btn secondary" disabled={loading || !data?.previous} onClick={() => setPage((current) => current - 1)}><Icon name="left" size={16} />Previous</button>
        <span aria-live="polite">{page} / {Math.max(1, Math.ceil((data?.count ?? 0) / 10))}</span>
        <button className="btn secondary" disabled={loading || !data?.next} onClick={() => setPage((current) => current + 1)}>Next<Icon name="right" size={16} /></button>
      </div>
    </div></>);
}
