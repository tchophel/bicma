import { Icon } from "../../components/Icon";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../api";
import { Field, PageHeader } from "../../components/ui";
import { Modal } from "../../components/Modal";
import { type DzongkhagRow, type Page } from "../../types";
import { useList } from "../../useList";
import "./Directory.css";
import "./Locations.css";

export function Dzongkhags() {
  const { data, err, loading, reload } = useList<Page<DzongkhagRow>>("/admin/dzongkhags/?page_size=100");
  const [name, setName] = useState("");
  const [msg, setMsg] = useState("");
  const [success, setSuccess] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [changing, setChanging] = useState<string | null>(null);
  async function add(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setMsg(""); setSuccess(""); setBusy(true);
    try {
      await api("/admin/dzongkhags/", { json: { name: name.trim() } });
      setSuccess(`${name.trim()} has been added.`); setName(""); reload();
    } catch (x) { setMsg((x as ApiError).message); }
    finally { setBusy(false); }
  }
  async function toggle(d: DzongkhagRow) {
    if (changing !== null) return;
    setChanging(d.id); setMsg(""); setSuccess("");
    try {
      await api(`/admin/dzongkhags/${d.id}/`, { method: "PATCH", json: { is_active: !d.is_active } });
      setSuccess(`${d.name} is now ${d.is_active ? "inactive" : "active"}.`); reload();
    } catch (x) { setMsg((x as ApiError).message); }
    finally { setChanging(null); }
  }
  const rows = data?.results ?? [];
  const visible = rows.filter((d) => d.name.toLowerCase().includes(query.toLowerCase()));
  const pageSize = 10;
  const totalPages = Math.max(1, Math.ceil(visible.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageRows = visible.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  return (
    <div className="locations-page">
      <PageHeader icon="map" title="Dzongkhags" subtitle="Manage the locations available on complaint forms.">
        <button type="button" className="btn" onClick={() => { setMsg(""); setAdding(true); }}><Icon name="plus" />Add Dzongkhag</button>
      </PageHeader>
      {err && <p className="error" role="alert">{err}</p>}
      {msg && <p className="error" role="alert">{msg}</p>}
      {success && <p className="users-success" role="status"><Icon name="check" />{success}</p>}
      <div className="locations-layout">
        <section className="card users-directory" aria-labelledby="dzongkhag-directory">
          <div className="users-toolbar">
            <div><h2 id="dzongkhag-directory">Dzongkhag directory <span className="chip">{data?.count ?? "—"}</span></h2><p className="muted">Select a Gewog count to manage its locations.</p></div>
            <label className="users-search"><span className="sr-only">Search loaded Dzongkhags</span><Icon name="search" /><input type="search" placeholder="Search Dzongkhags…" value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} /></label>
          </div>
          <div className="table-wrap"><table>
            <thead><tr><th>Dzongkhag</th><th>Gewogs</th><th>Status</th><th className="users-actions-cell">Actions</th></tr></thead>
            <tbody>{pageRows.map((d) => <tr key={d.id}>
              <td><div className="location-name"><span className="icon-tile"><Icon name="pin" size={17} /></span><strong>{d.name}</strong></div></td>
              <td><Link className="gewog-count" to={`/staff/gewogs?dzongkhag=${d.id}`} aria-label={`Manage ${d.gewog_count} Gewogs in ${d.name}`}><Icon name="map" size={15} />{d.gewog_count}<Icon name="right" size={14} /></Link></td>
              <td><span className={`badge ${d.is_active ? "ok" : "bad"}`}><span className="status-dot" />{d.is_active ? "Active" : "Inactive"}</span></td>
              <td className="users-actions-cell"><button className="btn secondary" disabled={changing !== null} onClick={() => toggle(d)} aria-label={`${d.is_active ? "Deactivate" : "Activate"} ${d.name}`}><Icon name="power" />{changing === d.id ? "Updating…" : d.is_active ? "Deactivate" : "Activate"}</button></td>
            </tr>)}
            {loading && <tr><td colSpan={4} className="users-empty">Loading Dzongkhags…</td></tr>}
            {!loading && visible.length === 0 && <tr><td colSpan={4} className="users-empty"><Icon name="map" size={28} /><p>{query ? "No Dzongkhags match your search." : "No Dzongkhags yet. Add one to get started."}</p></td></tr>}
            </tbody>
          </table></div>
          <div className="users-directory-footer location-pagination">
            <span>{visible.length ? `Showing ${(currentPage - 1) * pageSize + 1}–${Math.min(currentPage * pageSize, visible.length)} of ${visible.length} Dzongkhags` : "No Dzongkhags to show"}</span>
            <nav aria-label="Dzongkhag pages">
              <button type="button" className="btn secondary" disabled={currentPage === 1 || loading} onClick={() => setPage(currentPage - 1)}><Icon name="left" size={14} />Previous</button>
              <span aria-live="polite">{currentPage} / {totalPages}</span>
              <button type="button" className="btn secondary" disabled={currentPage === totalPages || loading} onClick={() => setPage(currentPage + 1)}>Next<Icon name="right" size={14} /></button>
            </nav>
          </div>
        </section>
        <aside className="locations-aside">
          <div className="location-guidance"><Icon name="help" size={21} /><div><strong>Keep location records intact</strong><p>Deactivate a Dzongkhag instead of deleting it. Existing complaints keep their location, while inactive entries are hidden from new complaint forms.</p></div></div>
        </aside>
      </div>
      <Modal open={adding} onClose={() => setAdding(false)} title="Add Dzongkhag" icon="map" busy={busy}>
        {msg && <p className="error" role="alert">{msg}</p>}
        <form onSubmit={add} aria-busy={busy}>
              <Field label="Dzongkhag name" required><input required maxLength={80} placeholder="Enter Dzongkhag name" value={name} onChange={(e) => setName(e.target.value)} disabled={busy} /></Field>
              <button className="btn" disabled={busy || !name.trim()}><Icon name="plus" />{busy ? "Adding…" : "Add Dzongkhag"}</button>
            </form>
      </Modal>
    </div>
  );
}
