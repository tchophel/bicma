import { useState, type FormEvent } from "react";
import { Loader } from "../../components/Loader";
import { api, ApiError } from "../../api";
import { useList } from "../../useList";
import { Icon } from "../../components/Icon";
import { Field, PageHeader, PanelTitle } from "../../components/ui";
import "../../styles/Help.css";
import "../../styles/MasterTheme.css";

type WarningSettings = { upload_instructions: string };

export function Help() {
  const { data, err, loading } = useList<WarningSettings>("/admin/settings/");
  const [draft, setDraft] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const message = draft ?? saved ?? data?.upload_instructions ?? "";

  async function save(e: FormEvent) {
    e.preventDefault();
    if (busy || !data) return;
    setBusy(true); setError(""); setSuccess("");
    try {
      const result = await api<WarningSettings>("/admin/settings/", {
        method: "PATCH", json: { upload_instructions: message },
      });
      setSaved(result.upload_instructions); setDraft(null);
      setSuccess("Upload warning saved.");
    } catch (x) { setError((x as ApiError).message); }
    finally { setBusy(false); }
  }

  return <div className="upload-warning-page master-page">
    <PageHeader icon="help" title="Upload warning" subtitle="Write the red warning shown beside supporting document uploads on all complaint forms." />
    {err && <p className="error" role="alert">{err}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {success && <p className="notice" role="status">{success}</p>}
    {loading && <Loader label="Loading upload warning" />}
    {!loading && data && <div className="upload-warning-grid">
      <form className="card upload-warning-form" onSubmit={save}>
        <PanelTitle icon="edit">Write upload warning</PanelTitle>
        <Field label="Warning message" hint="Explain which photos or documents to upload. Leave empty to hide the warning.">
          <textarea rows={8} maxLength={2000} disabled={busy} value={message} onChange={(e) => { setDraft(e.target.value); setSuccess(""); }} placeholder={"Warning\nPlease upload clear photos, screenshots, receipts, or other documents that support your complaint."} />
        </Field>
        <div className="upload-warning-actions"><button type="submit" className="btn" disabled={busy}><Icon name="check" />{busy ? "Saving…" : "Save warning"}</button></div>
      </form>
      <section className="card upload-warning-form" aria-label="Upload warning preview">
        <PanelTitle icon="help">Preview</PanelTitle>
        <p className="muted">This message appears beside the file picker.</p>
        {message.trim() ? <p className="upload-warning-preview">{message}</p> : <p className="muted">No warning will be shown.</p>}
      </section>
    </div>}
  </div>;
}
