import { Icon } from "./Icon";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import type { Meta } from "../types";
import { Field } from "./ui";
import "./ComplaintForm.css";

export interface FormResult { reference: string }

type Values = Record<string, string | boolean>;
const empty: Values = {
  complainant_name: "", phone: "", email: "", dzongkhag: "", gewog: "",
  preferred_contact: "email", on_behalf: false, affected_name: "", affected_relationship: "", affected_contact: "",
  division: "", category: "", subcategory: "", subject: "", description: "", incident_date: "", platform: "",
  website_or_social: "", additional_info: "", fax_number: "",
};

/** Used by the public portal (offline=false) and by officials registering offline complaints (offline=true). */
export function ComplaintForm({ offline, onDone }: { offline: boolean; onDone: (r: FormResult) => void }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [v, setV] = useState<Values>(empty);
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
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
    setV((p) => ({ ...p, [k]: e.target.value, ...(k === "category" ? { subcategory: "" } : {}), ...(k === "dzongkhag" ? { gewog: "" } : {}) }));
  const f = (k: string) => err?.fields[k];
  const gewogs = meta?.dzongkhags.find((d) => String(d.id) === v.dzongkhag)?.gewogs ?? [];

  async function submit(e: FormEvent) {
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
    const body: Record<string, unknown> = { ...v };
    for (const k of ["subcategory", "incident_date", "dzongkhag", "gewog"]) if (!body[k]) body[k] = null;
    delete body.category;
    delete body.subcategory;
    if (offline) body.channel = "other";
    if (!offline) { delete body.channel; body.captcha_token = cap?.token ?? ""; body.captcha_answer = capAnswer; }
    try {
      const res = await api<FormResult>(offline ? "/complaints/" : "/public/complaints/", { json: body });
      onDone(res);
    } catch (x) {
      setErr(x as ApiError);
      if (!offline) {
        loadCaptcha(); // each challenge is single-use
        if (!(x as ApiError).fields.captcha_answer) setVerificationOpen(false);
      }
      if (offline || !(x as ApiError).fields.captcha_answer) window.scrollTo({ top: 0 });
    } finally {
      setBusy(false);
    }
  }

  // Officials register on a complainant's behalf, so the copy talks about "the complainant", not "you".
  const t = (pub: string, staff: string) => (offline ? staff : pub);
  if (!meta) return <p>{err ? err.message : "Loading form…"}</p>;
  return (
    <form onSubmit={submit} className="card complaint-form" noValidate={false}>
      <p className="muted"><span className="req" style={{ color: "var(--c-accent)" }}>*</span> marks required fields.</p>
      {err && <p className="error" role="alert">{err.message}</p>}


      <section className="form-section" aria-labelledby="about-you-heading">
      <div className="complaint-section-heading"><span className="form-section-icon"><Icon name="users" size={23} /></span><div><span className="form-section-step">SECTION 01</span><h2 id="about-you-heading">{offline ? "Complainant" : "About you"}</h2><p className="section-description">{t("Tell us who is making the complaint and how we can contact you.", "Enter the details of the person who made the complaint and how BICMA can contact them.")}</p></div></div>
      <div className="row">
        <Field label="Full name" required error={f("complainant_name")}><input required placeholder={t("Enter your full name", "Enter the complainant’s full name")} value={v.complainant_name as string} onChange={set("complainant_name")} autoComplete="name" /></Field>
        <Field label="Contact number" required={!offline && !String(v.email).trim()} error={f("phone")} hint={offline ? undefined : "Provide a contact number or email address. Only one is required."}><input required={!offline && !String(v.email).trim()} type="tel" placeholder={t("Enter your contact number", "Enter the complainant’s phone number")} value={v.phone as string} onChange={set("phone")} autoComplete="tel" /></Field>
        <Field label="Email address" required={!offline && !String(v.phone).trim()} error={f("email")}><input required={!offline && !String(v.phone).trim()} type="email" placeholder={t("you@example.com", "complainant@example.com")} value={v.email as string} onChange={set("email")} autoComplete="email" /></Field>
        <Field label="Preferred communication" required>
          <select required value={v.preferred_contact as string} onChange={set("preferred_contact")}>
            <option value="email">Email</option><option value="sms">SMS</option><option value="phone">Phone call</option>
          </select>
        </Field>
        <Field label="Dzongkhag" required={!offline} error={f("dzongkhag")}>
          <select required={!offline} value={v.dzongkhag as string} onChange={set("dzongkhag")}>
            <option value="">{t("Select your Dzongkhag", "Select Dzongkhag")}</option>
            {meta.dzongkhags.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <Field label="Gewog" error={f("gewog")} hint={v.dzongkhag && gewogs.length === 0 ? "No Gewogs are listed for this Dzongkhag yet." : undefined}>
          <select value={v.gewog as string} onChange={set("gewog")} disabled={!v.dzongkhag || gewogs.length === 0}>
            <option value="">{v.dzongkhag ? (gewogs.length ? t("Select your Gewog", "Select Gewog") : "No Gewogs available") : "Select a Dzongkhag first"}</option>
            {gewogs.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </Field>
      </div>

      <label className="on-behalf">
        <input type="checkbox" checked={v.on_behalf as boolean} onChange={(e) => setV((p) => ({ ...p, on_behalf: e.target.checked }))} />
        <span><strong>{t("Submitting for someone else?", "Made on behalf of someone else?")}</strong><small>{t("I am submitting this complaint on behalf of another person.", "The complainant is reporting on behalf of another person.")}</small></span>
      </label>
      {v.on_behalf && (
        <div className="row">
          <Field label="Name of affected person" required error={f("affected_name")}><input required placeholder="Enter the affected person’s full name" value={v.affected_name as string} onChange={set("affected_name")} /></Field>
          <Field label={t("Relationship to you", "Relationship to complainant")} required error={f("affected_relationship")}><input required placeholder="e.g. Parent, spouse or representative" value={v.affected_relationship as string} onChange={set("affected_relationship")} /></Field>
          <Field label="Their contact details" error={f("affected_contact")}><input placeholder="Enter their phone number or email" value={v.affected_contact as string} onChange={set("affected_contact")} /></Field>
        </div>
      )}

      </section>
      <section className="form-section" aria-labelledby="complaint-heading">
      <div className="complaint-section-heading"><span className="form-section-icon"><Icon name="complaint" size={23} /></span><div><span className="form-section-step">SECTION 02</span><h2 id="complaint-heading">{t("Your complaint", "Complaint details")}</h2><p className="section-description">{t("Select the division responsible for your complaint and tell us what happened.", "Select the responsible division and record what the complainant reported.")}</p></div></div>
      <div className="row">
        <Field label="Division" required error={f("division")}>
          <select required value={v.division as string} onChange={set("division")}>
            <option value="">Select a division</option>
            {meta.divisions.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <Field label="Date of incident" error={f("incident_date")}><input type="date" max={new Date().toISOString().slice(0, 10)} value={v.incident_date as string} onChange={set("incident_date")} /></Field>
      </div>
      <Field label="Subject" required error={f("subject")}><input required maxLength={200} placeholder={t("Briefly summarize your complaint", "Briefly summarise the complaint")} value={v.subject as string} onChange={set("subject")} /></Field>
      <Field label="Describe the complaint in detail" required error={f("description")}><textarea required rows={7} placeholder={t("Describe what happened, when it happened, and any steps you have already taken to resolve it.", "Record what the complainant reported: what happened, when, and any steps already taken.")} value={v.description as string} onChange={set("description")} /></Field>
      <Field label={t("Anything else we should know?", "Additional notes")}><textarea rows={3} placeholder={t("Add any other information that may help us review your complaint (optional).", "Add any other notes that may help investigate (optional).")} value={v.additional_info as string} onChange={set("additional_info")} /></Field>

      </section>
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
      <button className="btn" disabled={busy}><Icon name="send" />{busy ? "Submitting…" : offline ? "Register complaint" : "Submit complaint"}</button>
      </div>
    </form>
  );
}
