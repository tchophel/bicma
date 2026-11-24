import { useState, type FormEvent } from "react";
import { useToast } from "../../components/Toast";
import { api, ApiError } from "../../api";
import { Field, PageHeader } from "../../components/ui";
import { Icon } from "../../components/Icon";
import { useList } from "../../useList";
import "../../styles/Settings.css";

type Settings = { reference_length: number; declaration_text: string; reality_shows: string };

export function SettingsPage() {
  const toast = useToast();
  const { data, err, loading, reload } = useList<Settings>("/admin/settings/");
  const [saved, setSaved] = useState<Settings | null>(null);
  const current = saved ?? data;
  const [len, setLen] = useState<string | null>(null);
  const [decl, setDecl] = useState<string | null>(null);
  const [shows, setShows] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [success, setSuccess] = useState(false);
  const value = len ?? String(current?.reference_length ?? 4);
  const declValue = decl ?? current?.declaration_text ?? "";
  const showsValue = shows ?? current?.reality_shows ?? "";
  const dirty = !!current && (Number(value) !== current.reference_length || declValue !== current.declaration_text || showsValue !== current.reality_shows);
  const digits = Math.max(3, Math.min(10, Number(value) || 4));
  const sample = `BICMA-${new Date().getFullYear()}-3-${"9".padStart(digits, "0")}`;
  function reset() { setLen(null); setDecl(null); setShows(null); setError(null); setSuccess(false); }
  async function save(e: FormEvent) {
    e.preventDefault();
    if (busy || !current) return;
    setBusy(true); setError(null); setSuccess(false);
    try {
      const result = await api<Settings>("/admin/settings/", { method: "PATCH", json: { reference_length: Number(value), declaration_text: declValue, reality_shows: showsValue } });
      setSaved(result); setLen(null); setDecl(null); setShows(null); setSuccess(true); reload(); toast.success("Settings saved.");
    } catch (x) { setError(x as ApiError); toast.error((x as ApiError).message); }
    finally { setBusy(false); }
  }
  return (
    <div className="settings-page">
      <PageHeader icon="gear" title="Settings" subtitle="Manage complaint references and the declaration shown to complainants." />
      {err && <p className="error" role="alert">{err}</p>}
      {loading && !current && <p role="status" className="muted">Loading settings…</p>}
      <form onSubmit={save} aria-busy={busy}>
        <fieldset disabled={busy || !current} className="settings-fields">
          <section className="card settings-section" aria-labelledby="settings-references">
            <header className="settings-section-header"><span className="icon-tile"><Icon name="complaint" size={22} /></span><div><span className="settings-eyebrow">COMPLAINT IDENTIFICATION</span><h2 id="settings-references">Reference numbers</h2><p>Each new complaint gets a random reference number. Choose how many digits it has.</p></div></header>
            <div className="settings-reference-grid">
              <Field label="Reference number length" required error={error?.fields.reference_length} hint="Digits in the random number at the end, 3 to 10."><input required type="number" inputMode="numeric" min={3} max={10} step={1} value={value} onChange={(e) => { setLen(e.target.value); setSuccess(false); }} /></Field>
              <div className="settings-reference-preview"><span>EXAMPLE REFERENCE</span><strong>{sample}</strong><small>BICMA · Year · Division code · Random number</small></div>
            </div>
            <p className="settings-inline-note"><Icon name="help" size={16} />Existing complaint reference numbers stay the same. A longer number allows more complaints per division each year; if the numbers ever run out, the next ones grow by one digit automatically.</p>
          </section>
          <section className="card settings-section" aria-labelledby="settings-shows">
            <header className="settings-section-header"><span className="icon-tile"><Icon name="category" size={22} /></span><div><span className="settings-eyebrow">PUBLIC COMPLAINT FORM</span><h2 id="settings-shows">Reality shows</h2><p>The list people choose from on the Online Reality Show complaint form.</p></div></header>
            <Field label="Reality shows" error={error?.fields.reality_shows} hint="One show per line. Complainants pick from this list, or choose “Other (specify)”. Leave it empty to let them type the name instead."><textarea rows={6} maxLength={24000} value={showsValue} onChange={(e) => { setShows(e.target.value); setSuccess(false); }} placeholder={"Name of the first show\nName of the second show"} /></Field>
            <div className="settings-editor-footer"><span>{showsValue.split("\n").filter((x) => x.trim()).length} shows listed</span></div>
          </section>
          <section className="card settings-section" aria-labelledby="settings-declaration">
            <header className="settings-section-header"><span className="icon-tile"><Icon name="edit" size={22} /></span><div><span className="settings-eyebrow">PUBLIC COMPLAINT FORM</span><h2 id="settings-declaration">Complainant declaration</h2><p>The statement a complainant accepts before submitting a complaint.</p></div></header>
            <Field label="Declaration text" required error={error?.fields.declaration_text}><textarea required rows={8} minLength={20} maxLength={3000} value={declValue} onChange={(e) => { setDecl(e.target.value); setSuccess(false); }} aria-describedby="declaration-help declaration-count" /></Field>
            <div className="settings-editor-footer"><span id="declaration-help">Use 20–3,000 characters.</span><span id="declaration-count">{declValue.length.toLocaleString()} / 3,000</span></div>
            <p className="settings-inline-note"><Icon name="check" size={16} />Acceptance is required on the public complaint form.</p>
          </section>
        </fieldset>
        {error && <p className="error" role="alert">{error.message}</p>}
        <div className="settings-save-bar"><span role="status" className={success && !dirty ? "settings-saved" : "muted"}>{busy ? "Saving settings…" : dirty ? "You have unsaved changes" : success ? "All changes saved" : "Changes apply to new submissions"}</span><div><button type="button" className="btn secondary" disabled={busy || !dirty} onClick={reset}>Discard changes</button><button className="btn" disabled={busy || !dirty}><Icon name={busy ? "refresh" : "check"} size={17} />{busy ? "Saving…" : "Save settings"}</button></div></div>
      </form>
      <aside className="settings-communications"><span className="icon-tile"><Icon name="mail" size={20} /></span><div><strong>Email &amp; SMS configuration</strong><p>Delivery settings are managed outside this page.</p></div><span className="chip">Managed separately</span></aside>
    </div>
  );
}
