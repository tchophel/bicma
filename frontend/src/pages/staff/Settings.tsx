import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { Field, PageHeader, PanelTitle } from "../../components/ui";
import { useList } from "../../useList";

export function SettingsPage() {
  const { data, err, reload } = useList<{ reference_prefix: string; declaration_text: string; upload_max_mb: number; upload_max_files: number; photo_max_kb: number }>("/admin/settings/");
  const [prefix, setPrefix] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const value = prefix ?? data?.reference_prefix ?? "";
  const [decl, setDecl] = useState<string | null>(null);
  const declValue = decl ?? data?.declaration_text ?? "";
  const [lim, setLim] = useState<Record<string, string>>({});
  const limVal = (k: "upload_max_mb" | "upload_max_files" | "photo_max_kb") => lim[k] ?? String(data?.[k] ?? "");
  async function save(e: FormEvent) {
    e.preventDefault(); setMsg({});
    try { await api("/admin/settings/", { method: "PATCH", json: { reference_prefix: value, declaration_text: declValue, upload_max_mb: Number(limVal("upload_max_mb")), upload_max_files: Number(limVal("upload_max_files")), photo_max_kb: Number(limVal("photo_max_kb")) } }); setPrefix(null); setDecl(null); setLim({}); reload(); setMsg({ ok: "Settings saved." }); }
    catch (x) { setMsg({ err: (x as ApiError).message }); }
  }
  return (<>
    <PageHeader icon="gear" title="Settings" subtitle="System-wide configuration." />{err && <p className="error">{err}</p>}
    <form className="card" onSubmit={save} style={{ maxWidth: 720 }}>
      <PanelTitle icon="complaint">Complaint reference numbers</PanelTitle>
      <Field label="Reference prefix" required hint={`New complaints will be numbered like ${value || "BICMA-CMS"}-${new Date().getFullYear()}-000001. Existing references never change.`}>
        <input required maxLength={20} value={value} onChange={(e) => setPrefix(e.target.value.toUpperCase())} />
      </Field>
      {msg.err && <p className="error" role="alert">{msg.err}</p>}{msg.ok && <p className="notice" role="status">{msg.ok}</p>}
      <PanelTitle icon="complaint">Upload limits</PanelTitle>
      <div className="row">
        <Field label="Largest document (MB)" required hint="1 to 20 MB per file."><input type="number" min={1} max={20} required value={limVal("upload_max_mb")} onChange={(e) => setLim({ ...lim, upload_max_mb: e.target.value })} /></Field>
        <Field label="Files per upload" required hint="1 to 10 files. Size times files may not exceed 40 MB."><input type="number" min={1} max={10} required value={limVal("upload_max_files")} onChange={(e) => setLim({ ...lim, upload_max_files: e.target.value })} /></Field>
        <Field label="Largest profile photo (KB)" required hint="50 to 5120 KB (5120 KB = 5 MB)."><input type="number" min={50} max={5120} required value={limVal("photo_max_kb")} onChange={(e) => setLim({ ...lim, photo_max_kb: e.target.value })} /></Field>
      </div>
      <PanelTitle icon="edit">Complaint form declaration</PanelTitle>
      <Field label="Declaration text" required hint="Shown on the public complaint form. The complainant must accept it to submit."><textarea required rows={7} minLength={20} maxLength={3000} value={declValue} onChange={(e) => setDecl(e.target.value)} /></Field>
      <button className="btn">Save settings</button>
    </form>
    <p className="muted">Notification templates, email and SMS settings arrive with the communications phase.</p></>);
}
