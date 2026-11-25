import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../api";
import { Field, StatusBadge, fmt } from "../../components/ui";
import { Icon, type IconName } from "../../components/Icon";
import { WalkingMascot } from "../../components/WalkingMascot";
import { useToast } from "../../components/Toast";
import { ScanBadge, useFileScan } from "../../components/FileScan";
import "../../styles/Track.css";

interface TrackDocument { id: string; name: string; size: number; kind: "attachment" | "followup" }

interface PublicMessage { kind: string; body: string; from: string; created_at: string }
interface Tracked {
  reference: string; public_status: string; public_status_display: string; created_at: string; updated_at: string;
  verified: boolean; messages?: PublicMessage[]; can_reply?: boolean;
  details?: { fields: { label: string; value: string }[]; documents: string[]; document_files?: TrackDocument[] };
}

const STAGES: { icon: IconName; label: string }[] = [
  { icon: "complaint", label: "Received" }, { icon: "search", label: "Under review" }, { icon: "check", label: "Outcome" },
];

function stageOf(status: string): { index: number; end: "" | "ok" | "bad" } {  // index 3 = finished successfully
  if (status === "received") return { index: 0, end: "" };
  if (status === "closed" || status === "resolved") return { index: 3, end: "ok" };  // past the last step: every step is done
  if (status === "not_within_mandate") return { index: 2, end: "bad" };
  return { index: 1, end: "" };
}

export function Track() {
  const toast = useToast();
  const [preview, setPreview] = useState<TrackDocument | null>(null);
  const previewDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (preview) previewDialog.current?.showModal();
    else previewDialog.current?.close();
  }, [preview]);
  const [sp] = useSearchParams();
  // The "information needed" email links here with ?ref=<reference>&t=<secure token>.
  const pre = sp.get("ref") ?? (useLocation().state as { reference?: string } | null)?.reference ?? "";
  const [token, setToken] = useState(sp.get("t") ?? "");
  const [ref, setRef] = useState(pre);
  const [res, setRes] = useState<Tracked | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [replyErr, setReplyErr] = useState("");
  const [sending, setSending] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  // Step 1 asks for a reference number or CID, step 2 for the 6-digit code emailed to the complainant.
  const [step, setStep] = useState<"id" | "code">("id");
  const [code, setCode] = useState("");
  const [notice, setNotice] = useState("");
  const [others, setOthers] = useState<{ reference: string; token: string }[]>([]);

  async function lookup(reference = ref, withToken = token) {
    setBusy(true); setErr(""); setRes(null);
    try { setRes(await api<Tracked>("/public/track/", { json: { reference: reference.trim(), ...(withToken ? { token: withToken } : {}) } })); }
    catch (x) { setErr((x as ApiError).message); if (withToken) setToken(""); }
    finally { setBusy(false); }
  }
  useEffect(() => { if (pre && token) void lookup(pre, token); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function sendCode(e?: FormEvent) {
    e?.preventDefault();
    if (busy) return;
    setBusy(true); setErr(""); setNotice(""); setRes(null);
    try {
      const r = await api<{ detail: string }>("/public/track/otp/", { json: { identifier: ref.trim() } });
      setNotice(r.detail); setStep("code"); setCode("");
    } catch (x) { setErr((x as ApiError).message); }
    finally { setBusy(false); }
  }
  async function confirmCode(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true); setErr("");
    try {
      const r = await api<{ complaints: { reference: string; token: string }[] }>("/public/track/otp/verify/", { json: { identifier: ref.trim(), code: code.trim() } });
      const first = r.complaints[0];
      setOthers(r.complaints.length > 1 ? r.complaints : []);
      setToken(first.token); setRef(first.reference); setStep("id"); setCode(""); setNotice("");
      await lookup(first.reference, first.token);
    } catch (x) { setErr((x as ApiError).message); setBusy(false); }
  }
  // Additional information: shown newest first, ten at a time, so even 100 additions stay light.
  interface Extra { id: string; body: string; created_at: string; files: string[]; document_files?: TrackDocument[] }
  const [extras, setExtras] = useState<Extra[]>([]);
  const [extraTotal, setExtraTotal] = useState(0);
  const [extraOpen, setExtraOpen] = useState(true);
  const [extraText, setExtraText] = useState("");
  const [extraFiles, setExtraFiles] = useState<File[]>([]);
  const [extraErr, setExtraErr] = useState("");
  const [extraBusy, setExtraBusy] = useState(false);
  const extraInput = useRef<HTMLInputElement>(null);

  async function loadExtras(reference: string, withToken: string, offset = 0) {
    try {
      const r = await api<{ total: number; open: boolean; items: Extra[] }>("/public/track/additional/", { json: { reference, token: withToken, action: "list", offset } });
      setExtras((prev) => (offset ? [...prev, ...r.items] : r.items)); setExtraTotal(r.total); setExtraOpen(r.open);
    } catch { /* the complaint itself is still shown */ }
  }
  useEffect(() => { if (res && token) void loadExtras(res.reference, token); else { setExtras([]); setExtraTotal(0); } }, [res?.reference, token]); // eslint-disable-line react-hooks/exhaustive-deps

  const extraScan = useFileScan(extraFiles);  // each chosen file is checked for viruses and harmful content straight away
  const replyScan = useFileScan(files);
  async function addExtra(e: FormEvent) {
    e.preventDefault();
    if (extraBusy || !res || extraScan.blocked || extraScan.scanning) return;
    setExtraBusy(true); setExtraErr("");
    const fd = new FormData();
    fd.append("reference", res.reference); fd.append("token", token); fd.append("message", extraText);
    extraFiles.forEach((f) => fd.append("files", f));
    try {
      await api("/public/track/additional/", { form: fd });
      setExtraText(""); setExtraFiles([]); if (extraInput.current) extraInput.current.value = "";
      toast.success("Your additional information has been sent to BICMA.");
      await loadExtras(res.reference, token);
    } catch (x) { const m = x as ApiError; setExtraErr(m.message); }
    finally { setExtraBusy(false); }
  }

  const startOver = () => { setStep("id"); setCode(""); setNotice(""); setErr(""); };

  async function sendReply(e: FormEvent) {
    e.preventDefault();
    if (sending || !res || replyScan.blocked || replyScan.scanning) return;
    setSending(true); setReplyErr("");
    const fd = new FormData();
    fd.append("reference", res.reference); fd.append("token", token); fd.append("message", reply);
    files.forEach((f) => fd.append("files", f));
    try {
      await api("/public/track/reply/", { form: fd });
      setReply(""); setFiles([]); if (fileInput.current) fileInput.current.value = "";
      toast.success("Your reply and documents have been sent to BICMA.");
      await lookup(res.reference, token);
    } catch (x) { setReplyErr((x as ApiError).message); }
    finally { setSending(false); }
  }

  function documentUrl(document: TrackDocument) {
    const query = new URLSearchParams({ reference: res!.reference, token });
    return `/api/public/track/documents/${document.kind}/${document.id}/?${query}`;
  }

  function documentList(documents: TrackDocument[]) {
    return <ul className="tracking-documents">{documents.map((d) => {
      return <li key={d.id}><span className="icon-tile"><Icon name="complaint" size={20} /></span><div><strong>{d.name}</strong><small>{d.size < 1024 * 1024 ? `${Math.max(1, Math.round(d.size / 1024))} KB` : `${(d.size / (1024 * 1024)).toFixed(1)} MB`}</small></div><button type="button" className="tracking-document-view" onClick={() => setPreview(d)}><Icon name="eye" size={16} />View<span className="sr-only"> {d.name}</span></button></li>;
    })}</ul>;
  }

  const stage = res ? stageOf(res.public_status) : null;
  return (
    <div className={`container track-page${res ? " track-page-with-result" : ""}`}>
      <dialog ref={previewDialog} className="tracking-document-dialog" onCancel={() => setPreview(null)} onClose={() => setPreview(null)} aria-labelledby="document-preview-title">
        {preview && <>
          <header><h2 id="document-preview-title">{preview.name}</h2><button type="button" className="tracking-document-close" aria-label="Close document preview" onClick={() => setPreview(null)}><Icon name="close" size={22} /></button></header>
          <div className="tracking-document-preview">
            {/\.(jpe?g|png|gif|webp)$/i.test(preview.name) ? <img src={documentUrl(preview)} alt={preview.name} /> : /\.pdf$/i.test(preview.name) ? <iframe src={documentUrl(preview)} title={preview.name} /> : <p>Open this document to view it in a supported application.</p>}
          </div>
          <footer><a href={documentUrl(preview)} target="_blank" rel="noopener noreferrer">Open in a new tab<Icon name="eye" size={16} /></a></footer>
        </>}
      </dialog>
      <header className={`track-hero${!res ? " track-entry-hero" : ""}`}>
        <span className="track-eyebrow"><Icon name="search" size={16} />BICMA COMPLAINT PORTAL</span>
        <h1>Track a complaint</h1>
        <p>{step === "code" ? "Verify your email to securely view your complaint." : "Enter your reference number or CID. We will email a 6-digit code to the address on the complaint."}</p>
      </header>
      {step === "id" ? (
        <form className="card track-search-card track-lookup-card" onSubmit={sendCode} aria-busy={busy} aria-labelledby="track-lookup-title">
          <div className="track-lookup-heading"><span className="track-lookup-icon"><Icon name="search" size={25} /></span><span className="tracking-eyebrow">STEP 1 OF 2 · FIND YOUR COMPLAINT</span><h2 id="track-lookup-title">Let’s find your complaint</h2><p>Use your complaint reference or the CID provided when you submitted it.</p></div>
          <Field label="Reference number or CID" required hint="Find your reference in your confirmation email, or enter your 11-digit CID."><input required value={ref} onChange={(e) => setRef(e.target.value)} placeholder="e.g. 0009 or your 11-digit CID" autoComplete="off" spellCheck={false} aria-invalid={!!err} aria-describedby={err ? "track-error" : undefined} /></Field>
          {err && <p id="track-error" className="error" role="alert">{err}</p>}
          <button type="submit" className="btn track-lookup-submit" disabled={busy || !ref.trim()}><Icon name={busy ? "refresh" : "mail"} />{busy ? "Sending…" : "Send verification code"}<Icon name="right" size={17} /></button>
          <div className="track-lookup-email"><Icon name="lock" size={18} /><p>We’ll email a 6-digit code to the address on your complaint before showing your details.</p></div>
          <p className="track-lookup-new">Need to raise a new issue? <Link to="/submit">Submit a complaint<Icon name="right" size={14} /></Link></p>
        </form>
      ) : (
        <form className="card track-search-card track-code-card" onSubmit={confirmCode} aria-labelledby="track-code-title" aria-busy={busy}>
          <div className="track-code-heading">
            <span className="track-code-icon"><Icon name="mail" size={26} /></span>
            <span className="tracking-eyebrow">STEP 2 OF 2 · EMAIL VERIFICATION</span>
            <h2 id="track-code-title">Check your email</h2>
            <p>Enter the 6-digit code to view your complaint.</p>
          </div>
          <div className="track-code-reference"><span>Reference number or CID</span><strong>{ref}</strong></div>
          {notice && <div id="track-code-notice" className="track-code-notice" role="status"><Icon name="inbox" size={20} /><p>{notice}</p></div>}
          <Field label="6-digit code" required><input className="track-code-input" required inputMode="numeric" pattern="\d{6}" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} placeholder="000000" autoComplete="one-time-code" autoFocus aria-invalid={!!err} aria-describedby={[notice && "track-code-notice", err && "track-error"].filter(Boolean).join(" ") || undefined} /></Field>
          {err && <p id="track-error" className="error" role="alert">{err}</p>}
          <button type="submit" className="btn track-code-confirm" disabled={busy || code.length !== 6}><Icon name={busy ? "refresh" : "check"} />{busy ? "Checking…" : "Confirm code"}</button>
          <div className="track-code-actions">
            <p>Didn’t receive an email? Check your spam folder.</p>
            <button type="button" className="track-code-link" disabled={busy} onClick={() => sendCode()}><Icon name="refresh" size={16} />Send a new code</button>
            <button type="button" className="track-code-link track-code-back" disabled={busy} onClick={startOver}><Icon name="left" size={16} />Change reference or CID</button>
          </div>
          <p className="track-code-security"><Icon name="lock" size={14} />Your complaint details stay private.</p>
        </form>
      )}
      {res && others.length > 1 && (
        <p className="muted" role="group" aria-label="Your complaints">Your complaints: {others.map((o) => <button key={o.reference} type="button" className="btn secondary" disabled={o.reference === res.reference} onClick={() => { setToken(o.token); setRef(o.reference); void lookup(o.reference, o.token); }}>{o.reference}</button>)}</p>
      )}
      {res && stage && (
        <section className="card tracking-result" aria-live="polite" aria-label="Complaint tracking result">
          <header className="tracking-result-header"><span className="icon-tile lg"><Icon name="complaint" size={26} /></span><div><span className="tracking-eyebrow">COMPLAINT REFERENCE</span><h2>{res.reference}</h2></div><StatusBadge value={res.public_status} label={res.public_status_display} /></header>
          <div className="tracking-progress"><h3>Complaint progress</h3>
          <WalkingMascot key={res.reference + res.public_status} stage={stage.index} done={stage.index >= 3} />
          <div className="tracker" role="list" aria-label="Progress">
            {STAGES.map((s, i) => {
              const state = i < stage.index ? "done" : i === stage.index ? `current ${stage.end}` : "";
              const label = i === 2 && stage.end === "bad" ? "Outside jurisdiction" : i === 2 && res.public_status === "closed" ? "Closed" : i === 2 && res.public_status === "resolved" ? "Resolved" : s.label;
              return (
                <div key={s.label} role="listitem" className={`step ${state}`} aria-current={i === stage.index ? "step" : undefined}>
                  <div className="node"><Icon name={i < stage.index ? "check" : i === 2 && stage.end === "bad" ? "close" : s.icon} size={20} /></div><strong>{label}</strong><span className="tracking-step-caption">{i < stage.index ? "Completed" : i === stage.index ? "Current stage" : "Next stage"}</span>
                </div>
              );
            })}
          </div>
          </div>
          {res.details && (
            <section className="tracking-submitted">
              <div className="tracking-section-title"><h3><Icon name="complaint" size={20} />Your complaint</h3><span className="chip"><Icon name="lock" size={12} /> View only</span></div><p className="tracking-section-intro">The details you submitted with your complaint.</p>
              <dl className="tracking-detail-grid">
                {res.details.fields.map((x) => <div key={x.label} className={["Description", "Remedy sought"].includes(x.label) ? "tracking-detail-wide" : undefined}><dt>{x.label}</dt><dd>{x.value}</dd></div>)}
              </dl>
              {!!res.details.documents.length && <div className="tracking-document-section"><h4>Documents submitted <span className="chip">{res.details.documents.length}</span></h4>{res.details.document_files ? documentList(res.details.document_files) : <p>{res.details.documents.join(", ")}</p>}</div>}
            </section>
          )}
          {res.verified && token && (
            <div className="tracking-submitted tracking-additional">
              <h3><Icon name="plus" size={20} />Additional information {extraTotal > 0 && <span className="chip" style={{ marginLeft: 6 }}>{extraTotal}</span>}</h3>
              <p className="tracking-section-intro">Have something to add? Send an update or supporting documents to BICMA.</p>
              {extraOpen ? (
                <form className="tracking-additional-form" onSubmit={addExtra}>
                  <Field label="Add information" hint="Anything new that helps BICMA with your complaint."><textarea rows={3} maxLength={5000} value={extraText} onChange={(e) => setExtraText(e.target.value)} /></Field>
                  <div className="upload-send-row">
                    <div className="tracking-compact-upload">
                  <Field label="Upload documents" hint="Optional. You can choose several files (photos, PDF and similar).">
                      <input ref={extraInput} type="file" multiple onChange={(e) => setExtraFiles(Array.from(e.target.files ?? []))} />
                    </Field>
                    </div>
                    <button type="submit" className="btn" disabled={extraBusy || extraScan.blocked || extraScan.scanning || (!extraText.trim() && !extraFiles.length)}><Icon name="send" />{extraBusy ? "Sending…" : extraScan.blocked ? "Remove the blocked file" : extraScan.scanning && extraFiles.length ? "Scanning…" : "Send to BICMA"}</button>
                  </div>
                  {extraFiles.length > 0 && <ul className="scan-list" aria-label="Files to send">{extraFiles.map((f, i) => <li key={`${f.name}-${i}`}><strong>{f.name}</strong><small>{Math.ceil(f.size / 1024)} KB</small><ScanBadge scan={extraScan.of(f)} /></li>)}</ul>}
                  {extraErr && <p className="error" role="alert">{extraErr}</p>}
                </form>
              ) : <p className="muted">This complaint is closed, so no more information can be added.</p>}
              {extras.length > 0 && (
                <ol className="timeline" style={{ marginTop: 14 }}>
                  {extras.map((x) => (
                    <li key={x.id}><span className="dot" aria-hidden="true"><Icon name="user" size={14} /></span>
                      <div className="when">{fmt(x.created_at)}</div>
                      {x.body && <div style={{ whiteSpace: "pre-wrap" }}>{x.body}</div>}
                      {x.document_files?.length ? documentList(x.document_files) : x.files.length > 0 && <div className="muted">Documents: {x.files.join(", ")}</div>}</li>
                  ))}
                </ol>
              )}
              {extras.length < extraTotal && <button type="button" className="btn secondary" onClick={() => loadExtras(res.reference, token, extras.length)}>Show older ({extraTotal - extras.length} more)</button>}
            </div>
          )}
          {res.verified && !!res.messages?.length && (
            <div style={{ marginTop: 18 }}>
              <h3>Messages</h3>
              <ol className="timeline">
                {res.messages.map((m, i) => (
                  <li key={i}><span className="dot" aria-hidden="true"><Icon name={m.from === "BICMA" ? "mail" : "user"} size={14} /></span>
                    <div className="what"><strong>{m.from}</strong>{m.kind === "info_request" && <span className="badge warn" style={{ marginLeft: 8 }}>Information requested</span>}</div>
                    <div className="when">{fmt(m.created_at)}</div><div style={{ whiteSpace: "pre-wrap" }}>{m.body}</div></li>
                ))}
              </ol>
            </div>
          )}
          {res.can_reply && (
            <form onSubmit={sendReply} style={{ marginTop: 18 }}>
              <h3>Send the information BICMA asked for</h3>
              <Field label="Your reply" required><textarea required rows={4} maxLength={10000} value={reply} onChange={(e) => setReply(e.target.value)} /></Field>
              <div className="upload-send-row">
                <Field label="Additional documents" hint="Optional. You can choose several files (photos, PDF and similar).">
                  <input ref={fileInput} type="file" multiple onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
                </Field>
                <button type="submit" className="btn" disabled={sending || replyScan.blocked || replyScan.scanning}><Icon name="send" />{sending ? "Sending…" : replyScan.blocked ? "Remove the blocked file" : replyScan.scanning && files.length ? "Scanning…" : "Send to BICMA"}</button>
              </div>
              {files.length > 0 && <ul className="scan-list" aria-label="Files to send">{files.map((f, i) => <li key={`${f.name}-${i}`}><strong>{f.name}</strong><small>{Math.ceil(f.size / 1024)} KB</small><ScanBadge scan={replyScan.of(f)} /></li>)}</ul>}
              {replyErr && <p className="error" role="alert">{replyErr}</p>}
            </form>
          )}
          <dl className="tracking-facts">
            <div><dt><Icon name="complaint" size={17} />Submitted</dt><dd><time dateTime={res.created_at}>{fmt(res.created_at)}</time></dd></div>
            <div><dt><Icon name="history" size={17} />Last updated</dt><dd><time dateTime={res.updated_at}>{fmt(res.updated_at)}</time></dd></div>
          </dl>
          <footer className="tracking-result-footer"><Icon name="help" size={18} /><span>Keep your reference number to check for updates.</span></footer>
        </section>
      )}
    </div>
  );
}
