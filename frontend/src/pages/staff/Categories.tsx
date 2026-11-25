import { useConfirm } from "../../components/Confirm";
import "../../styles/Categories.css";
import { IconBtn } from "../../components/IconBtn";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/Toast";
import { useState } from "react";
import { api, ApiError } from "../../api";
import { Field, PageHeader } from "../../components/ui";
import { Modal } from "../../components/Modal";
import { type Category, type Division, type Named, type Page } from "../../types";
import { useList } from "../../useList";

export function Categories() {
  const toast = useToast();
  const ask = useConfirm();
  const { data, err, reload } = useList<Page<Category>>("/admin/categories/?page_size=200");
  const divs = useList<Page<Division>>("/admin/divisions/?page_size=200").data?.results ?? [];
  const prios = useList<Page<Named>>("/admin/priorities/?page_size=200").data?.results ?? [];
  const [addCat, setAddCat] = useState(false);
  const [subFor, setSubFor] = useState<Category | null>(null);
  const [name, setName] = useState(""); const [desc, setDesc] = useState(""); const [msg, setMsg] = useState(""); const [sub, setSub] = useState("");
  const run = async (fn: () => Promise<unknown>, success = "Saved.") => { setMsg(""); try { await fn(); reload(); toast.success(success); } catch (x) { setMsg((x as ApiError).message); toast.error((x as ApiError).message); } };
  const remove = async (kind: "categories" | "subcategories", id: string) => {
    if (!await ask("Delete")) return;
    void run(() => api(`/admin/${kind}/${id}/`, { method: "DELETE" }), "Deleted successfully.");
  };
  const patch = async (c: Category, body: Record<string, unknown>) => {
    if (!await ask("is_active" in body ? (body.is_active ? "Activate" : "Deactivate") : "Save changes")) return;
    await run(() => api(`/admin/categories/${c.id}/`, { method: "PATCH", json: body }));
  };
  const sel = (c: Category, key: "default_division" | "urban_division" | "rural_division" | "default_priority", label: string, options: Named[]) => (
    <Field label={label}><select value={c[key] ?? ""} onChange={(e) => patch(c, { [key]: e.target.value || null })}><option value="">None</option>{options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></Field>
  );
  return (<>
    <PageHeader icon="category" title="Complaint categories" subtitle="Each category maps to a division and a default priority. Changes are audited with before and after values.">
      <button type="button" className="btn" onClick={() => setAddCat(true)}><Icon name="plus" />Add category</button>
    </PageHeader>{err && <p className="error">{err}</p>}
    {data?.results.map((c) => (
      <div className="card category-card" key={c.id}>
        <div className="category-card-heading"><div className="category-card-name">
        <strong>{c.name}</strong> {!c.is_active && <span className="badge bad">Inactive</span>}</div><div className="category-card-actions">
        <IconBtn icon="power" tone={c.is_active ? "danger" : "ok"} label={`${c.is_active ? "Deactivate" : "Activate"} ${c.name}`} onClick={() => patch(c, { is_active: !c.is_active })} />
        <IconBtn icon="trash" tone="danger" label={`Delete ${c.name}`} onClick={() => remove("categories", c.id)} /></div></div>
        <div className="category-fields">
          {sel(c, "default_division", "Division", divs)}
          {sel(c, "default_priority", "Default priority", prios)}
          {sel(c, "urban_division", "Urban areas go to", divs)}
          {sel(c, "rural_division", "Rural areas go to", divs)}
        </div>
        <DescriptionEditor key={`${c.id}-${c.description ?? ""}`} text={c.description ?? ""} onSave={(text) => patch(c, { description: text })} />
        <div className="category-subcategories"><span className="category-subheading">Subcategories <span>{c.subcategories.length}</span></span><ul>{c.subcategories.map((s) => <li key={s.id}><span>{s.name}</span><button type="button" aria-label={`Delete ${s.name}`} title={`Delete ${s.name}`} onClick={() => remove("subcategories", s.id)}><Icon name="trash" size={13} /></button></li>)}</ul>
        <IconBtn icon="plus" label={`Add subcategory to ${c.name}`} onClick={() => setSubFor(c)} /></div>
      </div>))}
    <Modal open={addCat} onClose={() => setAddCat(false)} title="Add category" icon="category">
      <form onSubmit={(e) => { e.preventDefault(); void run(async () => { await api("/admin/categories/", { json: { name, description: desc } }); setName(""); setDesc(""); setAddCat(false); }); }}>
        {msg && <p className="error" role="alert">{msg}</p>}
        <Field label="Name" required><input required value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="What this category is for" hint="Optional. Shown to complainants when they point at the category. Up to 400 characters."><textarea rows={3} maxLength={400} value={desc} onChange={(e) => setDesc(e.target.value)} /></Field>
        <button type="submit" className="btn"><Icon name="plus" />Add category</button>
      </form>
    </Modal>
    <Modal open={!!subFor} onClose={() => setSubFor(null)} title={subFor ? `Add subcategory to ${subFor.name}` : ""} icon="category">
      <form onSubmit={(e) => { e.preventDefault(); void run(async () => { await api("/admin/subcategories/", { json: { category: subFor?.id, name: sub } }); setSub(""); setSubFor(null); }); }}>
        {msg && <p className="error" role="alert">{msg}</p>}
        <Field label="Subcategory name" required><input required value={sub} onChange={(e) => setSub(e.target.value)} /></Field>
        <button type="submit" className="btn"><Icon name="plus" />Add subcategory</button>
      </form>
    </Modal></>);
}

/** "What this category is for": the text complainants see when they point at the category on the complaint form. */
function DescriptionEditor({ text, onSave }: { text: string; onSave: (text: string) => void }) {
  const [value, setValue] = useState(text);
  const changed = value.trim() !== text.trim();
  return (
    <div className="category-description">
      <Field label="What this category is for" hint={`Shown to complainants when they point at this category. ${value.length}/400.`}>
        <textarea rows={2} maxLength={400} value={value} placeholder="Write a short explanation for complainants." onChange={(e) => setValue(e.target.value)} />
      </Field>
      <button type="button" className="btn secondary" disabled={!changed} onClick={() => onSave(value.trim())}><Icon name="check" />Save description</button>
    </div>
  );
}
