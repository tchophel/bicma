import "../../styles/Categories.css";
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
  const { data, err, reload } = useList<Page<Category>>("/admin/categories/?page_size=200");
  const divs = useList<Page<Division>>("/admin/divisions/?page_size=200").data?.results ?? [];
  const prios = useList<Page<Named>>("/admin/priorities/?page_size=200").data?.results ?? [];
  const [addCat, setAddCat] = useState(false);
  const [subFor, setSubFor] = useState<Category | null>(null);
  const [name, setName] = useState(""); const [msg, setMsg] = useState(""); const [sub, setSub] = useState("");
  const run = async (fn: () => Promise<unknown>, success = "Saved.") => { setMsg(""); try { await fn(); reload(); toast.success(success); } catch (x) { setMsg((x as ApiError).message); toast.error((x as ApiError).message); } };
  const remove = (kind: "categories" | "subcategories", id: string, label: string) => {
    if (!confirm(`Delete "${label}" permanently? Items linked to complaints or subcategories cannot be deleted.`)) return;
    void run(() => api(`/admin/${kind}/${id}/`, { method: "DELETE" }), "Deleted successfully.");
  };
  const patch = (c: Category, body: Record<string, unknown>) => run(() => api(`/admin/categories/${c.id}/`, { method: "PATCH", json: { ...body, reason: prompt("Reason for this change:") ?? "" } }));
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
        <button className="btn secondary" onClick={() => patch(c, { is_active: !c.is_active })}><Icon name="power" />{c.is_active ? "Deactivate" : "Activate"}</button>
        <button type="button" className="category-delete" onClick={() => remove("categories", c.id, c.name)}>Delete</button></div></div>
        <div className="category-fields">
          {sel(c, "default_division", "Division", divs)}
          {sel(c, "default_priority", "Default priority", prios)}
          {sel(c, "urban_division", "Urban areas go to", divs)}
          {sel(c, "rural_division", "Rural areas go to", divs)}
        </div>
        <div className="category-subcategories"><span className="category-subheading">Subcategories <span>{c.subcategories.length}</span></span><ul>{c.subcategories.map((s) => <li key={s.id}><span>{s.name}</span><button type="button" aria-label={`Delete ${s.name}`} title={`Delete ${s.name}`} onClick={() => remove("subcategories", s.id, s.name)}><Icon name="close" size={13} /></button></li>)}</ul>
        <button type="button" className="btn secondary" onClick={() => setSubFor(c)}><Icon name="plus" />Add subcategory</button></div>
      </div>))}
    <Modal open={addCat} onClose={() => setAddCat(false)} title="Add category" icon="category">
      <form onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/admin/categories/", { json: { name } }); setName(""); setAddCat(false); }); }}>
        {msg && <p className="error" role="alert">{msg}</p>}
        <Field label="Name" required><input required value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <button className="btn"><Icon name="plus" />Add category</button>
      </form>
    </Modal>
    <Modal open={!!subFor} onClose={() => setSubFor(null)} title={subFor ? `Add subcategory to ${subFor.name}` : ""} icon="category">
      <form onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/admin/subcategories/", { json: { category: subFor?.id, name: sub } }); setSub(""); setSubFor(null); }); }}>
        {msg && <p className="error" role="alert">{msg}</p>}
        <Field label="Subcategory name" required><input required value={sub} onChange={(e) => setSub(e.target.value)} /></Field>
        <button className="btn"><Icon name="plus" />Add subcategory</button>
      </form>
    </Modal></>);
}
