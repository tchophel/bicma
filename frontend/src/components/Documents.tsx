import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { useList } from "../useList";
import type { ComplaintDetail, Meta } from "../types";
import { Icon } from "./Icon";
import { PanelTitle, humanKb } from "./ui";

/** Sidebar box on the case page: every document on the case, with an upload form for staff who may add to it. */
export function Documents({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const canUpload = c.permissions.note || c.permissions.message;
  const limits = useList<Meta>("/meta/").data?.limits;
  const [files, setFiles] = useState<File[]>([]);
  const [visibility, setVisibility] = useState("internal");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [key, setKey] = useState(0);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || !files.length) return;
    setBusy(true); setErr("");
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("visibility", visibility);
    try { await api(`/complaints/${c.id}/upload/`, { form: fd }); setFiles([]); setKey((k) => k + 1); onDone(); }
    catch (x) { setErr((x as ApiError).message); }
    finally { setBusy(false); }
  }
  return (
    <section className="card" aria-label="Documents">
      <PanelTitle icon="complaint">Documents</PanelTitle>
      {c.attachments.length === 0 && <p className="muted">No documents yet.</p>}
      <ul style={{ paddingLeft: 18, margin: "0 0 12px" }}>
        {c.attachments.map((a) => (
          <li key={a.id}><a href={`/api/complaints/${c.id}/attachments/${a.id}/`}>{a.original_name}</a>{" "}
            <small className="muted">{Math.ceil(a.size / 1024)} KB · {a.visibility === "public" ? "shared with complainant" : "internal"}</small></li>
        ))}
      </ul>
      {canUpload && (
        <form onSubmit={submit}>
          {err && <p className="error" role="alert">{err}</p>}
          <label className="field"><span>Upload documents</span>
            <input key={key} type="file" multiple accept={limits?.allowed_extensions.map((x) => `.${x}`).join(",")} onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
            <small>Up to {limits ? `${limits.upload_max_files} files of ${humanKb(limits.upload_max_kb)} each` : "the allowed number of files"}.</small></label>
          {c.permissions.message && (
            <label className="field"><span>Who can see them</span>
              <select value={visibility} onChange={(e) => setVisibility(e.target.value)}><option value="internal">Internal only</option><option value="public">Shared with the complainant</option></select></label>
          )}
          <button className="btn" disabled={busy || !files.length}><Icon name="plus" />{busy ? "Uploading…" : "Upload"}</button>
        </form>
      )}
    </section>
  );
}
