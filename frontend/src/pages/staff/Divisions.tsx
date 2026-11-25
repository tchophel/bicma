import { useConfirm } from "../../components/Confirm";
import { Icon } from "../../components/Icon";
import { IconBtn } from "../../components/IconBtn";
import { Loader } from "../../components/Loader";
import { useToast } from "../../components/Toast";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { Field, PageHeader } from "../../components/ui";
import { Modal } from "../../components/Modal";
import { type Division, type Page } from "../../types";
import { useList } from "../../useList";
import "../../styles/Directory.css";
import "../../styles/Locations.css";
import "../../styles/MasterTheme.css";
import { FocalRegistration } from "./FocalRegistration";

export function Divisions() {
  const toast = useToast();
  const ask = useConfirm();
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const { data, err, loading, reload } = useList<Page<Division>>(`/admin/divisions/?page=${page}&page_size=10&search=${encodeURIComponent(query)}`);
  const all = useList<Page<Division>>("/admin/divisions/?page_size=200");
  const [name, setName] = useState(""); const [code, setCode] = useState(""); const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [changing, setChanging] = useState<string | null>(null);
  async function add(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setMsg(""); setBusy(true);
    try {
      await api("/admin/divisions/", { json: { name: name.trim(), code: code.trim() } });
      toast.success(`${name.trim()} has been added.`); setName(""); setCode(""); reload(); all.reload(); setAdding(false);
    } catch (x) { setMsg((x as ApiError).message); }
    finally { setBusy(false); }
  }
  async function toggle(d: Division) {
    if (changing !== null) return;
    if (!await ask(d.is_active ? "Deactivate" : "Activate")) return;
    setChanging(d.id); setMsg("");
    try {
      await api(`/admin/divisions/${d.id}/`, { method: "PATCH", json: { is_active: !d.is_active } });
      toast.success(`${d.name} is now ${d.is_active ? "inactive" : "active"}.`); reload();
    } catch (x) { toast.error((x as ApiError).message); }
    finally { setChanging(null); }
  }
  return (
    <div className="locations-page divisions-page master-page">
      <PageHeader icon="division" title="Divisions" subtitle="Organisational divisions that investigate complaints.">
        <button type="button" className="btn" onClick={() => { setMsg(""); setAdding(true); }}><Icon name="plus" />Add division</button>
      </PageHeader>
      {err && <p className="error" role="alert">{err}</p>}{msg && <p className="error" role="alert">{msg}</p>}
      <FocalRegistration divisions={all.data?.results ?? []} onDone={() => { reload(); all.reload(); }} />
      <div className="locations-layout">
        <section className="card users-directory" aria-labelledby="division-directory">
          <div className="users-toolbar"><div><h2 id="division-directory">Division directory <span className="chip">{data?.count ?? "—"}</span></h2><p className="muted">Manage divisions and their availability.</p></div>
            <label className="users-search"><span className="sr-only">Search divisions</span><Icon name="search" /><input type="search" placeholder="Search name or code…" value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} /></label>
          </div>
          <div className="table-wrap"><table><thead><tr><th>Name</th><th>Code</th><th>Division Head</th><th>Status</th><th className="users-actions-cell">Actions</th></tr></thead>
            <tbody>{data?.results.map((d) => <tr key={d.id}>
              <td><div className="location-name"><span className="icon-tile"><Icon name="division" size={17} /></span><strong>{d.name}</strong></div></td>
              <td><span className="chip division-code">{d.code}</span></td>
              <td>{d.focal ? <div className="division-focal"><strong>{d.focal.name || d.focal.email}</strong>{d.focal.name && <small className="muted">{d.focal.email}</small>}</div> : <span className="badge warn">Not registered</span>}</td>
              <td><span className={`badge ${d.is_active ? "ok" : "bad"}`}><span className="status-dot" />{d.is_active ? "Active" : "Inactive"}</span></td>
              <td className="users-actions-cell"><IconBtn icon="power" tone={d.is_active ? "danger" : "ok"} disabled={changing !== null} onClick={() => toggle(d)} label={`${d.is_active ? "Deactivate" : "Activate"} ${d.name}`} /></td>
            </tr>)}
            {loading && <tr><td colSpan={5}><Loader size={40} label="Loading divisions" /></td></tr>}
            {!loading && data?.results.length === 0 && <tr><td colSpan={5} className="users-empty"><Icon name="division" size={28} /><p>{query ? "No divisions match your search." : "No divisions yet. Add one to get started."}</p></td></tr>}
            </tbody>
          </table></div>
          <div className="users-directory-footer location-pagination"><span>{data?.count ? `Showing ${(page - 1) * 10 + 1}–${(page - 1) * 10 + data.results.length} of ${data.count} divisions` : "No divisions to show"}</span>
            <nav aria-label="Division pages"><button type="submit" className="btn secondary" disabled={loading || !data?.previous} onClick={() => setPage(page - 1)}><Icon name="left" size={14} />Previous</button><span aria-live="polite">{page} / {Math.max(1, Math.ceil((data?.count ?? 0) / 10))}</span><button type="submit" className="btn secondary" disabled={loading || !data?.next} onClick={() => setPage(page + 1)}>Next<Icon name="right" size={14} /></button></nav>
          </div>
        </section>
        <aside className="locations-aside">
          <div className="location-guidance"><Icon name="help" size={21} /><div><strong>Keep division records intact</strong><p>Deactivate divisions that are no longer in use. Existing complaints retain their division details.</p></div></div>
        </aside>
      </div>
      <Modal open={adding} onClose={() => setAdding(false)} title="Add division" icon="division" busy={busy}>
        {msg && <p className="error" role="alert">{msg}</p>}
        <form onSubmit={add} aria-busy={busy}>
              <Field label="Division name" required><input required maxLength={120} placeholder="Enter division name" disabled={busy} value={name} onChange={(e) => setName(e.target.value)} /></Field>
              <Field label="Code" required hint="A unique short code, e.g. TEL."><input required maxLength={20} placeholder="e.g. TEL" disabled={busy} value={code} onChange={(e) => setCode(e.target.value)} /></Field>
              <button type="submit" className="btn" disabled={busy || !name.trim() || !code.trim()}><Icon name="plus" />{busy ? "Adding…" : "Add division"}</button>
            </form>
      </Modal>
    </div>
  );
}
