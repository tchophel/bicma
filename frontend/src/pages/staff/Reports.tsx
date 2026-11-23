import { useEffect, useState } from "react";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { Icon } from "../../components/Icon";
import { EmptyState, PageHeader } from "../../components/ui";
import { ReportInsights } from "../../components/ReportInsights";
import type { Meta } from "../../types";
import { useList } from "../../useList";

import "../../styles/Reports.css";

interface Report { title: string; subtitle?: string; columns: string[]; rows: (string | number)[][]; total_rows: number }

export function Reports() {
  const canExport = !!useAuth().user?.permissions?.includes("export_reports");
  const meta = useList<Meta>("/meta/").data;
  const [f, setF] = useState<Record<string, string>>({});
  const [rep, setRep] = useState<Report | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(true);
  const [generated, setGenerated] = useState({ key: "summary", query: "" });
  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const query = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
  useEffect(() => {
    let active = true;
    setErr(""); setBusy(true); setRep(null);
    api<Report>(`/reports/summary/?${query}`).then((report) => {
      if (active) { setRep(report); setGenerated({ key: "summary", query }); }
    }).catch((x) => { if (active) setErr((x as Error).message); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [query]);
  return (
    <div className="reports-page">
      <PageHeader icon="chart" title="Reports" subtitle="View, print and export your complaint summary. Results update automatically when you change a filter." />
      <section className="card report-builder" aria-label="Report filters">
        <fieldset className="report-builder-fields">
        <div className="report-filter-heading"><h3><Icon name="search" size={17} />Refine results</h3><span>Optional · Leave as All to include everything</span></div>
        <div className="report-secondary-fields">
        <label><span>Division</span><select onChange={set("division")}><option value="">All</option>{meta?.divisions.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label><span>Category</span><select onChange={set("category")}><option value="">All</option>{meta?.categories.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label><span>Provider type</span><select onChange={set("provider_type")}><option value="">All</option>{meta?.provider_types.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label><span>Provider</span><select onChange={set("provider")}><option value="">All</option>{meta?.providers.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label><span>Dzongkhag</span><select onChange={set("dzongkhag")}><option value="">All</option>{meta?.dzongkhags.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label><span>Status</span><select onChange={set("status")}><option value="">All</option>{["received", "triage", "assigned", "investigating", "awaiting_information", "referred", "submitted", "pending_approval", "management_rejected", "resolved", "not_within_mandate", "closed"].map((s) => <option key={s} value={s}>{s === "investigating" ? "under review" : s === "submitted" ? "submitted for approval" : s === "pending_approval" ? "awaiting supervisor approval" : s === "management_rejected" ? "returned by supervisor" : s.replace(/_/g, " ")}</option>)}</select></label>
        </div>
        </fieldset>
        <div className="report-builder-footer"><p><Icon name="lock" size={16} />Exports are recorded in the audit log.</p></div>
      </section>
      {err && <p className="error" role="alert">{err}</p>}
      {rep && <ReportInsights key={generated.query} query={generated.query} />}
      {rep && (
        <section className="card report-result" aria-label={rep.title}>
          <div className="report-result-heading">
            <h2 style={{ margin: 0, flex: 1 }}>{rep.title}{rep.subtitle ? ` · ${rep.subtitle}` : ""} <span className="chip">{rep.total_rows} rows</span></h2>
            {canExport && ["csv", "xlsx", "pdf"].map((x) => <a key={x} className="btn secondary" href={`/api/reports/${generated.key}/?${generated.query}&export=${x}`}><Icon name="send" />{x.toUpperCase()}</a>)}
            <button className="btn secondary" onClick={() => window.print()}><Icon name="complaint" />Print</button>
          </div>
          <div className="table-wrap report-table-wrap"><table className={generated.key === "monthly" ? "report-monthly-table" : "report-data-table"}>
            <thead><tr>{rep.columns.map((c, i) => <th key={i}>{c}</th>)}</tr></thead>
            <tbody>{rep.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{String(v).length > 180 ? <><details className="report-long-text"><summary>{String(v).slice(0, 180)}… <span>Show full text</span></summary><p>{String(v)}</p></details><span className="report-print-text">{String(v)}</span></> : String(v) || "—"}</td>)}</tr>)}</tbody>
          </table>{rep.rows.length === 0 && <EmptyState icon="chart">No data for these filters.</EmptyState>}</div>
          {rep.total_rows > rep.rows.length && <p className="muted">Showing the first {rep.rows.length}. Export to get all rows.</p>}
        </section>
      )}
      {busy && <p className="report-start-note" role="status"><Icon name="refresh" size={20} />Loading report…</p>}
    </div>
  );
}
