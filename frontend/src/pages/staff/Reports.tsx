import { useState } from "react";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { Icon } from "../../components/Icon";
import { EmptyState, PageHeader } from "../../components/ui";
import type { Meta } from "../../types";
import { useList } from "../../useList";

interface Report { title: string; subtitle?: string; columns: string[]; rows: (string | number)[][]; total_rows: number }

function range(period: string): { date_from?: string; date_to?: string } {
  const now = new Date(); const iso = (d: Date) => d.toISOString().slice(0, 10);
  if (period === "month") return { date_from: iso(new Date(now.getFullYear(), now.getMonth(), 1)) };
  if (period === "quarter") return { date_from: iso(new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1)) };
  if (period === "year") return { date_from: iso(new Date(now.getFullYear(), 0, 1)) };
  return {};
}

export function Reports() {
  const canExport = !!useAuth().user?.permissions?.includes("export_reports");
  const list = useList<{ key: string; name: string }[]>("/reports/");
  const meta = useList<Meta>("/meta/").data;
  const [key, setKey] = useState("monthly");
  const thisMonth = new Date().toISOString().slice(0, 7);
  const [f, setF] = useState<Record<string, string>>({ period: "pick", month: thisMonth });
  const [rep, setRep] = useState<Report | null>(null);
  const [err, setErr] = useState("");
  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const query = () => {
    const { period, ...rest } = f;
    const all = { ...(period === "custom" || period === "pick" ? {} : range(period)), ...rest };
    if (period !== "pick") delete (all as Record<string, string>).month;
    return new URLSearchParams(Object.entries(all).filter(([, v]) => v) as [string, string][]).toString();
  };
  async function run() {
    setErr("");
    try { setRep(await api<Report>(`/reports/${key}/?${query()}`)); } catch (x) { setErr((x as Error).message); setRep(null); }
  }
  return (
    <>
      <PageHeader icon="chart" title="Reports" subtitle="Generate, print and export complaint reports. Exports are recorded in the audit log." />
      <section className="card filter-bar" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))" }}>
        <label><span>Report</span><select value={key} onChange={(e) => setKey(e.target.value)}>{list.data?.map((r) => <option key={r.key} value={r.key}>{r.name}</option>)}</select></label>
        <label><span>Period</span><select value={f.period} onChange={set("period")}><option value="pick">A chosen month</option><option value="month">This month so far</option><option value="quarter">This quarter</option><option value="year">This year</option><option value="custom">Custom / all</option></select></label>
        {f.period === "pick" && <label><span>Month</span><input type="month" value={f.month} max={thisMonth} onChange={set("month")} /></label>}
        {f.period === "custom" && <><label><span>From</span><input type="date" onChange={set("date_from")} /></label><label><span>To</span><input type="date" onChange={set("date_to")} /></label></>}
        <label><span>Division</span><select onChange={set("division")}><option value="">All</option>{meta?.divisions.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label><span>Category</span><select onChange={set("category")}><option value="">All</option>{meta?.categories.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label><span>Provider type</span><select onChange={set("provider_type")}><option value="">All</option>{meta?.provider_types.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label><span>Provider</span><select onChange={set("provider")}><option value="">All</option>{meta?.providers.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label><span>Dzongkhag</span><select onChange={set("dzongkhag")}><option value="">All</option>{meta?.dzongkhags.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label><span>Status</span><select onChange={set("status")}><option value="">All</option>{["received", "triage", "assigned", "investigating", "awaiting_information", "referred", "pending_approval", "management_rejected", "resolved", "not_within_mandate", "closed"].map((s) => <option key={s} value={s}>{s === "investigating" ? "under review" : s === "pending_approval" ? "awaiting management approval" : s === "management_rejected" ? "returned by management" : s.replace(/_/g, " ")}</option>)}</select></label>
      </section>
      <p><button className="btn" onClick={run}><Icon name="chart" />Generate report</button></p>
      {err && <p className="error" role="alert">{err}</p>}
      {rep && (
        <section className="card" aria-label={rep.title}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
            <h2 style={{ margin: 0, flex: 1 }}>{rep.title}{rep.subtitle ? ` · ${rep.subtitle}` : ""} <span className="chip">{rep.total_rows} rows</span></h2>
            {canExport && ["csv", "xlsx", "pdf"].map((x) => <a key={x} className="btn secondary" href={`/api/reports/${key}/?${query()}&export=${x}`}><Icon name="send" />{x.toUpperCase()}</a>)}
            <button className="btn secondary" onClick={() => window.print()}><Icon name="complaint" />Print</button>
          </div>
          <div className="table-wrap"><table>
            <thead><tr>{rep.columns.map((c, i) => <th key={i}>{c}</th>)}</tr></thead>
            <tbody>{rep.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{String(v)}</td>)}</tr>)}</tbody>
          </table>{rep.rows.length === 0 && <EmptyState icon="chart">No data for these filters.</EmptyState>}</div>
          {rep.total_rows > rep.rows.length && <p className="muted">Showing the first {rep.rows.length}. Export to get all rows.</p>}
        </section>
      )}
    </>
  );
}
