import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../api";
import { Icon } from "../../components/Icon";
import { EmptyState, Field, PageHeader, PanelTitle, fmt } from "../../components/ui";
import { useList } from "../../useList";

interface Data {
  count: number; total_bytes: number; matches: number; page: number; pages: number;
  limits: { upload_max_mb: number; upload_max_files: number; photo_max_kb: number };
  results: { id: string; name: string; size: number; visibility: string; created_at: string; complaint: string; reference: string; uploaded_by: string }[];
}
const size = (b: number) => (b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

/** Administration > Uploads: the upload limits, how much is stored, and every uploaded document. */
export function Uploads() {
  const [q, setQ] = useState("");
  const [vis, setVis] = useState("");
  const [page, setPage] = useState(1);
  const { data, err, loading, reload } = useList<Data>(`/admin/uploads/?page=${page}${q ? `&q=${encodeURIComponent(q)}` : ""}${vis ? `&visibility=${vis}` : ""}`);
  const [lim, setLim] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const val = (k: "upload_max_mb" | "upload_max_files" | "photo_max_kb") => lim[k] ?? String(data?.limits[k] ?? "");

  async function save(e: FormEvent) {
    e.preventDefault(); setMsg({});
    try {
      await api("/admin/settings/", { method: "PATCH", json: { upload_max_mb: Number(val("upload_max_mb")), upload_max_files: Number(val("upload_max_files")), photo_max_kb: Number(val("photo_max_kb")) } });
      setLim({}); reload(); setMsg({ ok: "Upload limits saved." });
    } catch (x) { setMsg({ err: (x as ApiError).message }); }
  }
  return (
    <>
      <PageHeader icon="complaint" title="Uploads" subtitle="Upload limits, storage used and every document attached to a complaint." />
      {err && <p className="error" role="alert">{err}</p>}
      <div className="stat-grid">
        <div className="card stat"><span className="stat-icon" aria-hidden="true"><Icon name="complaint" size={24} /></span><div><div className="stat-num">{data?.count ?? "—"}</div><div className="stat-label">Documents stored</div></div></div>
        <div className="card stat"><span className="stat-icon" aria-hidden="true"><Icon name="chart" size={24} /></span><div><div className="stat-num">{data ? size(data.total_bytes) : "—"}</div><div className="stat-label">Space used</div></div></div>
      </div>
      <form className="card" onSubmit={save} style={{ marginBottom: 16 }}>
        <PanelTitle icon="gear">Upload limits</PanelTitle>
        <div className="row">
          <Field label="Largest document (MB)" required hint="1 to 20 MB per file."><input type="number" min={1} max={20} required value={val("upload_max_mb")} onChange={(e) => setLim({ ...lim, upload_max_mb: e.target.value })} /></Field>
          <Field label="Files per upload" required hint="1 to 10. Size times files may not exceed 40 MB."><input type="number" min={1} max={10} required value={val("upload_max_files")} onChange={(e) => setLim({ ...lim, upload_max_files: e.target.value })} /></Field>
          <Field label="Largest profile photo (KB)" required hint="50 to 5120 KB (5120 KB = 5 MB)."><input type="number" min={50} max={5120} required value={val("photo_max_kb")} onChange={(e) => setLim({ ...lim, photo_max_kb: e.target.value })} /></Field>
        </div>
        {msg.err && <p className="error" role="alert">{msg.err}</p>}{msg.ok && <p className="notice" role="status">{msg.ok}</p>}
        <button className="btn"><Icon name="check" />Save limits</button>
      </form>
      <section className="card">
        <PanelTitle icon="search">All documents</PanelTitle>
        <div className="filter-bar" style={{ gridTemplateColumns: "2fr 1fr", padding: 0, boxShadow: "none", border: 0 }}>
          <label><span>Search</span><div className="search-wrap"><Icon name="search" /><input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="File name or complaint reference" /></div></label>
          <label><span>Visibility</span><select value={vis} onChange={(e) => { setVis(e.target.value); setPage(1); }}><option value="">All</option><option value="public">Shared with complainant</option><option value="internal">Internal</option></select></label>
        </div>
        <div className="table-wrap"><table>
          <thead><tr><th>File</th><th>Size</th><th>Complaint</th><th>Uploaded by</th><th>Visibility</th><th>Date</th></tr></thead>
          <tbody>
            {data?.results.map((a) => (
              <tr key={a.id}><td><a href={`/api/complaints/${a.complaint}/attachments/${a.id}/`}>{a.name}</a></td><td>{size(a.size)}</td>
                <td><Link className="ref-link" to={`/staff/complaints/${a.complaint}`}>{a.reference}</Link></td><td>{a.uploaded_by}</td>
                <td><span className={`badge ${a.visibility === "public" ? "" : "warn"}`}>{a.visibility === "public" ? "Shared" : "Internal"}</span></td><td>{fmt(a.created_at)}</td></tr>
            ))}
            {loading && <tr><td colSpan={6} className="muted">Loading…</td></tr>}
          </tbody>
        </table>
        {!loading && data?.results.length === 0 && <EmptyState icon="search">No documents match.</EmptyState>}</div>
        {data && <div className="pager"><span>{data.matches} document{data.matches === 1 ? "" : "s"}</span>
          <div><button className="btn secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}><Icon name="left" size={16} />Previous</button>
            <button className="btn secondary" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next<Icon name="right" size={16} /></button></div></div>}
      </section>
    </>
  );
}
