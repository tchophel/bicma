import { useEffect, useId, useRef, useState } from "react";
import type { Category } from "../types";
import { Icon } from "./Icon";
import "../styles/CategoryPicker.css";

type Group = { label: string; cats: Category[] };

function divisionTone(label: string) {
  const name = label.toLowerCase();
  if (name.includes("spectrum")) return "blue";
  if (name.includes("media")) return "purple";
  if (name.includes("infocomm") || name.includes("infrastructure")) return "green";
  return "slate";
}

/** Category dropdown with readable descriptions and keyboard navigation. */
export function CategoryPicker({ groups, value, onChange, required, autoFocus, invalid }: {
  groups: Group[]; value: string; onChange: (id: string) => void; required?: boolean; autoFocus?: boolean; invalid?: boolean;
}) {
  const uid = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<string>("");
  const root = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const all = groups.flatMap((g) => g.cats);
  const selected = all.find((c) => c.id === value);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);
  useEffect(() => {
    const container = list.current;
    const option = container?.querySelector<HTMLElement>(`[data-id="${CSS.escape(active)}"]`);
    if (!open || !container || !option) return;
    const bounds = container.getBoundingClientRect();
    const item = option.getBoundingClientRect();
    if (item.top < bounds.top) container.scrollTop -= bounds.top - item.top;
    else if (item.bottom > bounds.bottom) container.scrollTop += item.bottom - bounds.bottom;
  }, [active, open]);

  const openList = () => { setActive(value || all[0]?.id || ""); setOpen(true); };
  const choose = (id: string) => { onChange(id); setOpen(false); };
  const move = (delta: number) => {
    const i = all.findIndex((c) => c.id === active);
    const next = all[Math.min(all.length - 1, Math.max(0, (i < 0 ? 0 : i) + delta))];
    if (next) setActive(next.id);
  };
  function key(e: React.KeyboardEvent) {
    if (!open) { if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) { e.preventDefault(); openList(); } return; }
    if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
    else if (e.key === "Home") { e.preventDefault(); setActive(all[0]?.id ?? ""); }
    else if (e.key === "End") { e.preventDefault(); setActive(all[all.length - 1]?.id ?? ""); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (active) choose(active); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setOpen(false); }
    else if (e.key === "Tab") setOpen(false);
  }

  return (
    <div className="catpick" ref={root}>
      <button type="button" className="catpick-button" role="combobox" aria-haspopup="listbox" aria-expanded={open} aria-controls={`${uid}-list`}
        aria-activedescendant={open && active ? `${uid}-${active}` : undefined} aria-invalid={invalid || undefined} aria-required={required} autoFocus={autoFocus}
        onClick={() => (open ? setOpen(false) : openList())} onKeyDown={key}>
        <span className={selected ? "" : "catpick-placeholder"}>{selected ? selected.name : "Select a category"}</span>
        <Icon name="chev" size={16} />
      </button>
      {/* keeps the browser's own "please fill this in" check working */}
      {required && <input className="catpick-required" tabIndex={-1} aria-hidden="true" required value={value} onChange={() => {}} />}
      {open && (
        <div className="catpick-panel" onClick={(e) => e.preventDefault()}>{/* the field is inside a <label>: without this a click in the list would re-click the button */}
          <div className="catpick-list" id={`${uid}-list`} role="listbox" aria-label="Complaint categories" ref={list}>
            {groups.map((g) => (
              <div role="group" aria-label={g.label} key={g.label}>
                <div className={`catpick-group catpick-division-${divisionTone(g.label)}`}><Icon name="division" size={14} />{g.label}</div>
                {g.cats.map((c) => (
                  <div key={c.id} id={`${uid}-${c.id}`} data-id={c.id} role="option" aria-selected={c.id === value} className={`catpick-option${c.id === active ? " active" : ""}${c.id === value ? " chosen" : ""}`}
                    onMouseEnter={() => setActive(c.id)} onMouseDown={(e) => e.preventDefault()} onClick={() => choose(c.id)}>
                    <span className="catpick-option-copy"><span>{c.name}</span>{c.description && <small>{c.description}</small>}</span>{c.id === value && <Icon name="check" size={18} />}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
      {!open && selected?.description && <p className="catpick-about"><Icon name="help" size={16} /><span><strong>About this category:</strong> {selected.description}</span></p>}
    </div>
  );
}
