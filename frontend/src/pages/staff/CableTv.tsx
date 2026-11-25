import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { Icon } from "../../components/Icon";
import { IconBtn } from "../../components/IconBtn";
import { Loader } from "../../components/Loader";
import { useConfirm } from "../../components/Confirm";
import { useToast } from "../../components/Toast";
import { PageHeader } from "../../components/ui";
import type { Page } from "../../types";
import { useList } from "../../useList";
import "../../styles/Users.css";
import "../../styles/CableTv.css";

const CABLE = "Cable TV operator";
type Named = { id: string; name: string };
type Prov = { id: string; name: string; provider_type: string | null; dzongkhags: string[]; is_active: boolean };

/** Master data: pick a Dzongkhag and keep the list of cable TV operators there.
 *  The complaint form offers exactly these names for the Dzongkhag the complainant chooses. */
export function CableTv() {
  const toast = useToast();
  const ask = useConfirm();
  const dz = useList<Page<Named>>("/admin/dzongkhags/?page_size=100");
  const types = useList<Page<Named>>("/admin/provider-types/?page_size=200");
  const provs = useList<Page<Prov>>("/admin/providers/?page_size=500");
  const [sel, setSel] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!dz.data || !types.data || !provs.data) return dz.err || types.err || provs.err ? <p className="error" role="alert">{dz.err || types.err || provs.err}</p> : <Loader />;

  const dzId = sel || dz.data.results[0]?.id || "";
  const typeId = types.data.results.find((t) => t.name === CABLE)?.id;
  const chosen = dz.data.results.find((d) => d.id === dzId);
  const cable = provs.data.results.filter((p) => typeId && p.provider_type === typeId);
  const here = cable.filter((p) => p.dzongkhags.includes(dzId));
  const fail = (e: unknown) => { setErr((e as ApiError).message); };

  async function add(e: FormEvent) {
    e.preventDefault();
    const n = name.trim();
    if (!n || !chosen || !typeId || busy) return;
    setBusy(true); setErr("");
    try {
      const same = cable.find((p) => p.name.toLowerCase() === n.toLowerCase());  // already a cable operator elsewhere: add this Dzongkhag to it
      if (same) await api(`/admin/providers/${same.id}/`, { method: "PATCH", json: { dzongkhags: [...new Set([...same.dzongkhags, dzId])], is_active: true } });
      else await api("/admin/providers/", { json: { name: n, provider_type: typeId, dzongkhags: [dzId] } });
      toast.success(`${n} added to ${chosen.name}.`); setName(""); provs.reload();
    } catch (x) { fail(x); } finally { setBusy(false); }
  }
  async function remove(p: Prov) {
    if (!await ask(`Remove ${p.name} from ${chosen?.name}`)) return;
    setBusy(true); setErr("");
    try {
      await api(`/admin/providers/${p.id}/`, { method: "PATCH", json: { dzongkhags: p.dzongkhags.filter((x) => x !== dzId) } });
      toast.success("Removed."); provs.reload();
    } catch (x) { fail(x); } finally { setBusy(false); }
  }

  const countFor = (id: string) => cable.filter((p) => p.dzongkhags.includes(id)).length;
  return (
    <div className="users-page">
      <PageHeader icon="map" title="Cable TV by Dzongkhag" subtitle="Each Dzongkhag has its own cable TV operators. Choose a Dzongkhag, then add or remove the names people can pick on the complaint form." />
      {!typeId && <p className="error" role="alert">The provider type “{CABLE}” is missing. Add it under Provider types first.</p>}
      <div className="cable-layout">
        <nav className="card cable-dz" aria-label="Dzongkhags">
          <h2>Dzongkhags</h2>
          <ul>
            {dz.data.results.map((d) => {
              const n = countFor(d.id);
              return (
                <li key={d.id}><button type="button" aria-current={d.id === dzId ? "true" : undefined} onClick={() => { setSel(d.id); setErr(""); setName(""); }}>
                  <span>{d.name}</span><span className={`cable-count${n ? " has" : ""}`}>{n}</span>
                </button></li>
              );
            })}
          </ul>
        </nav>
        <section className="card cable-panel" aria-live="polite">
          {chosen && <>
            <header>
              <span className="icon-tile"><Icon name="map" size={22} /></span>
              <div><h2>{chosen.name}</h2><p className="muted">{here.length === 0 ? "No cable TV operator yet" : `${here.length} cable TV ${here.length === 1 ? "operator" : "operators"}`}</p></div>
            </header>
            {here.length === 0 ? (
              <div className="cable-empty"><Icon name="search" size={26} /><strong>Nothing here yet</strong><span>Add the first cable TV name for {chosen.name} below.</span></div>
            ) : (
              <ul className="cable-ops">{here.map((p) => (
                <li key={p.id}><span className="cable-avatar" aria-hidden="true">{p.name.trim().charAt(0).toUpperCase()}</span>
                  <strong>{p.name}</strong>{!p.is_active && <span className="badge bad">Inactive</span>}
                  <IconBtn icon="close" tone="danger" label={`Remove ${p.name} from ${chosen.name}`} onClick={() => remove(p)} /></li>
              ))}</ul>
            )}
            <form className="cable-add" onSubmit={add}>
              <label htmlFor="cable-name">Add a cable TV name for {chosen.name}</label>
              <div>
                <input id="cable-name" maxLength={150} value={name} onChange={(e) => setName(e.target.value)} placeholder="Name of the cable TV operator" />
                <button className="btn" disabled={busy || !name.trim() || !typeId}><Icon name="plus" />Add</button>
              </div>
              {err && <p className="error" role="alert">{err}</p>}
            </form>
          </>}
        </section>
      </div>
    </div>
  );
}
