import { Icon } from "./Icon";
import { useState } from "react";
import { api, ApiError } from "../api";
import { useList } from "../useList";
import { useToast } from "./Toast";
import { fmt } from "./ui";

type Storage = {
  checked_at: string;
  disk: { total: number; used: number; free: number; used_pct: number };
  database: { bytes: number; tables: { table: string; bytes: number; rows: number }[] };
  files: { bytes: number; count: number; folders: { name: string; bytes: number; files: number }[]; kinds: { type: string; bytes: number; files: number }[];
    biggest: { id: string; name: string; bytes: number; reference: string; visibility: string; added: string }[] };
  tips: string[];
  compress: { enabled: boolean; waiting: { files: number; bytes: number }; saved: { files: number; bytes: number } };
};

function human(n: number) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${i ? n.toFixed(1) : n.toFixed(0)} ${units[i]}`;
}

/** Settings > Storage: disk use, what takes the most space, and a PDF of it. */
export function StoragePanel() {
  const { data, err, loading, reload } = useList<Storage>("/admin/storage/");
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  async function compress(body: { enabled?: boolean; run?: boolean }) {
    if (body.run && data?.compress.waiting.files === 0) { toast.success("Nothing to shrink: no resolved or closed complaint has pictures waiting."); return; }
    if (body.run && !window.confirm("This shrinks the pictures attached to resolved and closed complaints. The original pictures are replaced by smaller copies and cannot be restored. Documents and PDFs are not changed. Continue?")) return;
    setBusy(true);
    try {
      const r = await api<{ result: { shrunk: number; bytes_saved: number } | null }>("/admin/storage/", { method: "POST", json: body });
      if (r.result) toast.success(`Shrunk ${r.result.shrunk} pictures, saved ${human(r.result.bytes_saved)}.`);
      reload();
    } catch (e) { toast.error((e as ApiError).message); }
    finally { setBusy(false); }
  }
  const pct = data?.disk.used_pct ?? 0;
  const tone = pct >= 85 ? "bad" : pct >= 70 ? "warn" : "ok";
  const maxFolder = Math.max(1, ...(data?.files.folders.map((f) => f.bytes) ?? [1]));
  return (
    <section className="card settings-section" aria-labelledby="settings-storage">
      <header className="settings-section-header"><span className="icon-tile"><Icon name="category" size={22} /></span>
        <div><span className="settings-eyebrow">SYSTEM</span><h2 id="settings-storage">Storage</h2>
          <p>How much space the system uses, what takes the most, and what to do about it.</p></div></header>
      <div className="scan-bar">
        <button type="button" className="btn secondary" onClick={reload} disabled={loading}><Icon name="refresh" />{loading ? "Measuring…" : "Measure again"}</button>
        <a className="btn" href="/api/admin/storage-report/" download><Icon name="send" />Download PDF</a>
        {data && <span className="muted">Measured {fmt(data.checked_at)}</span>}
      </div>
      {err && <p className="error" role="alert">{err}</p>}
      {data && <>
        <div className="storage-disk" role="img" aria-label={`Disk ${pct}% full`}>
          <div className={`storage-disk-bar ${tone}`} style={{ width: `${pct}%` }} />
        </div>
        <p><strong>{pct}% of the disk is used.</strong> {human(data.disk.used)} used of {human(data.disk.total)}, {human(data.disk.free)} free.</p>
        <div className="storage-cards">
          <div className="scan-card"><strong>Database</strong><p>{human(data.database.bytes)}</p><small className="muted">Complaints, users, logs</small></div>
          <div className="scan-card"><strong>Uploaded documents</strong><p>{human(data.files.bytes)}</p><small className="muted">{data.files.count} files</small></div>
        </div>
        <div className="scan-plan"><h3>Shrink pictures of resolved complaints</h3>
          <p className="muted">Once a complaint is resolved or closed, its attached pictures (JPEG, PNG, WebP) are made smaller: scaled down to at most 2560 pixels and saved at a lower quality. PDFs and other documents are not touched. The original picture is replaced and cannot be restored.</p>
          <p>Saved so far: <strong>{human(data.compress.saved.bytes)}</strong> in {data.compress.saved.files} pictures. Waiting: {data.compress.waiting.files} pictures ({human(data.compress.waiting.bytes)}).</p>
          <label className="check"><input type="checkbox" checked={data.compress.enabled} disabled={busy} onChange={(e) => void compress({ enabled: e.target.checked })} /> Shrink automatically every day</label>
          <div className="scan-card-actions"><button type="button" className="btn" disabled={busy} onClick={() => void compress({ run: true })}><Icon name="refresh" />{busy ? "Working…" : "Shrink resolved complaint pictures now"}</button></div></div>
        <div className="scan-plan"><h3>What to do</h3><ul>{data.tips.map((t) => <li key={t}>{t}</li>)}</ul></div>
        <h3>Uploaded documents by folder</h3>
        <div className="storage-rows">{data.files.folders.map((f) => (
          <div key={f.name} className="storage-row"><span>{f.name} <small className="muted">{f.files} files</small></span>
            <span className="storage-meter"><i style={{ width: `${Math.max(2, (f.bytes / maxFolder) * 100)}%` }} /></span><strong>{human(f.bytes)}</strong></div>))}</div>
        <h3>Largest documents</h3>
        {data.files.biggest.length === 0 ? <p className="muted">No uploaded complaint documents yet.</p> :
          <div className="table-wrap"><table><thead><tr><th>Document</th><th>Complaint</th><th>Size</th><th>Added</th></tr></thead>
            <tbody>{data.files.biggest.map((b) => (<tr key={b.id}><td>{b.name}<small className="muted cell-sub">{b.visibility}</small></td><td>{b.reference}</td><td>{human(b.bytes)}</td><td>{fmt(b.added)}</td></tr>))}</tbody></table></div>}
        <h3>Largest database tables</h3>
        <div className="table-wrap"><table><thead><tr><th>Table</th><th>Rows</th><th>Size</th></tr></thead>
          <tbody>{data.database.tables.map((t) => (<tr key={t.table}><td><code>{t.table}</code></td><td>{t.rows}</td><td>{human(t.bytes)}</td></tr>))}</tbody></table></div>
      </>}
    </section>
  );
}
