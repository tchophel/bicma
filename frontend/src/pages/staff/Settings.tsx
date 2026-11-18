import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { Field, PageHeader, PanelTitle } from "../../components/ui";
import { useList } from "../../useList";

export function SettingsPage() {
  const { data, err, reload } = useList<{ reference_prefix: string; declaration_text: string}>("/admin/settings/");
  const [prefix, setPrefix] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const value = prefix ?? data?.reference_prefix ?? "";
  const [decl, setDecl] = useState<string | null>(null);
  const declValue = decl ?? data?.declaration_text ?? "";
  async function save(e: FormEvent) {
    e.preventDefault(); setMsg({});
    try { await api("/admin/settings/", { method: "PATCH", json: { reference_prefix: value, declaration_text: declValue } }); setPrefix(null); setDecl(null); reload(); setMsg({ ok: "Settings saved." }); }
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
      <PanelTitle icon="edit">Complaint form declaration</PanelTitle>
      <Field label="Declaration text" required hint="Shown on the public complaint form. The complainant must accept it to submit."><textarea required rows={7} minLength={20} maxLength={3000} value={declValue} onChange={(e) => setDecl(e.target.value)} /></Field>
      <button className="btn">Save settings</button>
    </form>
    <p className="muted">Notification templates, email and SMS settings arrive with the communications phase.</p></>);
}
