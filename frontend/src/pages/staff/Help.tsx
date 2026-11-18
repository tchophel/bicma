import { useRef, useState, type FormEvent } from "react";
import { Loader } from "../../components/Loader";
import { api, ApiError } from "../../api";
import { useList } from "../../useList";
import type { Page } from "../../types";
import { Icon } from "../../components/Icon";
import { Field, PageHeader, PanelTitle } from "../../components/ui";
import "../../styles/Help.css";

type FAQ = { id: string; question: string; answer: string; position: number; is_active: boolean };
const blank = { question: "", answer: "", position: 0, is_active: true };

export function Help() {
  const [page, setPage] = useState(1);
  const { data, err, loading, reload } = useList<Page<FAQ>>(`/admin/faqs/?page=${page}&page_size=10`);
  const [form, setForm] = useState(blank);
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const questionInput = useRef<HTMLInputElement>(null);
  function edit(item: FAQ) {
    setEditing(item.id); setForm({ question: item.question, answer: item.answer, position: item.position, is_active: item.is_active });
    setError(""); setSuccess(""); questionInput.current?.focus();
  }
  function cancel() { setEditing(null); setForm(blank); setError(""); }
  async function save(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true); setError(""); setSuccess("");
    try {
      await api(editing ? `/admin/faqs/${editing}/` : "/admin/faqs/", { method: editing ? "PATCH" : "POST", json: form });
      setSuccess(editing ? "FAQ updated." : "FAQ added."); cancel(); reload();
    } catch (x) { setError((x as ApiError).message); }
    finally { setBusy(false); }
  }
  async function toggle(item: FAQ) {
    if (busy) return;
    setBusy(true); setError(""); setSuccess("");
    try {
      await api(`/admin/faqs/${item.id}/`, { method: "PATCH", json: { is_active: !item.is_active } });
      if (editing === item.id) setForm((old) => ({ ...old, is_active: !item.is_active }));
      setSuccess(item.is_active ? "FAQ deactivated." : "FAQ activated."); reload();
    } catch (x) { setError((x as ApiError).message); }
    finally { setBusy(false); }
  }
  return <div className="faq-admin">
    <PageHeader icon="help" title="Help & FAQ" subtitle="Add and manage answers to common complaint questions." />
    {err && <p className="error" role="alert">{err}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {success && <p className="notice" role="status">{success}</p>}
    <div className="faq-admin-grid">
      <section aria-label="Saved FAQs">
        <div className="faq-list-heading"><h2>Questions & answers</h2><span className="badge">{data?.count ?? 0} FAQs</span></div>
        {loading && <Loader label="Loading FAQs" />}
        {!loading && data?.results.length === 0 && <div className="card faq-empty"><Icon name="help" size={28} /><h3>No FAQs yet</h3><p>Add a question and answer using the form.</p></div>}
        {data?.results.map((item) => <article className={`card faq-admin-item ${!item.is_active ? "faq-inactive" : ""}`} key={item.id}>
          <div className="faq-item-meta"><span className="chip">Order {item.position}</span><span className={`badge ${item.is_active ? "ok" : "bad"}`}>{item.is_active ? "Active" : "Inactive"}</span></div>
          <h3>{item.question}</h3><p className="faq-answer">{item.answer}</p>
          <div className="faq-item-actions"><button className="btn secondary" disabled={busy} onClick={() => edit(item)} aria-label={`Edit ${item.question}`}><Icon name="edit" size={16} />Edit</button><button className="btn secondary" disabled={busy} onClick={() => toggle(item)} aria-label={`${item.is_active ? "Deactivate" : "Activate"} ${item.question}`}><Icon name="power" size={16} />{item.is_active ? "Deactivate" : "Activate"}</button></div>
        </article>)}
        <nav className="faq-pager" aria-label="FAQ pages"><button className="btn secondary" disabled={loading || busy || !data?.previous} onClick={() => setPage(page - 1)}><Icon name="left" />Previous</button><span>{page} / {Math.max(1, Math.ceil((data?.count ?? 0) / 10))}</span><button className="btn secondary" disabled={loading || busy || !data?.next} onClick={() => setPage(page + 1)}>Next<Icon name="right" /></button></nav>
      </section>
      <form className="card faq-admin-form" onSubmit={save}>
        <PanelTitle icon={editing ? "edit" : "plus"}>{editing ? "Edit FAQ" : "Add FAQ"}</PanelTitle>
        <p className="muted">Write a clear question and a helpful answer.</p>
        <fieldset disabled={busy}>
          <Field label="Question" required><input ref={questionInput} required maxLength={300} value={form.question} onChange={(e) => setForm({ ...form, question: e.target.value })} placeholder="e.g. How do I track my complaint?" /></Field>
          <Field label="Answer" required><textarea required rows={7} maxLength={10000} value={form.answer} onChange={(e) => setForm({ ...form, answer: e.target.value })} placeholder="Enter the answer…" /></Field>
          <Field label="Display order" hint="Lower numbers appear first."><input type="number" min={0} max={2147483647} step={1} required value={form.position} onChange={(e) => setForm({ ...form, position: Number(e.target.value) })} /></Field>
          <label className="faq-active-control"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />Active</label>
        </fieldset>
        <div className="faq-form-actions">{editing && <button className="btn secondary" type="button" disabled={busy} onClick={cancel}>Cancel</button>}<button className="btn" disabled={busy}><Icon name={editing ? "check" : "plus"} />{busy ? "Saving…" : editing ? "Save changes" : "Add FAQ"}</button></div>
      </form>
    </div>
  </div>;
}
