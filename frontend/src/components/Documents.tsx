import { useState, type FormEvent } from "react";
import { useToast } from "./Toast";
import { ApiError, uploadWithProgress } from "../api";
import { useList } from "../useList";
import type { ComplaintDetail, Meta } from "../types";
import { Icon } from "./Icon";
import { FileLink } from "./FileLink";
import { ScanBadge, useFileScan } from "./FileScan";
import { PanelTitle, humanKb } from "./ui";

/** Upload form for staff who may add documents to the case. Used in the Assignment tab, and in the sidebar for people without that tab. */
export function UploadDocuments({ c, onDone, heading = false }: { c: ComplaintDetail; onDone: () => void; heading?: boolean }) {
  const toast = useToast();
  const canUpload = c.permissions.note || c.permissions.message;
  const limits = useList<Meta>("/meta/").data?.limits;
  const [files, setFiles] = useState<File[]>([]);
  const [visibility, setVisibility] = useState("internal");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [key, setKey] = useState(0);
  const [percent, setPercent] = useState(0);
  const [done, setDone] = useState<{ at: string; names: string[] } | null>(null);
  const scan = useFileScan(files);  // each chosen file is checked for viruses and harmful content straight away

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || !files.length || scan.blocked || scan.scanning) return;
    setBusy(true); setErr(""); setDone(null); setPercent(0);
    const names = files.map((f) => f.name);
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("visibility", visibility);
    try {
      await uploadWithProgress(`/complaints/${c.id}/upload/`, fd, setPercent);
      setPercent(100); setFiles([]); setKey((k) => k + 1); onDone();
      setDone({ at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }), names });
      toast.success(`${names.length === 1 ? "Document" : `${names.length} documents`} uploaded.`);
      setTimeout(() => setDone(null), 12000);
    } catch (x) { setErr((x as ApiError).message); toast.error((x as ApiError).message); }
    finally { setBusy(false); }
  }
  if (!canUpload) return null;
  return (
    <form className={heading ? "case-routing-form" : undefined} aria-label="Upload documents" onSubmit={submit}>
      {heading && <div className="case-routing-heading"><span className="icon-tile"><Icon name="plus" size={20} /></span><div><h3>Upload documents</h3><p>Add files to this complaint. Choose who can see them.</p></div></div>}
      {err && <p className="error" role="alert">{err}</p>}
      <label className="field"><span>Upload documents</span>
        <input key={key} type="file" multiple accept={limits?.allowed_extensions.map((x) => `.${x}`).join(",")} onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
        <small>Up to {limits ? `${limits.upload_max_files} files of ${humanKb(limits.upload_max_kb)} each` : "the allowed number of files"}.</small></label>
      {c.permissions.message && (
        <label className="field"><span>Who can see them</span>
          <select value={visibility} onChange={(e) => setVisibility(e.target.value)}><option value="internal">Internal only</option><option value="public">Shared with the complainant</option></select></label>
      )}
      {files.length > 0 && (
        <ul className="upload-picked" aria-label="Files to upload">
          {files.map((f, i) => <li key={`${f.name}-${i}`}><strong>{f.name}</strong><small>{Math.ceil(f.size / 1024)} KB</small><ScanBadge scan={scan.of(f)} /></li>)}
        </ul>
      )}
      <button type="submit" className={`btn upload-btn${busy ? " uploading" : ""}${done ? " completed" : ""}`} style={{ ["--pct" as string]: `${percent}%` }}
        disabled={busy || !files.length || scan.blocked || scan.scanning}>
        <Icon name={done ? "check" : "plus"} />
        {busy ? (percent < 100 ? `Uploading… ${percent}%` : "Finishing…") : scan.blocked ? "Remove the blocked file" : scan.scanning && files.length ? "Scanning…" : "Upload"}
      </button>
      {busy && <div className="upload-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label="Upload progress"><span style={{ width: `${percent}%` }} /></div>}
      {done && <p className="upload-done" role="status"><Icon name="check" size={16} /><span><strong>Upload complete</strong> at {done.at}. {done.names.join(", ")}</span></p>}
    </form>
  );
}

/** Sidebar box on the case page: every document on the case. */
export function Documents({ c, onDone }: { c: ComplaintDetail; onDone: () => void }) {
  const p = c.permissions;
  const hasAssignmentTab = p.triage || p.assign || p.refer || p.not_in_mandate;  // where the upload form lives for those users
  return (
    <section className="card" aria-label="Documents">
      <PanelTitle icon="complaint">Documents</PanelTitle>
      {c.attachments.length === 0 && <p className="muted">No documents yet.</p>}
      <ul className="doc-list">
        {c.attachments.map((a) => {
          const shared = a.visibility === "public";
          const kind = a.original_name.split(".").pop()?.toUpperCase() ?? "";
          return (
            <li key={a.id} className="doc-card">
              <span className="doc-icon" aria-hidden="true"><Icon name="complaint" size={22} /><b>{kind.slice(0, 4)}</b></span>
              <div className="doc-body">
                <FileLink href={`/api/complaints/${c.id}/attachments/${a.id}/`} name={a.original_name} />
                {a.slot_label && <div className="doc-type">{a.slot_label}</div>}
                <div className="doc-meta">
                  <span className="chip plain">{a.size >= 1048576 ? `${(a.size / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.ceil(a.size / 1024))} KB`}</span>
                  <span className={`doc-vis ${shared ? "shared" : "internal"}`}><Icon name={shared ? "users" : "lock"} size={13} />{shared ? "Shared with complainant" : "Internal only"}</span>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
      {!hasAssignmentTab && <UploadDocuments c={c} onDone={onDone} />}
    </section>
  );
}
