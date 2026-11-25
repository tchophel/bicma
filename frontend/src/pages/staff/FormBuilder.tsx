import { useMemo, useState, type FormEvent } from "react";
import { api, ApiError } from "../../api";
import { Icon } from "../../components/Icon";
import { Loader } from "../../components/Loader";
import { useToast } from "../../components/Toast";
import { EmptyState, Field } from "../../components/ui";
import type { Category, FormField, Meta, Page } from "../../types";
import { useList } from "../../useList";
import "../../styles/FormBuilder.css";

type Kind = "text" | "textarea" | "select" | "checks" | "yesno" | "date";
type Question = { id: string; key: string; division: string; division_name: string; category: string | null; category_name: string; label: string; kind: Kind; options: string[]; required: boolean; hint: string; position: number; is_active: boolean };
const KINDS: { value: Kind; label: string; icon: "edit" | "category" | "check" | "calendar" | "complaint"; sample: string }[] = [
  { value: "text", label: "Short text", icon: "edit", sample: "A single line answer" },
  { value: "textarea", label: "Long text", icon: "complaint", sample: "A longer written answer" },
  { value: "select", label: "Dropdown", icon: "category", sample: "Choose one from a list" },
  { value: "checks", label: "Tick boxes", icon: "check", sample: "Tick all that apply" },
  { value: "yesno", label: "Yes / No", icon: "check", sample: "Yes or No" },
  { value: "date", label: "Date", icon: "calendar", sample: "Pick a date" },
];

const FIELD_KIND: Record<FormField["type"], string> = { text: "Short text", textarea: "Long text", select: "Dropdown", checks: "Tick boxes", yesno: "Yes / No", date: "Date", provider: "Provider list", provider_checks: "Operator tick boxes" };

/** What the complaint form already asks for a category: the standard details of the complainant, its own questions and its documents. Read only. */
function BuiltIn({ cat }: { cat: Category }) {
  const form = cat.form;
  const who: string[] = ["Name", "CID number", "Contact number", "Email"];
  if (!form) who.push("Dzongkhag", "Locality", "Entity type");
  else {
    if (form.identity.location) who.push("Location (Dzongkhag)");
    if (form.identity.present_address) who.push("Present address");
    if (form.identity.complaining_for) who.push("Complaining on behalf of");
  }
  return (
    <div className="builtin-body">
      <div className="builtin-block">
        <h4>About the complainant <small>always asked</small></h4>
        <ul className="builtin-chips">{who.map((w) => <li key={w}>{w}</li>)}</ul>
      </div>
      <div className="builtin-block">
        <h4>Questions for this category <small>{form ? `${form.fields.length} built in` : "standard form"}</small></h4>
        {!form && <p className="muted">This category uses the standard form: the service provider, whether the complainant already complained to the provider, and a description.</p>}
        {form && form.fields.length === 0 && <p className="muted">No extra questions. The complainant describes the problem in their own words.</p>}
        {form && form.fields.length > 0 && (
          <ol className="builtin-list">
            {form.fields.map((q) => (
              <li key={q.key}>
                <strong>{q.label}</strong>
                <span className="builder-pill"><Icon name="edit" size={12} />{FIELD_KIND[q.type]}</span>
                {q.required && <span className="builder-pill req">Required</span>}
                {q.when && <span className="builder-pill soft">Only when an earlier answer applies</span>}
                {!!q.options?.length && <div className="builder-options">{q.options.slice(0, 8).map((o) => <span key={o}>{o}</span>)}{q.options.length > 8 && <span>+{q.options.length - 8} more</span>}</div>}
              </li>
            ))}
          </ol>
        )}
        {form?.description && <p className="builtin-line"><Icon name="complaint" size={15} />{form.description.label}{form.description.required ? " (required)" : ""}</p>}
      </div>
      {form && form.docs.length > 0 && (
        <div className="builtin-block">
          <h4>Documents <small>{form.docs.length}</small></h4>
          <ul className="builtin-chips docs">{form.docs.map((d) => <li key={d.key}>{d.label}{d.required === true ? " (required)" : d.required === "when" ? " (sometimes required)" : ""}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

const blank = { label: "", kind: "text" as Kind, options: "", category: "", required: false, hint: "" };

/** Administrator: add inputs, dropdowns and other questions to each division's complaint form. Nothing is deleted, only switched off. */
export function FormBuilderPage() {
  const toast = useToast();
  const meta = useList<Meta>("/meta/");
  const list = useList<Page<Question>>("/admin/form-questions/?page_size=500");
  const [division, setDivision] = useState("");
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [form, setForm] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const divisions = meta.data?.divisions ?? [];
  const current = division || divisions[0]?.id || "";
  const questions = useMemo(() => (list.data?.results ?? []).filter((q) => q.division === current).sort((a, b) => a.position - b.position), [list.data, current]);
  const categories = (meta.data?.categories ?? []).filter((c) => c.default_division === current);
  const counts = (id: string) => (list.data?.results ?? []).filter((q) => q.division === id && q.is_active).length;
  const f = (k: string) => err?.fields[k];

  function startNew() { setForm(blank); setErr(null); setEditing("new"); }
  function startEdit(q: Question) { setForm({ label: q.label, kind: q.kind, options: q.options.join("\n"), category: q.category ?? "", required: q.required, hint: q.hint }); setErr(null); setEditing(q.id); }
  async function save(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true); setErr(null);
    const body = { division: current, category: form.category || null, label: form.label, kind: form.kind, options: form.options.split("\n").map((x) => x.trim()).filter(Boolean), required: form.required, hint: form.hint };
    try {
      if (editing === "new") await api("/admin/form-questions/", { method: "POST", json: body });
      else await api(`/admin/form-questions/${editing}/`, { method: "PATCH", json: body });
      toast.success(editing === "new" ? "Question added. It appears on the complaint form now." : "Question saved.");
      setEditing(null); list.reload();
    } catch (x) { setErr(x as ApiError); } finally { setBusy(false); }
  }
  async function patch(q: Question, json: Partial<Question>, ok?: string) {
    try { await api(`/admin/form-questions/${q.id}/`, { method: "PATCH", json }); if (ok) toast.success(ok); list.reload(); }
    catch (x) { toast.error((x as ApiError).message); }
  }
  async function move(i: number, dir: -1 | 1) {
    const a = questions[i], b = questions[i + dir];
    if (!a || !b) return;
    try {
      await api(`/admin/form-questions/${a.id}/`, { method: "PATCH", json: { position: b.position } });
      await api(`/admin/form-questions/${b.id}/`, { method: "PATCH", json: { position: a.position } });
      list.reload();
    } catch (x) { toast.error((x as ApiError).message); }
  }

  const needsOptions = form.kind === "select" || form.kind === "checks";
  const optionList = form.options.split("\n").map((x) => x.trim()).filter(Boolean);
  const divName = divisions.find((d) => d.id === current)?.name ?? "";

  return (
    <div className="builder-page">
      <header className="builder-hero">
        <span className="builder-hero-icon"><Icon name="edit" size={26} /></span>
        <div><h1>Form builder</h1><p>Add inputs, dropdowns, tick boxes and more to the complaint form of each division. They appear for complainants and staff straight away.</p></div>
        <button type="button" className="builder-add" onClick={startNew} disabled={!current}><Icon name="plus" size={18} />Add question</button>
      </header>

      {(meta.err || list.err) && <p className="error" role="alert">{meta.err || list.err}</p>}
      {(meta.loading && !meta.data) && <Loader />}

      <div className="builder-tabs" role="tablist" aria-label="Division">
        {divisions.map((d) => (
          <button key={d.id} type="button" role="tab" aria-selected={d.id === current} className={d.id === current ? "on" : ""} onClick={() => { setDivision(d.id); setEditing(null); }}>
            {d.name}<span>{counts(d.id)}</span>
          </button>
        ))}
      </div>

      {editing && (
        <form className="builder-editor" onSubmit={save} aria-busy={busy} aria-labelledby="builder-editor-title">
          <h2 id="builder-editor-title"><Icon name={editing === "new" ? "plus" : "edit"} size={20} />{editing === "new" ? `New question for ${divName}` : "Edit question"}</h2>
          <div className="builder-grid">
            <div className="builder-fields">
              <Field label="Question" required error={f("label")} hint="What the complainant is asked, for example: Which operator is it?">
                <input required maxLength={200} value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} autoFocus />
              </Field>
              <div className="builder-kinds" role="radiogroup" aria-label="Answer type">
                {KINDS.map((k) => (
                  <label key={k.value} className={form.kind === k.value ? "on" : ""}>
                    <input type="radio" name="kind" value={k.value} checked={form.kind === k.value} onChange={() => setForm({ ...form, kind: k.value })} />
                    <Icon name={k.icon} size={18} /><b>{k.label}</b><small>{k.sample}</small>
                  </label>
                ))}
              </div>
              {needsOptions && (
                <Field label={form.kind === "select" ? "Dropdown choices" : "Tick box choices"} required error={f("options")} hint="One choice per line. At least two.">
                  <textarea rows={5} value={form.options} onChange={(e) => setForm({ ...form, options: e.target.value })} placeholder={"Choice one\nChoice two"} />
                </Field>
              )}
              <div className="row">
                <Field label="Asked for" error={f("category")} hint="Every category of the division, or just one.">
                  <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                    <option value="">All categories in {divName}</option>
                    {categories.map((c) => <option key={c.id} value={c.id}>{c.name} only</option>)}
                  </select>
                </Field>
                <Field label="Help text" hint="Optional line shown under the question.">
                  <input maxLength={200} value={form.hint} onChange={(e) => setForm({ ...form, hint: e.target.value })} />
                </Field>
              </div>
              <label className="builder-required"><input type="checkbox" checked={form.required} onChange={(e) => setForm({ ...form, required: e.target.checked })} />Required: the complaint cannot be sent without an answer</label>
            </div>
            <aside className="builder-preview" aria-label="What the complainant sees">
              <span className="builder-preview-tag">PREVIEW</span>
              <div className="field">
                <span>{form.label || "Your question appears here"}{form.required && <span className="req"> *</span>}</span>
                {form.kind === "text" && <input disabled placeholder="Short answer" />}
                {form.kind === "textarea" && <textarea disabled rows={3} placeholder="Longer answer" />}
                {form.kind === "date" && <input disabled type="date" />}
                {form.kind === "yesno" && <div className="builder-yesno"><span>Yes</span><span>No</span></div>}
                {form.kind === "select" && <select disabled><option>Select</option>{optionList.map((o) => <option key={o}>{o}</option>)}</select>}
                {form.kind === "checks" && <div className="builder-checks">{(optionList.length ? optionList : ["Choice one", "Choice two"]).map((o) => <label key={o}><input type="checkbox" disabled />{o}</label>)}</div>}
                {form.hint && <small>{form.hint}</small>}
              </div>
            </aside>
          </div>
          {err && !Object.keys(err.fields).length && <p className="error" role="alert">{err.message}</p>}
          <div className="builder-actions">
            <button type="submit" className="btn" disabled={busy}><Icon name={busy ? "refresh" : "check"} />{busy ? "Saving…" : editing === "new" ? "Add question" : "Save changes"}</button>
            <button type="button" className="btn secondary" onClick={() => setEditing(null)}>Cancel</button>
          </div>
        </form>
      )}

      <section className="builder-list" aria-label={`Questions for ${divName}`}>
        <h2>Questions for {divName || "this division"} <span>{questions.filter((q) => q.is_active).length} on</span></h2>
        {list.loading && !list.data && <Loader />}
        {!list.loading && questions.length === 0 && <EmptyState icon="edit">No added questions yet. Press “Add question” to add the first input or dropdown.</EmptyState>}
        <ol>
          {questions.map((q, i) => {
            const k = KINDS.find((x) => x.value === q.kind);
            return (
              <li key={q.id} className={q.is_active ? "" : "off"} style={{ "--i": Math.min(i, 12) } as React.CSSProperties}>
                <span className="builder-num">{i + 1}</span>
                <div className="builder-body">
                  <strong>{q.label}</strong>
                  <div className="builder-meta">
                    <span className="builder-pill"><Icon name={k?.icon ?? "edit"} size={13} />{k?.label}</span>
                    {q.required && <span className="builder-pill req">Required</span>}
                    <span className="builder-pill soft">{q.category ? q.category_name : "All categories"}</span>
                    {!q.is_active && <span className="builder-pill off">Switched off</span>}
                  </div>
                  {q.options.length > 0 && <div className="builder-options">{q.options.map((o) => <span key={o}>{o}</span>)}</div>}
                </div>
                <div className="builder-row-actions">
                  <button type="button" className="mv up" aria-label="Move up" title="Move up" disabled={i === 0} onClick={() => void move(i, -1)}><Icon name="left" size={16} /></button>
                  <button type="button" className="mv down" aria-label="Move down" title="Move down" disabled={i === questions.length - 1} onClick={() => void move(i, 1)}><Icon name="right" size={16} /></button>
                  <button type="button" onClick={() => startEdit(q)}><Icon name="edit" size={16} />Edit</button>
                  <button type="button" onClick={() => void patch(q, { is_active: !q.is_active }, q.is_active ? "Switched off. It is no longer asked." : "Switched on.")}>{q.is_active ? "Switch off" : "Switch on"}</button>
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="builtin" aria-label={`Built-in questions of ${divName}`}>
        <h2>Built-in questions <span>{categories.length} {categories.length === 1 ? "category" : "categories"}</span></h2>
        <p className="muted">These come with the system for each category and are shown on the complaint form together with the questions you add above. They are fixed here; the ones you add can be changed at any time.</p>
        {categories.length === 0 && <EmptyState icon="category">No categories in this division yet.</EmptyState>}
        {categories.map((c, i) => {
          const added = questions.filter((q) => q.is_active && (!q.category || q.category === c.id)).length;
          return (
            <details key={c.id} className="builtin-cat" style={{ "--i": Math.min(i, 12) } as React.CSSProperties}>
              <summary>
                <span className="builtin-name">{c.name}</span>
                <span className="builder-pill">{c.form ? `${c.form.fields.length} built in` : "Standard form"}</span>
                {added > 0 && <span className="builder-pill soft">+{added} added by you</span>}
              </summary>
              <BuiltIn cat={c} />
            </details>
          );
        })}
      </section>
    </div>
  );
}
