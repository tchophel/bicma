import { Icon } from "../../components/Icon";
import { useState } from "react";
import { api, ApiError } from "../../api";
import { Field, PageHeader, PanelTitle } from "../../components/ui";
import { type Category, type Division, type Named, type Page } from "../../types";
import { useList } from "../../useList";

export function Categories() {
  const { data, err, reload } = useList<Page<Category>>("/admin/categories/?page_size=200");
  const divs = useList<Page<Division>>("/admin/divisions/?page_size=200").data?.results ?? [];
  const prios = useList<Page<Named>>("/admin/priorities/?page_size=200").data?.results ?? [];
  const [name, setName] = useState(""); const [msg, setMsg] = useState(""); const [sub, setSub] = useState<Record<string, string>>({});
  const run = async (fn: () => Promise<unknown>) => { setMsg(""); try { await fn(); reload(); } catch (x) { setMsg((x as ApiError).message); } };
  const patch = (c: Category, body: Record<string, unknown>) => run(() => api(`/admin/categories/${c.id}/`, { method: "PATCH", json: { ...body, reason: prompt("Reason for this change:") ?? "" } }));
  const sel = (c: Category, key: "default_division" | "urban_division" | "rural_division" | "default_priority", label: string, options: Named[]) => (
    <Field label={label}><select value={c[key] ?? ""} onChange={(e) => patch(c, { [key]: e.target.value || null })}><option value="">None</option>{options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></Field>
  );
  return (<>
    <PageHeader icon="category" title="Complaint categories" subtitle="Each category maps to a division and a default priority. Changes are audited with before and after values." />{err && <p className="error">{err}</p>}{msg && <p className="error" role="alert">{msg}</p>}
    {data?.results.map((c) => (
      <div className="card" key={c.id} style={{ marginBottom: 12 }}>
        <strong>{c.name}</strong> {!c.is_active && <span className="badge bad">Inactive</span>}{" "}
        <button className="btn secondary" onClick={() => patch(c, { is_active: !c.is_active })}><Icon name="power" />{c.is_active ? "Deactivate" : "Activate"}</button>
        <div className="row" style={{ marginTop: 10 }}>
          {sel(c, "default_division", "Division", divs)}
          {sel(c, "default_priority", "Default priority", prios)}
          {sel(c, "urban_division", "Urban areas go to", divs)}
          {sel(c, "rural_division", "Rural areas go to", divs)}
        </div>
        <ul>{c.subcategories.map((s) => <li key={s.id}>{s.name}</li>)}</ul>
        <form onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/admin/subcategories/", { json: { category: c.id, name: sub[c.id] } }); setSub({ ...sub, [c.id]: "" }); }); }} style={{ display: "flex", gap: 8 }}>
          <input aria-label={`New subcategory for ${c.name}`} placeholder="New subcategory" required value={sub[c.id] ?? ""} onChange={(e) => setSub({ ...sub, [c.id]: e.target.value })} />
          <button className="btn"><Icon name="plus" />Add</button>
        </form>
      </div>))}
    <PanelTitle icon="plus">Add category</PanelTitle>
    <form className="card" style={{ maxWidth: 520 }} onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/admin/categories/", { json: { name } }); setName(""); }); }}>
      <Field label="Name" required><input required value={name} onChange={(e) => setName(e.target.value)} /></Field><button className="btn"><Icon name="plus" />Add category</button>
    </form></>);
}
