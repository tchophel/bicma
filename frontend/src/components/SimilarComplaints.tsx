import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { useList } from "../useList";
import type { ComplaintDetail } from "../types";
import { Icon } from "./Icon";
import { useToast } from "./Toast";

type Item = { id: string; reference: string; subject: string; status: string; officer: string | null; why: string[]; linked: boolean; has_resolution: boolean };

/** BICMA-2026-1-9350 -> 9350 */
const num = (ref: string) => ref.split("-").pop() ?? ref;
const key = (id: string) => `similar-no:${id}`;
const asked = (id: string) => { try { return localStorage.getItem(key(id)) === "1"; } catch { return false; } };

/** Tells the officer when another open case in the division looks like this one. Yes: handle them together
 *  (and reuse the findings of the one already worked). No: carry on with this case alone. */
export function SimilarComplaints({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const { data, reload } = useList<{ items: Item[]; total?: number; days?: number }>(`/complaints/${c.id}/similar/`);
  const [no, setNo] = useState(asked(c.id));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const toast = useToast();
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const banner = total > 0 && (
    <section className={`card similar-total ${total >= 10 ? "many" : ""}`} aria-label="Same issue reported by others">
      <h3><Icon name={total >= 10 ? "alert" : "users"} size={18} /> {total >= 10 ? `Widespread issue: ${total} other people reported the same problem` : `${total} other ${total === 1 ? "person" : "people"} reported the same problem`}</h3>
      <p className="muted">Same category and provider in the last {data?.days ?? 90} days, across all divisions.{total >= 10 ? " Consider handling these together or raising it with the supervisor." : ""}</p>
    </section>
  );
  if (!items.length) return banner || null;
  const unlinked = items.filter((i) => !i.linked);
  if (no && unlinked.length === items.length) return banner || null;

  const link = async (i: Item, reuse: boolean) => {
    setBusy(true); setErr("");
    try {
      await api(`/complaints/${c.id}/link-similar/`, { method: "POST", json: { id: i.id, reuse } });
      toast.success(reuse ? `Findings from ${i.reference} copied. Check them and submit.` : `Linked with ${i.reference}.`);
      reload(); onDone();
    } catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  };
  const dismiss = () => { try { localStorage.setItem(key(c.id), "1"); } catch { /* private window */ } setNo(true); };

  return (
    <>
    {banner}
    <section className="card similar-box" aria-label="Similar complaints">
      <h3><Icon name="refresh" size={18} /> {items.length === 1 ? "There is a similar complaint" : `There are ${items.length} similar complaints`} in this division</h3>
      <p className="muted">Do you want to handle {items.length === 1 ? "it" : "them"} together with this one? If yes, the answer can be reused and resolved sooner. If not, carry on with this complaint as it is.</p>
      <ul className="similar-list">
        {items.map((i) => (
          <li key={i.id}>
            <div><Link to={`/staff/complaints/${i.id}`}><strong title={i.reference}>{num(i.reference)}</strong></Link> · {i.status}{i.officer ? ` · ${i.officer}` : ""}
              <div>{i.subject}</div><small className="muted">{i.why.join(", ")}</small></div>
            {i.linked ? <span className="badge ok">Linked</span> : <button type="button" className="btn" disabled={busy} onClick={() => link(i, false)}>Yes, handle together</button>}
            {i.linked && i.has_resolution && c.permissions.save_findings && <button type="button" className="btn secondary" disabled={busy} onClick={() => link(i, true)}>Reuse its findings</button>}
          </li>
        ))}
      </ul>
      {err && <p className="error" role="alert">{err}</p>}
      {!no && <button type="button" className="btn secondary" onClick={dismiss}>No, continue on its own</button>}
    </section>
    </>
  );
}
