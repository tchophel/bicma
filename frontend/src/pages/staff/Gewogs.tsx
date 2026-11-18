import { Icon } from "../../components/Icon";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../api";
import { Field, PageHeader } from "../../components/ui";
import { Modal } from "../../components/Modal";
import { type DzongkhagRow, type GewogRow, type Page } from "../../types";
import { useList } from "../../useList";
import "./Directory.css";
import "./Locations.css";
import "./Gewogs.css";

export function Gewogs() {
  const [sp, setSp] = useSearchParams();
  const dz = sp.get("dzongkhag") ?? "";
  const dzs = useList<Page<DzongkhagRow>>("/admin/dzongkhags/?page_size=100");
  const { data, err, loading, reload } = useList<Page<GewogRow>>(`/admin/gewogs/?page_size=200${dz ? `&dzongkhag=${dz}` : ""}`);
  const [bulk, setBulk] = useState(""); const [msg, setMsg] = useState(""); const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const run = async (fn: () => Promise<void>) => { if (busy) return; setBusy(true); setMsg(""); setOk(""); try { await fn(); reload(); dzs.reload(); } catch (x) { setMsg((x as ApiError).message); } finally { setBusy(false); } };
  const rows = (data?.results ?? []).filter((g) => `${g.name} ${g.dzongkhag_name}`.toLowerCase().includes(query.toLowerCase()));
  const totalPages = Math.max(1, Math.ceil(rows.length / 10));
  const currentPage = Math.min(page, totalPages);
  const pageRows = rows.slice((currentPage - 1) * 10, currentPage * 10);
  return (<div className="locations-page gewogs-page">
    <PageHeader icon="pin" title="Gewogs" subtitle="Each Gewog belongs to one Dzongkhag. The complaint form lists only the Gewogs of the chosen Dzongkhag.">
      <button type="button" className="btn" onClick={() => { setMsg(""); setAdding(true); }}><Icon name="plus" />Add Gewogs</button>
    </PageHeader>
    {err && <p className="error">{err}</p>}{msg && <p className="error" role="alert">{msg}</p>}{ok && <p className="users-success" role="status"><Icon name="check" />{ok}</p>}
    {dzs.err && <p className="error" role="alert">Could not load Dzongkhags. Refresh to try again.</p>}
    <section className="card users-directory" aria-labelledby="gewog-directory">
    <div className="users-toolbar"><div><h2 id="gewog-directory">Gewog directory <span className="chip">{data?.count ?? "—"}</span></h2><p className="muted">Browse locations or choose a Dzongkhag to narrow the list.</p></div></div>
    <div className="gewog-filter-bar"><label><span>Dzongkhag</span>
      <select value={dz} onChange={(e) => { setSp(e.target.value ? { dzongkhag: e.target.value } : {}); setPage(1); }}>
        <option value="">All</option>{dzs.data?.results.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.gewog_count})</option>)}
      </select></label>
      <label className="users-search"><span className="sr-only">Search loaded Gewogs</span><Icon name="search" /><input type="search" placeholder="Search Gewogs…" value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} /></label>
    </div>
    <div className="table-wrap"><table><thead><tr><th>Gewog</th><th>Dzongkhag</th><th>Status</th><th className="users-actions-cell">Actions</th></tr></thead>
      <tbody>{pageRows.map((g) => <tr key={g.id}><td><div className="location-name"><span className="icon-tile"><Icon name="pin" size={16} /></span><strong>{g.name}</strong></div></td><td><span className="chip">{g.dzongkhag_name}</span></td>
        <td>{g.is_active ? <span className="badge ok"><span className="status-dot" />Active</span> : <span className="badge bad"><span className="status-dot" />Inactive</span>}</td>
        <td className="users-actions-cell"><button disabled={busy} className="btn secondary" onClick={() => run(async () => { await api(`/admin/gewogs/${g.id}/`, { method: "PATCH", json: { is_active: !g.is_active } }); })}><Icon name="power" size={14} />{g.is_active ? "Deactivate" : "Activate"}</button></td></tr>)}
        {loading && <tr><td colSpan={4} className="users-empty">Loading Gewogs…</td></tr>}
        {!loading && rows.length === 0 && <tr><td colSpan={4} className="users-empty"><span className="icon-tile lg"><Icon name="pin" size={26} /></span><h3>{query ? "No matching Gewogs" : "No Gewogs yet"}</h3><p>{query ? "Try a different search." : "Use the form above to add Gewogs to this Dzongkhag."}</p></td></tr>}</tbody></table></div>
    <div className="users-directory-footer location-pagination"><span>{rows.length ? `Showing ${(currentPage - 1) * 10 + 1}–${Math.min(currentPage * 10, rows.length)} of ${rows.length} Gewogs` : "No Gewogs to show"}</span><nav aria-label="Gewog pages"><button className="btn secondary" disabled={loading || currentPage === 1} onClick={() => setPage(currentPage - 1)}><Icon name="left" size={14} />Previous</button><span aria-live="polite">{currentPage} / {totalPages}</span><button className="btn secondary" disabled={loading || currentPage === totalPages} onClick={() => setPage(currentPage + 1)}>Next<Icon name="right" size={14} /></button></nav></div>
    </section>
    <Modal open={adding} onClose={() => setAdding(false)} title="Add Gewogs" icon="pin" busy={busy}>
      <form className="gewog-create" onSubmit={(e) => { e.preventDefault(); run(async () => {
        const r = await api<{ created: number; skipped: number }>("/admin/gewogs/bulk/", { json: { dzongkhag: dz, names: bulk.split("\n") } });
        setBulk(""); setAdding(false); setOk(`Added ${r.created} Gewog(s); skipped ${r.skipped} already listed.`); }); }}>
        <p className="gewog-form-intro">Paste several names to update your location list in one step.</p><fieldset disabled={busy}>
        <Field label="Dzongkhag" required><select required value={dz} onChange={(e) => setSp({ dzongkhag: e.target.value })}><option value="">Select a Dzongkhag</option>{dzs.data?.results.filter((d) => d.is_active).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
        <Field label="Gewog names" required hint="Paste a list, one name per line. Names already listed are skipped."><textarea required placeholder={"First Gewog name\nSecond Gewog name\nThird Gewog name"} rows={6} value={bulk} onChange={(e) => setBulk(e.target.value)} /></Field>
        </fieldset><div className="gewog-form-footer"><button className="btn" disabled={busy || !bulk.trim() || !dz}><Icon name="plus" />{busy ? "Saving…" : "Add all"}</button></div>
      </form>
    </Modal>
    </div>);
}
