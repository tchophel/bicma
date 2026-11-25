import { useState, type FormEvent } from "react";
import { Loader } from "../../components/Loader";
import { useToast } from "../../components/Toast";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../api";
import { Icon } from "../../components/Icon";
import { EmptyState, Field, PageHeader, PanelTitle, fmt, humanKb } from "../../components/ui";
import type { Limits } from "../../types";
import { useList } from "../../useList";

interface Data {
  count: number; total_bytes: number; matches: number; page: number; pages: number;
  limits: Limits;
  results: { id: string; name: string; size: number; visibility: string; created_at: string; complaint: string; reference: string; uploaded_by: string }[];
}
const size = (b: number) => (b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

/** A size limit entered as a number with a KB or MB unit; the value is kept in KB. */
function SizeField({ label, hint, kb, onChange, minKb, maxKb }: { label: string; hint: string; kb: number; onChange: (kb: number) => void; minKb: number; maxKb: number }) {
  const [unit, setUnit] = useState<"KB" | "MB">(kb % 1024 === 0 && kb >= 1024 ? "MB" : "KB");
  const shown = unit === "MB" ? Number((kb / 1024).toFixed(2)) : kb;
  const set = (n: number, u = unit) => onChange(Math.round(n * (u === "MB" ? 1024 : 1)));
  return (
    <Field label={label} required hint={`${hint} (${humanKb(minKb)} to ${humanKb(maxKb)}).`}>
      <div style={{ display: "flex", gap: 8 }}>
        <input type="number" step={unit === "MB" ? "0.1" : "1"} min={0} required value={Number.isNaN(shown) ? "" : shown} onChange={(e) => set(Number(e.target.value))} />
        <select aria-label={`${label} unit`} style={{ width: 90 }} value={unit} onChange={(e) => { const u = e.target.value as "KB" | "MB"; setUnit(u); set(u === "MB" ? kb / 1024 : kb, u); }}><option>KB</option><option>MB</option></select>
      </div>
    </Field>
  );
}

/** Administration > Uploads: the upload limits, how much is stored, and every uploaded document. */
export function Uploads() {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [vis, setVis] = useState("");
  const [page, setPage] = useState(1);
  const { data, err, loading, reload } = useList<Data>(`/admin/uploads/?page=${page}${q ? `&q=${encodeURIComponent(q)}` : ""}${vis ? `&visibility=${vis}` : ""}`);
  const [lim, setLim] = useState<Partial<Limits>>({});
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const cur = (data ? { ...data.limits, ...lim } : null) as Limits | null;

  async function save(e: FormEvent) {
    e.preventDefault(); setMsg({});
    if (!cur) return;
    try {
      await api("/admin/settings/", { method: "PATCH", json: { upload_max_kb: cur.upload_max_kb, upload_max_files: cur.upload_max_files, photo_max_kb: cur.photo_max_kb, upload_types: cur.upload_types, upload_instructions: cur.upload_instructions } });
      setLim({}); reload(); toast.success("Upload settings saved.");
    } catch (x) { setMsg({ err: (x as ApiError).message }); toast.error((x as ApiError).message); }
  }
  const toggleType = (key: string, on: boolean) => cur && setLim({ ...lim, upload_types: on ? [...cur.upload_types, key] : cur.upload_types.filter((k) => k !== key) });
  return (
    <>
      <PageHeader icon="complaint" title="Uploads" subtitle="Upload limits, storage used and every document attached to a complaint." />
      {err && <p className="error" role="alert">{err}</p>}
      <div className="stat-grid">
        <div className="card stat"><span className="stat-icon" aria-hidden="true"><Icon name="complaint" size={24} /></span><div><div className="stat-num">{data?.count ?? "—"}</div><div className="stat-label">Documents stored</div></div></div>
        <div className="card stat"><span className="stat-icon" aria-hidden="true"><Icon name="chart" size={24} /></span><div><div className="stat-num">{data ? size(data.total_bytes) : "—"}</div><div className="stat-label">Space used</div></div></div>
      </div>
      {cur && (
        <form className="card" onSubmit={save} style={{ marginBottom: 16 }}>
          <PanelTitle icon="gear">Upload limits</PanelTitle>
          <div className="row">
            <SizeField key={`d${data?.limits.upload_max_kb}`} label="Largest document" hint="Per file" kb={cur.upload_max_kb} onChange={(kb) => setLim({ ...lim, upload_max_kb: kb })} minKb={50} maxKb={20480} />
            <Field label="Files per upload" required hint="1 to 10. Size times files may not exceed 40 MB."><input type="number" min={1} max={10} required value={cur.upload_max_files} onChange={(e) => setLim({ ...lim, upload_max_files: Number(e.target.value) })} /></Field>
            <SizeField key={`p${data?.limits.photo_max_kb}`} label="Largest profile photo" hint="Per photo" kb={cur.photo_max_kb} onChange={(kb) => setLim({ ...lim, photo_max_kb: kb })} minKb={50} maxKb={5120} />
          </div>
          <fieldset style={{ border: 0, padding: 0, margin: "8px 0 16px" }}>
            <legend style={{ fontWeight: 700, marginBottom: 8 }}>Kinds of document people may upload</legend>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 8 }}>
              {cur.type_catalog.map((t) => (
                <label key={t.key} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input type="checkbox" style={{ width: 18, height: 18, minHeight: 0 }} checked={cur.upload_types.includes(t.key)} onChange={(e) => toggleType(t.key, e.target.checked)} />
                  <span>{t.label} <small className="muted">.{t.extensions.join(" .")}</small></span>
                </label>
              ))}
            </div>
            <small className="muted">Profile photos are always JPG, PNG or WebP.</small>
          </fieldset>
          <Field label="Upload instructions" hint="Shown in red beside supporting document uploads on all complaint forms. Leave empty to hide." ><textarea rows={3} maxLength={2000} value={cur.upload_instructions ?? ""} onChange={(e) => setLim({ ...lim, upload_instructions: e.target.value })} /></Field>
          {msg.err && <p className="error" role="alert">{msg.err}</p>}{msg.ok && <p className="notice" role="status">{msg.ok}</p>}
          <button type="submit" className="btn"><Icon name="check" />Save upload settings</button>
        </form>
      )}
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
            {loading && <tr><td colSpan={6}><Loader size={40} /></td></tr>}
          </tbody>
        </table>
        {!loading && data?.results.length === 0 && <EmptyState icon="search">No documents match.</EmptyState>}</div>
        {data && <div className="pager"><span>{data.matches} document{data.matches === 1 ? "" : "s"}</span>
          <div><button type="submit" className="btn secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}><Icon name="left" size={16} />Previous</button>
            <button type="submit" className="btn secondary" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next<Icon name="right" size={16} /></button></div></div>}
      </section>
    </>
  );
}
