import { Icon } from "../../components/Icon";
import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../auth";
import { EmptyState, PageHeader, StatusBadge, fmtDate } from "../../components/ui";
import { type ComplaintRow, type Meta, type Page } from "../../types";
import { useList } from "../../useList";
import { ComplaintPanel } from "./ComplaintPopup";
import "./Complaints.css";

export function Complaints() {
  const { user } = useAuth();
  const [sp, setSp] = useSearchParams();
  const f = { q: sp.get("q") ?? "", scope: sp.get("scope") ?? "", status: sp.get("status") ?? "", category: sp.get("category") ?? "", division: sp.get("division") ?? "" };
  const page = Number(sp.get("page") ?? 1);
  const update = (patch: Record<string, string>) => {
    const next = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(patch)) (v ? next.set(k, v) : next.delete(k));
    setSp(next, { replace: true });
  };
  const setPage = (n: number) => update({ page: n > 1 ? String(n) : "" });
  const openId = sp.get("open");
  const closePanel = () => update({ open: "" });
  useEffect(() => {
    if (!openId) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closePanel(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openId]);
  const meta = useList<Meta>("/meta/");
  const qs = new URLSearchParams({ page: String(page), ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) }).toString();
  const { data, err, loading, reload } = useList<Page<ComplaintRow>>(`/complaints/?${qs}`);
  const set = (k: string) => (e: { target: { value: string } }) => update({ [k]: e.target.value, page: "" });
  const filtered = Object.values(f).some(Boolean);
  const STATUSES = ["submitted", "unassigned", "assigned_to_division", "assigned_to_officer", "investigation_in_progress", "findings_submitted", "awaiting_focal_approval", "awaiting_supervisor_approval", "pending_response", "pending_external_action", "on_hold", "referred", "closed", "rejected"];
  return (
    <>
      <PageHeader icon="complaint" title="Complaints" subtitle="Search and filter every complaint you are permitted to see.">
        {user && ["focal", "investigator", "super_admin"].includes(user.role) && <Link className="btn" to="/staff/register"><Icon name="plus" />Register complaint</Link>}
      </PageHeader>
      <div className="card filter-bar">
        <label><span>Search</span><div className="search-wrap"><Icon name="search" /><input value={f.q} onChange={set("q")} placeholder="Reference, subject or name" /></div></label>
        <label><span>Scope</span>
          <select value={f.scope} onChange={set("scope")}>
            <option value="">All I can see</option>
            <option value="mine">Assigned to me</option>
            <option value="unassigned">Unassigned</option>
            {user?.division && <option value="division">My division</option>}
          </select>
        </label>
        <label><span>Status</span>
          <select value={f.status} onChange={set("status")}>
            <option value="">Any</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
          </select>
        </label>
        <label><span>Category</span>
          <select value={f.category} onChange={set("category")}>
            <option value="">Any</option>
            {meta.data?.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
      </div>
      {filtered && (
        <div className="chips" aria-label="Active filters">
          {f.q && <span className="chip plain">Search: {f.q}</span>}
          {f.scope && <span className="chip plain">Scope: {f.scope}</span>}
          {f.status && <span className="chip plain">Status: {f.status.replace(/_/g, " ")}</span>}
          {f.category && <span className="chip plain">Category: {meta.data?.categories.find((c) => String(c.id) === f.category)?.name ?? f.category}</span>}
          {f.division && <span className="chip plain">One division</span>}
          <button className="chip" onClick={() => setSp({})}><Icon name="close" size={14} />Clear all filters</button>
        </div>
      )}
      {err && <p className="error" role="alert">{err}</p>}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Reference</th><th>Subject</th><th>Category</th><th>Division</th><th>Assigned to</th><th>Status</th><th>Received</th></tr></thead>
          <tbody>
            {data?.results.map((c) => (
              <tr key={c.id} className={`clickable ${String(c.id) === openId ? "row-active" : ""}`} onClick={() => update({ open: String(c.id) })}>
                <td><button type="button" className="ref-link linklike" aria-label={`Open ${c.reference}`} onClick={(e) => { e.stopPropagation(); update({ open: String(c.id) }); }}>{c.reference}</button></td>
                <td>{c.subject}</td><td><span className="chip plain">{c.category_name}</span></td>
                <td>{c.division_name ?? <span className="muted">Unassigned</span>}</td>
                <td>{c.assigned_to_name ?? "—"}</td>
                <td><StatusBadge value={c.internal_status} label={c.internal_status_display} /></td>
                <td>{fmtDate(c.created_at)}</td>
              </tr>
            ))}
            {loading && <tr><td colSpan={7} className="muted">Loading…</td></tr>}
          </tbody>
        </table>
        {!loading && data?.results.length === 0 && <EmptyState icon="search">No complaints match your filters.</EmptyState>}
      </div>
      {data && (
        <div className="pager">
          <span>{data.count} complaint{data.count === 1 ? "" : "s"}</span>
          <div>
            <button className="btn secondary" disabled={!data.previous} onClick={() => setPage(page - 1)}><Icon name="left" size={16} />Previous</button>
            <button className="btn secondary" disabled={!data.next} onClick={() => setPage(page + 1)}>Next<Icon name="right" size={16} /></button>
          </div>
        </div>
      )}
      {openId && (<>
        <div className="panel-backdrop" onClick={closePanel} aria-hidden="true" />
        <ComplaintPanel key={openId} id={openId} onClose={closePanel} onAssigned={reload} />
      </>)}
    </>
  );
}
