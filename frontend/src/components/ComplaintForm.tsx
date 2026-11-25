import { MapPicker, inBhutan } from "./MapPicker";
import { CategoryPicker } from "./CategoryPicker";
import { YesNoBoxes } from "./YesNoBoxes";
import { ScanBadge, useFileScan } from "./FileScan";
import { Icon } from "./Icon";
import { Modal } from "./Modal";
import { Loader } from "./Loader";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { SimilarNotice, type SimilarInfo } from "./SimilarNotice";
import type { FormDoc, FormField, FormWhen, Meta } from "../types";
import { Field, humanKb } from "./ui";
import "../styles/ComplaintForm.css";

export interface FormResult extends Partial<SimilarInfo> { reference: string; id?: string; draft?: boolean }

/** A person's name with a capital letter at the start of each word ("dechen LHAM" -> "Dechen Lham"); a word with its own mixed capitals is kept. */
const properName = (name: string) => name.split(/\s+/).filter(Boolean).map((w) => (w === w.toLowerCase() || w === w.toUpperCase() ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : w.charAt(0).toUpperCase() + w.slice(1))).join(" ");

type Values = Record<string, string | boolean>;
const ENTITY_TYPES = [["individual", "Person"], ["firm", "Firm"], ["institute", "Institute"], ["agency", "Agency"]] as const;
// Remedy Sought and Nature of Complaint come from masters in the FRD; until those masters exist these are the options offered.
const REMEDIES = ["Correction or clarification", "Apology", "Removal of the content", "Right of reply", "Compensation", "Other"];
const NATURES = ["Defamation", "Inaccurate or misleading report", "Invasion of privacy", "Hate speech or incitement", "Obscene or harmful content", "Advertising or sponsorship breach", "Other"];
const OTHER = "__other__";
const empty: Values = {
  channel: "phone", date_received: new Date().toISOString().slice(0, 10),
  complainant_type: "individual", complainant_name: "", cid: "", phone: "", email: "", confidential: false, dzongkhag: "", area_type: "",
  preferred_contact: "email", on_behalf: false, affected_name: "", affected_relationship: "", affected_contact: "",
  category: "", subcategory: "", subject: "", description: "", incident_date: "", incident_time: "",
  provider_type: "", provider: "", platform: "", already_complained: false, provider_reference: "", medium_of_publication: "",
  remedy_sought: "", website_or_social: "", additional_info: "", declaration_accepted: false, fax_number: "",
  concerned_frequency: "", publication_date: "", publication_url: "", nature_of_complaint: "",
  agency_name: "", present_address: "", geo_latitude: "", geo_longitude: "", complaining_for: "self", other_party_name: "", authorised_to_act: "",
};
let mediaIds = new Set<string>();
const isMediaCat = (id: string) => mediaIds.has(id);
const NULLABLE = ["subcategory", "category", "provider", "provider_type", "dzongkhag", "incident_date", "incident_time", "date_received", "publication_date"];

/** Used by the public portal (offline=false) and by officials registering offline complaints (offline=true). */
export function ComplaintForm({ offline, onDone }: { offline: boolean; onDone: (r: FormResult) => void }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [v, setV] = useState<Values>(empty);
  const [geoMsg, setGeoMsg] = useState("");
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [cidState, setCidState] = useState<"" | "loading" | "found" | "missing" | "unavailable">("");
  const [dups, setDups] = useState<{ id: string; reference: string; subject: string }[] | null>(null);
  const [cap, setCap] = useState<{ token: string; svg: string } | null>(null);
  const [capAnswer, setCapAnswer] = useState("");
  const [verificationOpen, setVerificationOpen] = useState(false);
  const [open, setOpen] = useState(false);
  const [already, setAlready] = useState<"" | "yes" | "no">("");
  const [remedies, setRemedies] = useState<string[]>([]);
  const [natures, setNatures] = useState<string[]>([]);
  const [otherKeys, setOtherKeys] = useState<string[]>([]);
  const [det, setDet] = useState<Record<string, string | string[]>>({});
  const [slotFiles, setSlotFiles] = useState<Record<string, File[]>>({});
  const scan = useFileScan([...files, ...Object.values(slotFiles).flat()]);  // each file is scanned as soon as it is chosen
  const [otherProvider, setOtherProvider] = useState(false);
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

  useEffect(() => { api<Meta>("/meta/").then((m) => { mediaIds = new Set(m.categories.filter((c) => m.divisions.find((d) => d.id === c.default_division)?.name.toLowerCase().startsWith("media")).map((c) => c.id)); setMeta(m); }).catch(() => setErr(new ApiError("Could not load the form. Please refresh.", 0))); }, []);

  const set = (k: string) => (e: { target: { value: string } }) =>
    setV((p) => ({ ...p, [k]: e.target.value, ...(k === "category" ? { subcategory: "", complainant_type: isMediaCat(e.target.value) ? "individual" : p.complainant_type } : {}),
            ...(k === "provider" ? { platform: meta?.providers.find((p) => p.id === e.target.value)?.name ?? "" } : {}),
      ...(k === "complainant_type" ? { cid: "", agency_name: "", complainant_name: "" } : {}) }));
  function pickProvider(value: string) {
    setOtherProvider(value === OTHER);
    setV((p) => ({ ...p, provider: value === OTHER ? "" : value, platform: value === OTHER ? "" : (meta?.providers.find((x) => x.id === value)?.name ?? "") }));
  }
  const entity = v.complainant_type as string;
  const individual = entity === "individual";
  async function lookupCid(cid: string) {
    if (!individual || !/^\d{11}$/.test(cid)) { setCidState(""); return; }
    setCidState("loading");
    try {
      const r = await api<{ full_name: string }>("/public/cid-lookup/", { json: { cid } });
      setV((p) => (p.cid === cid ? { ...p, complainant_name: properName(r.full_name) } : p));
      setCidState("found");
    } catch (x) {
      setCidState((x as ApiError).status === 404 ? "missing" : "unavailable");
    }
  }
  const onCid = (e: { target: { value: string } }) => {
    const cid = individual ? e.target.value.replace(/\D/g, "").slice(0, 11) : e.target.value.slice(0, 20);
    setV((p) => ({ ...p, cid }));
    if (individual && cid.length === 11) void lookupCid(cid); else setCidState("");
  };
  const check = (k: string) => (e: { target: { checked: boolean } }) => setV((p) => ({ ...p, [k]: e.target.checked }));
  const f = (k: string) => err?.fields[k];
  const tidyName = () => setV((p) => (p.complainant_type === "individual" && typeof p.complainant_name === "string" ? { ...p, complainant_name: properName(p.complainant_name) } : p));
  const cat = meta?.categories.find((c) => c.id === v.category);
  const spec = cat?.form ?? null;
  const division = meta?.divisions.find((d) => d.id === cat?.default_division);
  // Before submitting: how many people recently reported the same issue (same category and provider or platform). A number only.
  const [similar, setSimilar] = useState<SimilarInfo | null>(null);
  const detailProvider = spec?.fields.find((fd) => fd.type === "provider" && typeof det[fd.key] === "string" && det[fd.key])?.key;
  const checkPlatform = ((v.platform as string) || (detailProvider ? (det[detailProvider] as string) : "")).trim();
  useEffect(() => {
    if (!v.category || !(checkPlatform || v.provider || v.subcategory)) { setSimilar(null); return; }
    setSimilar(null);
    let stale = false;
    const t = setTimeout(() => {
      const q = new URLSearchParams({ category: v.category as string });
      if (v.provider) q.set("provider", v.provider as string);
      if (checkPlatform) q.set("platform", checkPlatform);
      if (v.subcategory) q.set("subcategory", v.subcategory as string);
      if (v.dzongkhag) q.set("dzongkhag", v.dzongkhag as string);  // only people in the same Dzongkhag
      api<SimilarInfo>(`/public/similar/?${q}`).then((r) => { if (!stale) setSimilar(r); }).catch(() => { if (!stale) setSimilar(null); });
    }, 600);
    return () => { stale = true; clearTimeout(t); };
  }, [v.category, v.provider, v.subcategory, v.dzongkhag, checkPlatform]);
  const similarNotice = similar && <SimilarNotice info={similar} showEmpty />;
  const dn = division?.name.toLowerCase() ?? "";
  const isMedia = dn.startsWith("media");
  const isIid = dn.startsWith("infocomm");
  const isStd = dn.startsWith("spectrum");
  const catGroups = (meta?.divisions ?? []).map((d) => ({ d, cats: (meta?.categories ?? []).filter((c) => c.default_division === d.id) })).filter((g) => g.cats.length);
  const ungrouped = (meta?.categories ?? []).filter((c) => !c.default_division);
  function toggleNature(n: string) {
    const next = natures.includes(n) ? natures.filter((x) => x !== n) : [...natures, n];
    setNatures(next);
    setV((p) => ({ ...p, nature_of_complaint: next.join("; ") }));
  }
  function toggleRemedy(r: string) {
    const next = remedies.includes(r) ? remedies.filter((x) => x !== r) : [...remedies, r];
    setRemedies(next);
    setV((p) => ({ ...p, remedy_sought: next.join("; ") }));
  }

  // BRD Form B: "Already complained to the provider?" is asked for every IID complaint (both form layouts).
  const alreadyQuestion = isIid ? (
    <>
      <Field label="Already complained to the provider?" required error={f("already_complained")}>
        <YesNoBoxes name="already" value={already === "yes" ? "Yes" : already === "no" ? "No" : ""} invalid={!!f("already_complained")}
          onChange={(x) => { setAlready(x === "Yes" ? "yes" : x === "No" ? "no" : ""); setV((p) => ({ ...p, already_complained: x === "Yes" })); }} />
      </Field>
      {already === "yes" && <Field label="Provider reference number" required error={f("provider_reference")}><input required value={v.provider_reference as string} onChange={set("provider_reference")} /></Field>}
    </>
  ) : null;

  async function submit(e: FormEvent, opts: { draft?: boolean; confirmDuplicate?: boolean } = {}) {
    e.preventDefault();
    if (busy) return;
    if (scan.blocked) { setErr(new ApiError("One of your files was blocked by the safety scan. Remove it, then try again.", 400)); return; }
    if (scan.scanning) { setErr(new ApiError("Your files are still being scanned. Please wait a moment and try again.", 400)); return; }
    if (!opts.draft && !spec && !isMedia && isIid && !already) { setErr(new ApiError("Say whether you have already complained to the provider.", 400)); return; }
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
      if (typeof val === "boolean") fd.append(k, k === "already_complained" ? (already === "yes" ? "true" : "false") : (val ? "true" : "false"));
      else if (val !== "" || !NULLABLE.includes(k)) { if (val !== "") fd.append(k, val); }
    }
    if (!offline) { fd.delete("channel"); fd.delete("date_received"); fd.append("captcha_token", cap?.token ?? ""); fd.append("captcha_answer", capAnswer); }
    if (opts.draft) fd.append("draft", "true");
    if (opts.confirmDuplicate) fd.append("confirm_duplicate", "true");
    files.forEach((f) => fd.append("files", f));
    if (spec || (cat?.extra_fields?.length ?? 0) > 0) fd.append("details", JSON.stringify(det));
    if (spec) {
      for (const [slot, list] of Object.entries(slotFiles)) list.forEach((f) => fd.append(`doc__${slot}`, f));
    }
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
  if (!meta) return err ? <p className="error" role="alert">{err.message}</p> : <Loader label="Loading the form" />;
  const shown = (w?: FormWhen): boolean => {
    if (!w) return true;
    if (w.all) return w.all.every((x) => shown(x));
    const cur = det[w.key ?? ""];
    return w.equals !== undefined ? cur === w.equals : Array.isArray(cur) && cur.includes(w.includes ?? "");
  };
  const setD = (k: string, val: string | string[]) => setDet((p) => ({ ...p, [k]: val }));
  const today = new Date().toISOString().slice(0, 10);
  const renderField = (fd: FormField) => {
    if (!shown(fd.when)) return null;
    const err = f(`details.${fd.key}`);
    const val = det[fd.key];
    if (fd.type === "checks" || fd.type === "provider_checks") {
      let options = fd.options ?? [];
      if (fd.type === "provider_checks") {  // from master data: providers of the named type, or every active provider when none carry that type
        const typeId = meta?.provider_types.find((t) => t.name === fd.provider_type)?.id;
        const all = meta?.providers ?? [];
        const typed = all.filter((p) => p.provider_type === typeId);
        options = (typed.length ? typed : all).map((p) => p.name);
      }
      const list = Array.isArray(val) ? val : [];
      return (
        <fieldset className="field complaint-choice-field" key={fd.key}>
          <legend style={{ fontWeight: 600, fontSize: ".9rem", marginBottom: 7 }}>{fd.label}{fd.required && <span className="req" aria-hidden="true"> *</span>}</legend>
          <p className="complaint-choice-help"><span>{fd.hint ?? "Select all that apply"}</span><span>{list.length ? `${list.length} selected` : ""}</span></p>
          <div className="complaint-choice-grid">
            {options.length === 0 && <span className="muted">No options yet. An administrator adds them under Master data.</span>}
            {options.map((o) => <label key={o} className={`complaint-choice${list.includes(o) ? " is-selected" : ""}${o.length > 110 ? " complaint-choice-long" : ""}`}><input type="checkbox" checked={list.includes(o)} onChange={() => setD(fd.key, list.includes(o) ? list.filter((x) => x !== o) : [...list, o])} /><span>{o}</span></label>)}
          </div>
          {err && <p className="error" role="alert">{err}</p>}
        </fieldset>
      );
    }
    // the cable provider depends on the Dzongkhag: nothing to pick until one is chosen
    if (fd.type === "provider" && fd.provider_type && !v.dzongkhag) return null;
    const text = typeof val === "string" ? val : "";
    const common = { required: fd.required, value: text };
    return (
      <Field key={fd.key} label={fd.label} required={fd.required} error={err} hint={fd.hint}>
        {fd.type === "textarea" ? <textarea rows={3} {...common} onChange={(e) => setD(fd.key, e.target.value)} />
          : fd.type === "date" ? <input type="date" max={fd.past ? today : undefined} {...common} onChange={(e) => setD(fd.key, e.target.value)} />
          : fd.type === "yesno" ? <YesNoBoxes name={fd.key} value={(val === "Yes" || val === "No" ? val : "") as "Yes" | "No" | ""} onChange={(x) => setD(fd.key, x)} invalid={!!err} />
          : fd.type === "select" ? <select {...common} onChange={(e) => setD(fd.key, e.target.value)}><option value="">Select</option>{fd.options?.map((o) => <option key={o} value={o}>{o}</option>)}</select>
          : fd.type === "provider" ? (() => {
              const typeId = fd.provider_type ? meta?.provider_types.find((t) => t.name === fd.provider_type)?.id : undefined;
              const ofType = (meta?.providers ?? []).filter((p) => p.provider_type === typeId);
              const list = (typeId && ofType.length ? ofType : meta?.providers ?? []).filter((p) => !v.dzongkhag || p.dzongkhags.length === 0 || p.dzongkhags.includes(v.dzongkhag as string));
              const other = otherKeys.includes(fd.key) || (!!text && !list.some((p) => p.name === text));
              return <>
                <select required={fd.required} value={other ? OTHER : text} onChange={(e) => {
                  if (e.target.value === OTHER) { setOtherKeys((k) => [...k, fd.key]); setD(fd.key, ""); }
                  else { setOtherKeys((k) => k.filter((x) => x !== fd.key)); setD(fd.key, e.target.value); }
                }}><option value="">Select</option>{list.map((p) => <option key={p.id} value={p.name}>{p.name}</option>)}<option value={OTHER}>Other / Not listed</option></select>
                {other && <input style={{ marginTop: 8 }} required={fd.required} maxLength={150} placeholder="Type the provider name" value={text} onChange={(e) => setD(fd.key, e.target.value)} />}
              </>;
            })()
          : <input maxLength={300} {...common} onChange={(e) => setD(fd.key, e.target.value)} />}
      </Field>
    );
  };
  // Questions an Administrator added in the form builder for this category's division; shown in every layout
  const extraQuestions = (cat?.extra_fields ?? []).length > 0 ? <div className="extra-questions">{(cat?.extra_fields ?? []).map(renderField)}</div> : null;
  const renderDoc = (d: FormDoc) => {
    if (!shown(d.when) || !meta) return null;
    const list = slotFiles[d.key] ?? [];
    const must = d.required === true || d.required === "when";
    const accept = (d.image ? ["jpg", "jpeg", "png"] : meta.limits.allowed_extensions).map((x) => `.${x}`).join(",");
    return (
      <div className="supporting-documents" key={d.key}>
        <div className="supporting-documents-heading"><div className="supporting-upload-title"><span className="supporting-upload-title-icon"><Icon name="complaint" size={21} /></span><div><h3>{d.label}</h3><p>Add evidence to help us understand your complaint.</p></div></div><span>{must ? "Required" : "Optional"}</span></div>
        {(meta.limits.upload_instructions || d.hint || d.required_hint || d.optional_hint) && <div className="supporting-upload-guidance" id={`upload-instructions-${d.key}`}><Icon name="help" size={18} /><div>{meta.limits.upload_instructions && <p>{meta.limits.upload_instructions}</p>}{d.hint && <p><strong>What to upload</strong><br />{d.hint}</p>}{d.required_hint && <p className="upload-required-detail"><strong>Required <span aria-hidden="true">*</span></strong><br />{d.required_hint}</p>}{d.optional_hint && <p className="upload-optional-detail"><strong>Optional</strong><br />{d.optional_hint}</p>}</div></div>}
        <label className="supporting-documents-picker">
          <input type="file" multiple accept={accept} aria-label={d.label} aria-describedby={meta.limits.upload_instructions || d.hint || d.required_hint || d.optional_hint ? `upload-instructions-${d.key}` : undefined} aria-invalid={!!f(`doc__${d.key}`)} onChange={(e) => setSlotFiles((p) => ({ ...p, [d.key]: Array.from(e.target.files ?? []) }))} />
          <span className="supporting-documents-icon"><Icon name="plus" size={24} /></span>
          <span className="supporting-documents-copy"><strong>{d.image ? "Choose your photos" : "Choose supporting files"}</strong><span>{d.image ? "Clear photos of your complaint" : "Documents, photos, audio or video"}</span></span>
          <span className="supporting-documents-browse">Choose files</span>
        </label>
        <div className="supporting-documents-hint"><details className="supporting-file-types"><summary>Accepted file types</summary><p>{d.image ? "JPG, JPEG, PNG" : meta.limits.allowed_extensions.map((x) => x.toUpperCase()).join(", ")}</p></details><strong>Up to {meta.limits.upload_max_files} files · {humanKb(meta.limits.upload_max_kb)} each</strong></div>
        {f(`doc__${d.key}`) && <p className="error" role="alert">{f(`doc__${d.key}`)}</p>}
        {list.length > 0 && <div className="supporting-documents-selected"><p aria-live="polite">{list.length} {list.length === 1 ? "file" : "files"} selected</p><ul>{list.map((file, i) => <li key={`${file.name}-${i}`}><span className="supporting-documents-file-name"><strong>{file.name}</strong><small>{Math.ceil(file.size / 1024)} KB</small><ScanBadge scan={scan.of(file)} /></span><button type="button" aria-label={`Remove ${file.name}`} onClick={() => setSlotFiles((p) => ({ ...p, [d.key]: list.filter((_, j) => j !== i) }))}><Icon name="close" size={16} /></button></li>)}</ul></div>}
      </div>
    );
  };
  const notices = (
    <>
      {err && <p className="error" role="alert">{err.message}</p>}
      {dups && (
        <div className="notice" role="alert">
          <strong>A similar open complaint already exists.</strong>
          <ul>{dups.map((d) => <li key={d.id}><a href={`/staff/complaints/${d.id}`} target="_blank" rel="noreferrer">{d.reference}</a> — {d.subject}</li>)}</ul>
          <button type="button" className="btn secondary" disabled={busy} onClick={(e) => submit(e as unknown as FormEvent, { confirmDuplicate: true })}>Register anyway</button>
        </div>
      )}

    </>
  );
  return (
    <form onSubmit={(e) => submit(e)} className="card complaint-form" noValidate={false}>
      <p className="muted"><span className="req" style={{ color: "var(--c-accent)" }}>*</span> marks required fields.</p>
      {!open && notices}
      {offline && (
        <section className="form-section" aria-labelledby="channel-heading">
          <div className="complaint-section-heading"><span className="form-section-icon"><Icon name="send" size={23} /></span><div><span className="form-section-step">SECTION 01</span><h2 id="channel-heading">How was it received?</h2></div></div>
          <div className="row">
            <Field label="Channel" required error={f("channel")}><select required value={v.channel as string} onChange={set("channel")}>{meta.channels.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</select></Field>
            <Field label="Date received" required error={f("date_received")}><input required type="date" max={new Date().toISOString().slice(0, 10)} value={v.date_received as string} onChange={set("date_received")} /></Field>
          </div>
        </section>
      )}

      <section className="card category-summary" aria-live="polite">
        <span className="category-summary-icon"><Icon name="category" size={24} /></span>
        <div className="category-summary-copy">
          <span className="form-section-step">LET’S GET STARTED</span>
          <h2>{cat ? cat.name : "What is your complaint about?"}</h2>
          <p>{cat ? `${division?.name ?? "Division decided in triage"}` : "Choose the category that best describes your complaint to begin."}</p>
        </div>
        <p className="category-summary-intro">Share what happened and the outcome you’d like. We’ll guide you through the details.</p>
        <ol className="category-summary-journey" aria-label="Complaint submission steps"><li><span>1</span>Choose a category</li><li><span>2</span>Add your details</li><li><span>3</span>Review &amp; submit</li></ol>
        <div className="category-summary-actions">
          <button type="button" className="btn" onClick={() => setOpen(true)}><Icon name={cat ? "edit" : "complaint"} />{cat ? "Continue your complaint" : "Start complaint"}<Icon name="right" size={18} /></button>
        </div>
      </section>

      <Modal open={open} onClose={() => setOpen(false)} busy={busy || verificationOpen} wide title="What is your complaint about?" icon="category">
      {notices}
      <nav className="complaint-form-navigation" aria-label="Complaint form sections">
        {[{ id: "form-a-heading", title: "Category", icon: "category" as const }, { id: "identity-heading", title: "Your details", icon: "user" as const }, { id: "details-heading", title: "Your complaint", icon: "complaint" as const }].map((step, index) => <button key={step.id} type="button" disabled={index > 0 && !cat} onClick={() => document.getElementById(step.id)?.scrollIntoView({ block: "start", behavior: "instant" })}><span>{index + 1}</span><Icon name={step.icon} size={16} />{step.title}</button>)}
      </nav>
      <section className="form-section complaint-category-section" aria-labelledby="form-a-heading">
        <div className="complaint-section-heading"><span className="form-section-icon"><Icon name="category" size={22} /></span><div><span className="form-section-step">SECTION 01</span><h2 id="form-a-heading">Choose a category</h2></div></div>
        <p className="muted">{t("Choose the category that best fits. It decides which BICMA division handles your complaint and which form you fill in.", "Choose the category. It decides the responsible division and the form shown.")}</p>
        <div className="row">
          <Field label="Complaint category" required error={f("category")}>
            <CategoryPicker autoFocus required invalid={!!f("category")} value={v.category as string}
              groups={[...catGroups.map((g) => ({ label: g.d.name, cats: g.cats })), ...(ungrouped.length ? [{ label: "Other", cats: ungrouped }] : [])]}
              onChange={(id) => { set("category")({ target: { value: id } }); setDet({}); setSlotFiles({}); }} />
          </Field>
          <Field label="Division" hint="Filled in from the category."><input readOnly value={cat ? (division?.name ?? "Decided in triage") : ""} placeholder="Chosen from the category" /></Field>
        </div>
      </section>

      {cat && (
        <>
          {spec ? (
            <>
              <section className="form-section" aria-labelledby="identity-heading">
                <div className="complaint-section-heading"><span className="form-section-icon"><Icon name="users" size={23} /></span><div><span className="form-section-step">SECTION 02</span><h2 id="identity-heading">Your details</h2><p className="section-description">Tell us who is making this complaint and how we can contact you.</p></div></div>
                <div className="row">
                  <Field label="CID number" required={!offline} error={f("cid")} hint={cidState === "loading" ? "Looking up the name…" : cidState === "found" ? "Name filled from the citizen registry." : cidState === "missing" ? "No registry record found. Enter the name by hand." : cidState === "unavailable" ? "Registry lookup is unavailable. Enter the name by hand." : "11 digits. The name is filled in automatically."}>
                    <input required={!offline} inputMode="numeric" pattern="\d{11}" maxLength={11} placeholder="11-digit CID" value={v.cid as string} onChange={onCid} autoComplete="off" />
                  </Field>
                  <Field label={spec.division === "mcd" ? "Name of the complainant (person, firm, institute or agency)" : "Name"} required error={f("complainant_name")}>
                    <input required readOnly={cidState === "found"} placeholder={cidState === "loading" ? "Looking up…" : "Enter the name"} value={v.complainant_name as string} onChange={set("complainant_name")} onBlur={tidyName} autoComplete="name" />
                  </Field>
                  <Field label="Contact number" required={!offline} error={f("phone")} hint="8-digit Bhutan number"><input required={!offline} type="tel" pattern="(\+975)?\d{8}" autoComplete="tel" placeholder="17123456" value={v.phone as string} onChange={set("phone")} /></Field>
                  <Field label="Email" error={f("email")} hint="Optional. Used for the acknowledgement and updates."><input type="email" autoComplete="email" placeholder="you@example.com" value={v.email as string} onChange={set("email")} /></Field>
                </div>
                {spec.identity.present_address && <Field label="Present address" required error={f("present_address")}><textarea required rows={2} value={v.present_address as string} onChange={set("present_address")} /></Field>}
                {(spec.identity.location || spec.identity.complaining_for) && <div className="complaint-location-party-row">
                  {spec.identity.location && <Field label="Location (Dzongkhag)" required error={f("dzongkhag")}>
                    <select required value={v.dzongkhag as string} onChange={set("dzongkhag")}><option value="">Select Dzongkhag</option>{meta.dzongkhags.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
                  </Field>}
                  {spec.identity.complaining_for && <Field label="Complaining on behalf of" required error={f("complaining_for")}>
                    <select required value={v.complaining_for as string} onChange={set("complaining_for")}>{spec.identity.complaining_for.map(([val, label]) => <option key={val} value={val}>{label}</option>)}</select>
                  </Field>}
                </div>}
                {spec.identity.complaining_for && v.complaining_for !== "self" && spec.division === "mcd" && (
                  <fieldset className="represented-party">
                    <legend>Details of the person or organisation represented</legend>
                    <Field label="Name of the person/organisation" required error={f("other_party_name")}><input required maxLength={200} value={v.other_party_name as string} onChange={set("other_party_name")} /></Field>
                    <Field label="Relationship or designation of the complainant" required error={f("affected_relationship")} hint="For example: brother, guardian, lawyer, spokesperson, director."><input required maxLength={100} value={v.affected_relationship as string} onChange={set("affected_relationship")} /></Field>
                    <Field label="Contact details (if applicable)" error={f("affected_contact")} hint="Phone number or email of the person or organisation."><input maxLength={150} value={v.affected_contact as string} onChange={set("affected_contact")} /></Field>
                    <div className="authorised-question">
                      <span id="authorised-label" className="authorised-label">Are you authorised by the affected person or organisation to submit this complaint on their behalf? <b aria-hidden="true">*</b></span>
                      <YesNoBoxes name="authorised" labelledBy="authorised-label" value={v.authorised_to_act === "yes" ? "Yes" : v.authorised_to_act === "no" ? "No" : ""} invalid={!!f("authorised_to_act")}
                        onChange={(x) => setV((p) => ({ ...p, authorised_to_act: x === "Yes" ? "yes" : x === "No" ? "no" : "" }))} />
                      {v.authorised_to_act === "no" && <p className="muted authorised-note">You can still submit. BICMA may ask you for proof of authority before acting on the complaint.</p>}
                      {f("authorised_to_act") && <p className="error" role="alert">{f("authorised_to_act")}</p>}
                    </div>
                  </fieldset>
                )}
                {spec.identity.complaining_for && v.complaining_for !== "self" && spec.division !== "mcd" && <Field label={spec.identity.other_party_label} required error={f("other_party_name")}><input required value={v.other_party_name as string} onChange={set("other_party_name")} /></Field>}
              </section>
              <section className="form-section complaint-details" aria-labelledby="details-heading">
                <div className="complaint-section-heading"><span className="form-section-icon"><Icon name="complaint" size={23} /></span><div><span className="form-section-step">SECTION 03</span><h2 id="details-heading">Your complaint</h2><p className="section-description">Share the details and supporting evidence. Submission date and time are recorded automatically.</p></div></div>
                {spec.fields.map(renderField)}
                {extraQuestions}
                {alreadyQuestion}
                {spec.description && <Field label={spec.description.label} required={spec.description.required} error={f("description")}><textarea required={spec.description.required} rows={5} value={v.description as string} onChange={set("description")} /></Field>}
                {similarNotice}
                {spec.geo && <>
                <div className="row">
                  <Field label="Geo-coordinate of issue area: latitude" error={f("geo_latitude")} hint="Optional. Inside Bhutan: 26.69 to 28.33, e.g. 27.472800."><input type="number" step="any" min="26.69" max="28.33" title="A latitude inside Bhutan: 26.69 to 28.33" placeholder="27.472800" value={v.geo_latitude as string} onChange={set("geo_latitude")} /></Field>
                  <Field label="Geo-coordinate of issue area: longitude" error={f("geo_longitude")} hint="Optional. Inside Bhutan: 88.74 to 92.13, e.g. 89.639000."><input type="number" step="any" min="88.74" max="92.13" title="A longitude inside Bhutan: 88.74 to 92.13" placeholder="89.639000" value={v.geo_longitude as string} onChange={set("geo_longitude")} /></Field>
                </div>
                {typeof navigator !== "undefined" && "geolocation" in navigator && (
                  <p><button type="button" className="btn secondary" onClick={() => navigator.geolocation.getCurrentPosition(
                    (pos) => {
                      const { latitude: a, longitude: b } = pos.coords;
                      if (!inBhutan(a, b)) { setGeoMsg("Your current location is outside Bhutan. Click the place of the issue on the map instead."); return; }
                      setGeoMsg(""); setV((p) => ({ ...p, geo_latitude: a.toFixed(6), geo_longitude: b.toFixed(6) }));
                    },
                    () => setGeoMsg("Could not read your location. Click the place of the issue on the map instead."), { enableHighAccuracy: true, timeout: 10000 })}>Use my current location</button> <span className="muted">Only if you are at the place of the issue. Bhutan only.</span>{geoMsg && <span className="error" role="alert" style={{ display: "block" }}>{geoMsg}</span>}</p>
                )}
                <MapPicker lat={v.geo_latitude as string} lng={v.geo_longitude as string} onPick={(a, b) => setV((p) => ({ ...p, geo_latitude: a, geo_longitude: b }))} />
                </>}
                {spec.docs.map(renderDoc)}
              </section>
            </>
          ) : (
            <>
          <section className="form-section" aria-labelledby="identity-heading">
            <div className="complaint-section-heading"><span className="form-section-icon"><Icon name="users" size={23} /></span><div><h2 id="identity-heading">{t("About you", "Complainant")}</h2></div></div>
            <div className="row">
              {!isMedia && (
                <Field label="Entity type" required error={f("complainant_type")}>
                  <select required value={entity} onChange={set("complainant_type")}>{ENTITY_TYPES.map(([val, label]) => <option key={val} value={val}>{label}</option>)}</select>
                </Field>
              )}
              {entity !== "agency" ? (
                <Field label={individual ? "CID number" : "CID / licence number"} required={!offline} error={f("cid")} hint={!individual ? "CID or the number the organisation is registered under." : cidState === "loading" ? "Looking up the name…" : cidState === "found" ? "Name filled from the citizen registry." : cidState === "missing" ? "No registry record found. Enter the name by hand." : cidState === "unavailable" ? "Registry lookup is unavailable. Enter the name by hand." : "11 digits. The name is filled in automatically."}>
                  <input required={!offline} inputMode={individual ? "numeric" : "text"} pattern={individual ? "\\d{11}" : undefined} maxLength={individual ? 11 : 20} placeholder={individual ? "11-digit CID" : "CID or licence number"} value={v.cid as string} onChange={onCid} autoComplete="off" />
                </Field>
              ) : (
                <Field label="Agency name" required error={f("agency_name")}><input required maxLength={150} value={v.agency_name as string} onChange={set("agency_name")} /></Field>
              )}
              <Field label={entity === "individual" ? "Full name" : entity === "agency" ? "Name of complainant (contact person)" : `Name of the ${entity}`} required error={f("complainant_name")}>
                <input required readOnly={cidState === "found" && individual} placeholder={cidState === "loading" ? "Looking up…" : "Enter the name"} value={v.complainant_name as string} onChange={set("complainant_name")} onBlur={tidyName} autoComplete="name" />
              </Field>
              <Field label="Contact number" required={!offline} error={f("phone")} hint="8-digit Bhutan number"><input required={!offline} type="tel" pattern="(\+975)?\d{8}" autoComplete="tel" placeholder="17123456" value={v.phone as string} onChange={set("phone")} /></Field>
              <Field label="Email" error={f("email")} hint="Optional. Used for the acknowledgement and updates."><input type="email" autoComplete="email" placeholder="you@example.com" value={v.email as string} onChange={set("email")} /></Field>
            </div>
            {isMedia && (
              <>
                <Field label="Present address" required error={f("present_address")}><textarea required rows={2} value={v.present_address as string} onChange={set("present_address")} /></Field>
                <label className="on-behalf">
                  <input type="checkbox" checked={v.on_behalf as boolean} onChange={check("on_behalf")} />
                  <span><strong>On others’ behalf</strong><small>{t("I am submitting this complaint on behalf of another person.", "The complainant is reporting on behalf of another person.")}</small></span>
                </label>
                {v.on_behalf && (
                  <div className="row">
                    <Field label="Name of affected person" required error={f("affected_name")}><input required value={v.affected_name as string} onChange={set("affected_name")} /></Field>
                    <Field label="Relationship" required error={f("affected_relationship")}><input required value={v.affected_relationship as string} onChange={set("affected_relationship")} /></Field>
                    <Field label="Their contact details" error={f("affected_contact")}><input value={v.affected_contact as string} onChange={set("affected_contact")} /></Field>
                  </div>
                )}
              </>
            )}
          </section>

          <section className="form-section complaint-details" aria-labelledby="details-heading">
            <div className="complaint-section-heading"><span className="form-section-icon"><Icon name="complaint" size={23} /></span><div><h2 id="details-heading">Details of the complaint</h2><p className="section-description">Date and time are recorded automatically when the complaint is submitted.</p></div></div>
            {isMedia ? (
              <>
                <Field label="Title of the post, article or video published" required error={f("subject")}><input required maxLength={200} value={v.subject as string} onChange={set("subject")} /></Field>
                <div className="row">
                  <Field label="Date of publication" required error={f("publication_date")}><input type="date" required max={new Date().toISOString().slice(0, 10)} value={v.publication_date as string} onChange={set("publication_date")} /></Field>
                  <Field label="Medium of publication" required error={f("medium_of_publication")} hint="Where it was published."><input required placeholder="e.g. newspaper, TV channel, website, social media page" value={v.medium_of_publication as string} onChange={set("medium_of_publication")} /></Field>
                  <Field label="Media house / publisher" error={f("provider")} hint="Optional.">
                    <select value={otherProvider ? OTHER : (v.provider as string)} onChange={(e) => pickProvider(e.target.value)}><option value="">Select</option>{meta.providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}<option value={OTHER}>Other / Not listed</option></select>
                  </Field>
                  {otherProvider && <Field label="Name of the media house" error={f("platform")}><input value={v.platform as string} onChange={set("platform")} /></Field>}
                  <Field label="Link to the post, article or video" error={f("publication_url")}><input type="url" maxLength={500} placeholder="https://" value={v.publication_url as string} onChange={set("publication_url")} /></Field>
                </div>
                <Field label="Brief description" required error={f("description")} hint="A brief statement of the nature of the complaint."><textarea required rows={4} value={v.description as string} onChange={set("description")} /></Field>
                <fieldset className="field" style={{ border: 0, padding: 0 }}>
                  <legend style={{ fontWeight: 600, fontSize: ".9rem", marginBottom: 7 }}>Nature of complaint <span className="req" aria-hidden="true">*</span></legend>
                  <div style={{ display: "grid", gap: 8 }}>
                    {NATURES.map((n) => <label key={n} style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={natures.includes(n)} onChange={() => toggleNature(n)} />{n}</label>)}
                  </div>
                  {f("nature_of_complaint") && <p className="error" role="alert">{f("nature_of_complaint")}</p>}
                </fieldset>
                <fieldset className="field" style={{ border: 0, padding: 0 }}>
                  <legend style={{ fontWeight: 600, fontSize: ".9rem", marginBottom: 7 }}>Remedy sought <span className="req" aria-hidden="true">*</span></legend>
                  <div style={{ display: "grid", gap: 8 }}>
                    {REMEDIES.map((r) => <label key={r} style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={remedies.includes(r)} onChange={() => toggleRemedy(r)} />{r}</label>)}
                  </div>
                  {f("remedy_sought") && <p className="error" role="alert">{f("remedy_sought")}</p>}
                </fieldset>
              </>
            ) : (
              <>
                <div className="row">
                  <Field label="Location (Dzongkhag)" required error={f("dzongkhag")}>
                    <select required value={v.dzongkhag as string} onChange={set("dzongkhag")}><option value="">Select Dzongkhag</option>{meta.dzongkhags.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
                  </Field>
                  <Field label="Area type" error={f("area_type")} hint="Urban or rural."><select value={v.area_type as string} onChange={set("area_type")}><option value="">Select</option><option value="urban">Urban</option><option value="rural">Rural</option></select></Field>
                  {isStd && <Field label="Concerned frequency" error={f("concerned_frequency")} hint="Optional. Frequency or band, if known."><input maxLength={120} value={v.concerned_frequency as string} onChange={set("concerned_frequency")} /></Field>}
                </div>
                <div className="row">
                  <Field label="Concerned service provider" required={isIid} error={f("provider")} hint={isIid ? "Cable or ISP provider." : "Telecom operator or company, if known."}>
                    <select required={isIid} value={otherProvider ? OTHER : (v.provider as string)} onChange={(e) => pickProvider(e.target.value)}><option value="">Select</option>{meta.providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}<option value={OTHER}>Other / Not listed</option></select>
                  </Field>
                  {otherProvider && <Field label="Name of the provider" required error={f("platform")} hint="The Division Head confirms it in triage."><input required value={v.platform as string} onChange={set("platform")} /></Field>}
                  {alreadyQuestion}
                </div>
                {extraQuestions}
                <Field label="Complaint description" required error={f("description")} hint="Detailed description of the complaint."><textarea required rows={6} placeholder={t("Describe what happened and any steps you have already taken.", "Record what the complainant reported.")} value={v.description as string} onChange={set("description")} /></Field>
              </>
            )}
      <div className="supporting-documents">
        <div className="supporting-documents-heading"><div className="supporting-upload-title"><span className="supporting-upload-title-icon"><Icon name="complaint" size={21} /></span><div><h3>Supporting documents</h3><p>Add evidence to help us understand your complaint.</p></div></div><span>Optional</span></div>
        {meta.limits.upload_instructions && <div className="supporting-upload-guidance" id="upload-instructions-general"><Icon name="help" size={18} /><p>{meta.limits.upload_instructions}</p></div>}
        <label className="supporting-documents-picker">
          <input type="file" multiple accept={meta.limits.allowed_extensions.map((x) => `.${x}`).join(",")} aria-label="Choose supporting documents" aria-describedby={`supporting-documents-hint${meta.limits.upload_instructions ? " upload-instructions-general" : ""}`} aria-invalid={!!f("files")} onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
          <span className="supporting-documents-icon"><Icon name="plus" size={24} /></span>
          <span className="supporting-documents-copy"><strong>Upload supporting files</strong><span>Choose documents, photos or recordings for your complaint.</span></span>
          <span className="supporting-documents-browse">Choose files</span>
        </label>
        <div className="supporting-documents-hint" id="supporting-documents-hint"><details className="supporting-file-types"><summary>Accepted file types</summary><p>{meta.limits.allowed_extensions.map((x) => x.toUpperCase()).join(", ")}</p></details><strong>Up to {meta.limits.upload_max_files} files · {humanKb(meta.limits.upload_max_kb)} each</strong></div>
        {f("files") && <p className="error" role="alert">{f("files")}</p>}
        {files.length > 0 && <div className="supporting-documents-selected"><p aria-live="polite">{files.length} {files.length === 1 ? "file" : "files"} selected</p><ul>{files.map((file, index) => <li key={`${file.name}-${index}`}><span className="supporting-documents-file-icon"><Icon name="complaint" size={20} /></span><span className="supporting-documents-file-name"><strong>{file.name}</strong><small>{Math.ceil(file.size / 1024)} KB</small><ScanBadge scan={scan.of(file)} /></span><button type="button" aria-label={`Remove ${file.name}`} onClick={() => setFiles((current) => current.filter((_, i) => i !== index))}><Icon name="close" size={16} /></button></li>)}</ul></div>}
      </div>
          </section>
            </>
          )}

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
            {cap ? <img className="captcha-img" alt="Verification characters" src={`data:image/svg+xml;utf8,${encodeURIComponent(cap.svg)}`} width={170} height={60} /> : <div className="captcha-img captcha-loading"><Loader size={40} block={false} label="Loading the image" /></div>}
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
        <button type="submit" className="btn" disabled={busy}><Icon name="send" />{busy ? "Submitting…" : offline ? "Register complaint" : "Submit complaint"}</button>
      </div>
        </>
      )}
      </Modal>
    </form>
  );
}
