import { Icon } from "./Icon";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import type { Meta } from "../types";
import { Field, humanKb } from "./ui";
import "../styles/ComplaintForm.css";

export interface FormResult { reference: string; id?: string; draft?: boolean }

type Values = Record<string, string | boolean>;
const empty: Values = {
  channel: "phone", date_received: new Date().toISOString().slice(0, 10),
  complainant_type: "individual", complainant_name: "", cid: "", phone: "", email: "", confidential: false, dzongkhag: "", gewog: "", locality: "", area_type: "",
  preferred_contact: "email", on_behalf: false, affected_name: "", affected_relationship: "", affected_contact: "",
  category: "", subcategory: "", subject: "", description: "", incident_date: "", incident_time: "",
  provider_type: "", provider: "", platform: "", already_complained: false, provider_reference: "", medium_of_publication: "",
  remedy_sought: "", website_or_social: "", additional_info: "", declaration_accepted: false, fax_number: "",
};
const NULLABLE = ["subcategory", "category", "provider", "provider_type", "dzongkhag", "gewog", "incident_date", "incident_time", "date_received"];

/** Used by the public portal (offline=false) and by officials registering offline complaints (offline=true). */
export function ComplaintForm({ offline, onDone }: { offline: boolean; onDone: (r: FormResult) => void }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [v, setV] = useState<Values>(empty);
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [cidState, setCidState] = useState<"" | "loading" | "found" | "missing" | "unavailable">("");
  const [dups, setDups] = useState<{ id: string; reference: string; subject: string }[] | null>(null);
  const [cap, setCap] = useState<{ token: string; svg: string } | null>(null);
  const [capAnswer, setCapAnswer] = useState("");
  const [verificationOpen, setVerificationOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [captchaError, setCaptchaError] = useState("");
  const loadCaptcha = useCallback(() => {
    setCapAnswer("");
    setCap(null);
    setCaptchaError("");
    api<{ token: string; svg: string }>("/public/captcha/").then(setCap).catch(() => setCaptchaError("Could not load the security image. Please select New image to try again."));
  }, []);
  useEffect(() => {
    if (verificationOpen) dialogRef.current?.showModal();
    else dialogRef.current?.close();
  }, [verificationOpen]);

  useEffect(() => { api<Meta>("/meta/").then(setMeta).catch(() => setErr(new ApiError("Could not load the form. Please refresh.", 0))); }, []);

  const set = (k: string) => (e: { target: { value: string } }) =>
    setV((p) => ({ ...p, [k]: e.target.value, ...(k === "category" ? { subcategory: "" } : {}), ...(k === "dzongkhag" ? { gewog: "" } : {}),
      ...(k === "provider" ? { platform: meta?.providers.find((p) => p.id === e.target.value)?.name ?? "" } : {}) }));
  const individual = true; // the complainant is always a person on this form
  async function lookupCid(cid: string) {
    if (!individual || !/^\d{11}$/.test(cid)) { setCidState(""); return; }
    setCidState("loading");
    try {
      const r = await api<{ full_name: string }>("/public/cid-lookup/", { json: { cid } });
      setV((p) => (p.cid === cid ? { ...p, complainant_name: r.full_name } : p));
      setCidState("found");
    } catch (x) {
      setCidState((x as ApiError).status === 404 ? "missing" : "unavailable");
    }
  }
  const onCid = (e: { target: { value: string } }) => {
    const cid = individual ? e.target.value.replace(/\D/g, "").slice(0, 11) : e.target.value.slice(0, 20);
    setV((p) => ({ ...p, cid }));
    if (individual && cid.length === 11) lookupCid(cid); else setCidState("");
  };
  const check = (k: string) => (e: { target: { checked: boolean } }) => setV((p) => ({ ...p, [k]: e.target.checked }));
  const f = (k: string) => err?.fields[k];
  const gewogs = meta?.dzongkhags.find((d) => String(d.id) === v.dzongkhag)?.gewogs ?? [];
  const cat = meta?.categories.find((c) => c.id === v.category);
  const suggested = meta?.divisions.find((d) => d.id === cat?.default_division);
  const isMedia = !!suggested && suggested.name.toLowerCase().startsWith("media");
  const catGroups = (meta?.divisions ?? []).map((d) => ({ d, cats: (meta?.categories ?? []).filter((c) => c.default_division === d.id) })).filter((g) => g.cats.length);
  const ungrouped = (meta?.categories ?? []).filter((c) => !c.default_division);

  async function submit(e: FormEvent, opts: { draft?: boolean; confirmDuplicate?: boolean } = {}) {
    e.preventDefault();
    if (busy) return;
    if (!offline && !verificationOpen) {
      setErr(null);
      loadCaptcha();
      setVerificationOpen(true);
      return;
    }
    if (!offline && !cap) return;
    setBusy(true);
    setErr(null);
    setDups(null);
    const fd = new FormData();
    for (const [k, val] of Object.entries(v)) {
      if (typeof val === "boolean") fd.append(k, val ? "true" : "false");
      else if (val !== "" || !NULLABLE.includes(k)) { if (val !== "") fd.append(k, val); }
    }
    if (!offline) { fd.delete("channel"); fd.delete("date_received"); fd.append("captcha_token", cap?.token ?? ""); fd.append("captcha_answer", capAnswer); }
    if (opts.draft) fd.append("draft", "true");
    if (opts.confirmDuplicate) fd.append("confirm_duplicate", "true");
    files.forEach((f) => fd.append("files", f));
    try {
      const res = await api<FormResult>(offline ? "/complaints/" : "/public/complaints/", { form: fd });
      onDone({ ...res, draft: opts.draft });
    } catch (x) {
      const ex = x as ApiError;
      const body = ex.body as { duplicates?: { id: string; reference: string; subject: string }[] } | null;
      if (ex.status === 409 && body?.duplicates) setDups(body.duplicates);
      else setErr(ex);
      if (!offline) {
        loadCaptcha(); // each challenge is single-use
        if (!ex.fields.captcha_answer) setVerificationOpen(false);
      }
      if (offline || !ex.fields.captcha_answer) window.scrollTo({ top: 0 });
    } finally {
      setBusy(false);
    }
  }

  // Officials register on a complainant's behalf, so the copy talks about "the complainant", not "you".
  const t = (pub: string, staff: string) => (offline ? staff : pub);
  if (!meta) return <p>{err ? err.message : "Loading form…"}</p>;
  return (
    <form onSubmit={(e) => submit(e)} className="card complaint-form" noValidate={false}>
      <p className="muted"><span className="req" style={{ color: "var(--c-accent)" }}>*</span> marks required fields.</p>
      {err && <p className="error" role="alert">{err.message}</p>}
      {dups && (
        <div className="notice" role="alert">
          <strong>A similar open complaint already exists.</strong>
          <ul>{dups.map((d) => <li key={d.id}><a href={`/staff/complaints/${d.id}`} target="_blank" rel="noreferrer">{d.reference}</a> — {d.subject}</li>)}</ul>
          <button type="button" className="btn secondary" disabled={busy} onClick={(e) => submit(e as unknown as FormEvent, { confirmDuplicate: true })}>Register anyway</button>
        </div>
      )}

      {offline && (
        <section className="form-section" aria-labelledby="channel-heading">
          <div className="complaint-section-heading"><span className="form-section-icon"><Icon name="send" size={23} /></span><div><span className="form-section-step">SECTION 01</span><h2 id="channel-heading">How was it received?</h2></div></div>
          <div className="row">
            <Field label="Channel" required error={f("channel")}><select required value={v.channel as string} onChange={set("channel")}>{meta.channels.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</select></Field>
            <Field label="Date received" required error={f("date_received")}><input required type="date" max={new Date().toISOString().slice(0, 10)} value={v.date_received as string} onChange={set("date_received")} /></Field>
          </div>
        </section>
      )}

      <section className="form-section" aria-labelledby="about-you-heading">
      <div className="complaint-section-heading"><span className="form-section-icon"><Icon name="users" size={23} /></span><div><span className="form-section-step">SECTION {offline ? "02" : "01"}</span><h2 id="about-you-heading">{offline ? "Complainant" : "About you"}</h2><p className="section-description">{t("Tell us who is making the complaint and how we can contact you.", "Enter the details of the person who made the complaint and how BICMA can contact them.")}</p></div></div>
      <div className="row">
        <Field label={individual ? "CID number" : "Registration / licence number"} required={!offline} error={f("cid")} hint={!individual ? "Enter the number the organisation is registered under." : cidState === "loading" ? "Looking up your name…" : cidState === "found" ? "Name filled from the citizen registry." : cidState === "missing" ? "No registry record found. Enter the name by hand." : cidState === "unavailable" ? "Registry lookup is unavailable. Enter the name by hand." : "11 digits. Your name is filled in automatically."}><input required={!offline} inputMode={individual ? "numeric" : "text"} pattern={individual ? "\\d{11}" : undefined} maxLength={individual ? 11 : 20} placeholder={individual ? "11-digit CID" : "Registration number"} value={v.cid as string} onChange={onCid} autoComplete="off" /></Field>
        <Field label={individual ? "Full name" : "Name of the organisation"} required error={f("complainant_name")}><input required readOnly={cidState === "found"} placeholder={cidState === "loading" ? "Looking up…" : t("Enter your full name", "Enter the complainant’s full name")} value={v.complainant_name as string} onChange={set("complainant_name")} autoComplete="name" /></Field>
        <Field label="Phone number" required={!offline} error={f("phone")} hint="8-digit Bhutan number"><input required={!offline} type="tel" pattern="(\+975)?\d{8}" placeholder="17123456" value={v.phone as string} onChange={set("phone")} autoComplete="tel" /></Field>
        <Field label="Email address" required={!offline} error={f("email")} hint={offline ? "Leave empty if the complainant has none." : "Used for the acknowledgement and updates."}><input required={!offline} type="email" placeholder="you@example.com" value={v.email as string} onChange={set("email")} autoComplete="email" /></Field>
        <Field label="Preferred communication" required>
          <select required value={v.preferred_contact as string} onChange={set("preferred_contact")}>
            <option value="email">Email</option><option value="phone">Phone call</option>
          </select>
        </Field>
      </div>
      <label className="on-behalf">
        <input type="checkbox" checked={v.confidential as boolean} onChange={check("confidential")} />
        <span><strong>Keep my identity confidential</strong><small>{t("Your identity will be hidden from the provider and from officers who do not need it.", "Hide the complainant’s identity from the provider and from officers who do not need it.")}</small></span>
      </label>
      <label className="on-behalf">
        <input type="checkbox" checked={v.on_behalf as boolean} onChange={check("on_behalf")} />
        <span><strong>{t("Submitting for someone else?", "Made on behalf of someone else?")}</strong><small>{t("I am submitting this complaint on behalf of another person.", "The complainant is reporting on behalf of another person.")}</small></span>
      </label>
      {v.on_behalf && (
        <div className="row">
          <Field label="Name of affected person" required error={f("affected_name")}><input required value={v.affected_name as string} onChange={set("affected_name")} /></Field>
          <Field label={t("Relationship to you", "Relationship to complainant")} required error={f("affected_relationship")}><input required placeholder="e.g. Parent, spouse or representative" value={v.affected_relationship as string} onChange={set("affected_relationship")} /></Field>
          <Field label="Their contact details" error={f("affected_contact")}><input value={v.affected_contact as string} onChange={set("affected_contact")} /></Field>
        </div>
      )}
      </section>

      <section className="form-section" aria-labelledby="complaint-heading">
      <div className="complaint-section-heading"><span className="form-section-icon"><Icon name="complaint" size={23} /></span><div><span className="form-section-step">SECTION {offline ? "03" : "02"}</span><h2 id="complaint-heading">{t("Your complaint", "Complaint details")}</h2><p className="section-description">{t("Choose the category that best fits. It decides which BICMA division handles your complaint.", "Choose the category; it suggests the responsible division, which is reviewed in triage.")}</p></div></div>
      <div className="row">
        <Field label="Complaint category" required error={f("category")}>
          <select required value={v.category as string} onChange={set("category")}>
            <option value="">Select a category</option>
            {catGroups.map((g) => <optgroup key={g.d.id} label={g.d.name}>{g.cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</optgroup>)}
            {ungrouped.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Suggested division"><input readOnly value={suggested?.name ?? (v.category ? "To be decided in triage" : "")} placeholder="Chosen from the category" /></Field>
        {cat && cat.subcategories.length > 0 && (
          <Field label="Sub-category" error={f("subcategory")}><select value={v.subcategory as string} onChange={set("subcategory")}><option value="">Select (optional)</option>{cat.subcategories.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
        )}
      </div>
      <Field label="Title" required error={f("subject")}><input required maxLength={200} placeholder={t("Briefly summarise your complaint", "Briefly summarise the complaint")} value={v.subject as string} onChange={set("subject")} /></Field>
      {isMedia && <Field label="Medium of publication" required error={f("medium_of_publication")}><input required placeholder="e.g. newspaper, TV channel, website, social media page" value={v.medium_of_publication as string} onChange={set("medium_of_publication")} /></Field>}
      <div className="row">
        <Field label="Provider / party type" required error={f("provider_type")}>
          <select required value={v.provider_type as string} onChange={set("provider_type")}><option value="">Select type</option>{meta.provider_types.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
        </Field>
        <Field label="Provider / company" error={f("provider")} hint="Pick from the list, or type the name below.">
          <select value={v.provider as string} onChange={set("provider")}><option value="">Not in the list</option>{meta.providers.filter((p) => !v.provider_type || !p.provider_type || p.provider_type === v.provider_type).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
        </Field>
        {!v.provider && <Field label="Company name" error={f("platform")}><input value={v.platform as string} onChange={set("platform")} placeholder="Name of the company or channel" /></Field>}
      </div>
      <div className="row">
        <Field label="Already complained to the provider?" required>
          <select required value={v.already_complained ? "yes" : "no"} onChange={(e) => setV((p) => ({ ...p, already_complained: e.target.value === "yes" }))}><option value="no">No</option><option value="yes">Yes</option></select>
        </Field>
        {v.already_complained && <Field label="Provider reference number" required error={f("provider_reference")}><input required value={v.provider_reference as string} onChange={set("provider_reference")} /></Field>}
      </div>
      <div className="row">
        <Field label="Dzongkhag" required error={f("dzongkhag")}>
          <select required value={v.dzongkhag as string} onChange={set("dzongkhag")}><option value="">Select Dzongkhag</option>{meta.dzongkhags.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
        </Field>
        <Field label="Gewog" error={f("gewog")}>
          <select value={v.gewog as string} onChange={set("gewog")} disabled={!v.dzongkhag || gewogs.length === 0}>
            <option value="">{v.dzongkhag ? (gewogs.length ? "Select Gewog" : "No Gewogs listed") : "Select a Dzongkhag first"}</option>
            {gewogs.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </Field>
        <Field label="Gewog / town / village" required={!v.gewog} error={f("locality")}><input required={!v.gewog} value={v.locality as string} onChange={set("locality")} /></Field>
        <Field label="Area type" required error={f("area_type")}>
          <select required value={v.area_type as string} onChange={set("area_type")}><option value="">Select</option><option value="urban">Urban</option><option value="rural">Rural</option></select>
        </Field>
        <Field label="Incident date" required error={f("incident_date")}><input required type="date" max={new Date().toISOString().slice(0, 10)} value={v.incident_date as string} onChange={set("incident_date")} /></Field>
        <Field label="Incident time" required error={f("incident_time")}><input required type="time" value={v.incident_time as string} onChange={set("incident_time")} /></Field>
      </div>
      <Field label="Complaint description" required error={f("description")}><textarea required rows={7} placeholder={t("Describe what happened and any steps you have already taken.", "Record what the complainant reported.")} value={v.description as string} onChange={set("description")} /></Field>
      <Field label="Remedy sought" required error={f("remedy_sought")}><textarea required rows={3} placeholder="What outcome do you want?" value={v.remedy_sought as string} onChange={set("remedy_sought")} /></Field>
      <Field label="Additional notes" error={f("additional_info")}><textarea rows={3} value={v.additional_info as string} onChange={set("additional_info")} /></Field>
      <div className="supporting-documents">
        <div className="supporting-documents-heading"><h3>Supporting documents</h3><span>Optional</span></div>
        <label className="supporting-documents-picker">
          <input type="file" multiple accept={meta.limits.allowed_extensions.map((x) => `.${x}`).join(",")} aria-label="Choose supporting documents" aria-describedby="supporting-documents-hint" aria-invalid={!!f("files")} onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
          <span className="supporting-documents-icon"><Icon name="plus" size={24} /></span>
          <span className="supporting-documents-copy"><strong>Upload supporting files</strong><span>Choose documents, photos or recordings for your complaint.</span></span>
          <span className="supporting-documents-browse">Choose files</span>
        </label>
        <div className="supporting-documents-hint" id="supporting-documents-hint"><span>{meta.limits.allowed_extensions.map((x) => x.toUpperCase()).join(", ")}</span><strong>Up to {meta.limits.upload_max_files} files · {humanKb(meta.limits.upload_max_kb)} each</strong></div>
        {f("files") && <p className="error" role="alert">{f("files")}</p>}
        {files.length > 0 && <div className="supporting-documents-selected"><p aria-live="polite">{files.length} {files.length === 1 ? "file" : "files"} selected</p><ul>{files.map((file, index) => <li key={`${file.name}-${index}`}><span className="supporting-documents-file-icon"><Icon name="complaint" size={20} /></span><span className="supporting-documents-file-name"><strong>{file.name}</strong><small>{Math.ceil(file.size / 1024)} KB</small></span><button type="button" aria-label={`Remove ${file.name}`} onClick={() => setFiles((current) => current.filter((_, i) => i !== index))}><Icon name="close" size={16} /></button></li>)}</ul></div>}
      </div>
      </section>

      {!offline && (
        <label className="on-behalf">
          <input type="checkbox" required checked={v.declaration_accepted as boolean} onChange={check("declaration_accepted")} />
          <span><strong>Declaration <span className="req" aria-hidden="true">*</span></strong><small>{meta.declaration_text}</small></span>
          {f("declaration_accepted") && <small role="alert" style={{ color: "var(--c-accent)" }}>{f("declaration_accepted")}</small>}
        </label>
      )}
      {!offline && <div hidden className="hp" aria-hidden="true"><label>Leave empty<input tabIndex={-1} autoComplete="off" value={v.fax_number as string} onChange={set("fax_number")} /></label></div>}
      {!offline && (
        <dialog ref={dialogRef} className="captcha-dialog" aria-labelledby="captcha-title" aria-describedby="captcha-description" onCancel={(e) => { if (busy) e.preventDefault(); else setVerificationOpen(false); }} onClose={() => setVerificationOpen(false)}>
        {verificationOpen && <section className="captcha" aria-busy={busy}>
          <div className="captcha-dialog-heading">
            <h2 id="captcha-title" className="captcha-title"><Icon name="lock" size={18} />Security check</h2>
            <button type="button" className="btn secondary" aria-label="Close security check" disabled={busy} onClick={() => setVerificationOpen(false)}><Icon name="close" /></button>
          </div>
          <p id="captcha-description" className="muted">Complete this check to submit your complaint.</p>
          <div className="captcha-row">
            {cap ? <img className="captcha-img" alt="Verification characters" src={`data:image/svg+xml;utf8,${encodeURIComponent(cap.svg)}`} width={170} height={60} /> : <div className="captcha-img captcha-loading">Loading…</div>}
            <button type="button" className="btn secondary" onClick={loadCaptcha} disabled={busy} aria-label="Get a new image"><Icon name="refresh" />New image</button>
            <label className="captcha-input">
              <span>Type the characters shown <span className="req" aria-hidden="true">*</span></span>
              <input autoFocus required disabled={busy} autoComplete="off" autoCapitalize="characters" spellCheck={false} maxLength={8} value={capAnswer} onChange={(e) => setCapAnswer(e.target.value)} placeholder="e.g. K7M2P" aria-describedby="captcha-err" />
            </label>
          </div>
          <p id="captcha-err" role="alert" className="captcha-error">{captchaError || f("captcha_answer")}</p>
          <div className="captcha-dialog-actions">
            <button type="button" className="btn secondary" disabled={busy} onClick={() => setVerificationOpen(false)}>Cancel</button>
            <button type="submit" className="btn" disabled={busy || !cap || !capAnswer.trim()}><Icon name="send" />{busy ? "Submitting…" : "Verify and submit"}</button>
          </div>
        </section>}
        </dialog>
      )}
      <div className="form-actions">
        <p className="muted"><Icon name="check" size={18} /><span>{t("Please check your details before submitting.", "Check the details before registering the complaint.")}</span></p>
        {offline && <button type="button" className="btn secondary" disabled={busy} onClick={(e) => submit(e as unknown as FormEvent, { draft: true })}><Icon name="edit" />Save draft</button>}
        <button className="btn" disabled={busy}><Icon name="send" />{busy ? "Submitting…" : offline ? "Register complaint" : "Submit complaint"}</button>
      </div>
    </form>
  );
}
