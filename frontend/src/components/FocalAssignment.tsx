import { Link } from "react-router-dom";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { useList } from "../useList";
import { useAuth } from "../auth";
import type { ComplaintDetail } from "../types";
import { Field } from "./ui";
import { Icon } from "./Icon";
import "./FocalAssignment.css";

type Focal = { id: string; name: string; division_name: string };
export function FocalAssignment({ complaint, onAssigned }: { complaint: ComplaintDetail; onAssigned: () => void }) {
  const { user } = useAuth();
  if (user?.role !== "super_admin" || !["submitted", "unassigned", "under_screening", "assigned_to_division"].includes(complaint.internal_status)) return null;
  return <AssignmentForm key={`${complaint.id}-${complaint.assigned_to}`} complaint={complaint} onAssigned={onAssigned} />;
}
function AssignmentForm({ complaint, onAssigned }: { complaint: ComplaintDetail; onAssigned: () => void }) {
  const path = `/complaints/${complaint.id}/assign-focal/`;
  const { data, err, loading, reload } = useList<Focal[]>(path);
  const [focal, setFocal] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const refresh = () => { if (document.visibilityState === "visible") reload(); };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [reload]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true); setError("");
    try { await api(path, { json: { focal } }); onAssigned(); }
    catch (x) { setError((x as ApiError).message); }
    finally { setBusy(false); }
  }
  return <form className="focal-assignment" onSubmit={submit}>
    <div className="focal-assignment-heading"><h3><Icon name="users" size={18} />Assign Divisional Focal</h3><button className="btn secondary" type="button" disabled={busy || loading} onClick={reload}><Icon name="refresh" size={15} />Refresh focals</button></div>
    <p className="muted">{complaint.division_name ? `Choose a focal from ${complaint.division_name}.` : "The complaint will use the selected focal’s division."}</p>
    {(err || error) && <p className="error" role="alert">{err || error}</p>}
    <Field label="Divisional Focal" required><select required disabled={loading || busy || !!err || !data?.length} value={focal} onChange={(e) => setFocal(e.target.value)}><option value="">{loading ? "Loading…" : err ? "Unable to load focals" : !data?.length ? "No matching Divisional Focal" : "Select Divisional Focal"}</option>{data?.map((u) => <option key={u.id} value={u.id}>{u.name} · {u.division_name}</option>)}</select></Field>
    {!loading && !err && data?.length === 0 && <p className="muted">{complaint.division_name ? `No active Divisional Focal is linked to ${complaint.division_name}.` : "No active Divisional Focal with an active division is available."} <Link to="/staff/divisions">Manage divisional focals</Link>, then refresh this list.</p>}
    <button className="btn" disabled={busy || !focal || loading || !!err || !data?.some((candidate) => candidate.id === focal)}><Icon name="users" size={16} />{busy ? "Assigning…" : "Assign focal"}</button>
  </form>;
}
