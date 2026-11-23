import { useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";
import { Icon } from "./Icon";
import "../styles/EmailChips.css";

const EMAIL = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]{2,}$/;

/** Several email addresses as chips: type or paste addresses and press Enter, comma, space or leave the box to add them. */
export function EmailChips({ value, onChange, max = 5, id }: { value: string[]; onChange: (list: string[]) => void; max?: number; id?: string }) {
  const [text, setText] = useState("");
  const [problem, setProblem] = useState("");
  const input = useRef<HTMLInputElement>(null);

  function add(raw: string) {
    const parts = raw.split(/[,;\s]+/).map((p) => p.trim().toLowerCase()).filter(Boolean);
    if (!parts.length) return;
    const next = [...value];
    let bad = "";
    for (const p of parts) {
      if (!EMAIL.test(p)) { bad = p; continue; }
      if (next.includes(p)) continue;
      if (next.length >= max) { setProblem(`You can send to at most ${max} addresses at a time.`); break; }
      next.push(p);
    }
    onChange(next);
    if (bad) { setText(bad); setProblem(`"${bad.slice(0, 60)}" is not a valid email address.`); } else { setText(""); if (next.length < max) setProblem(""); }
  }
  const key = (e: KeyboardEvent<HTMLInputElement>) => {
    if (["Enter", ",", ";", " ", "Tab"].includes(e.key) && text.trim()) { if (e.key !== "Tab") e.preventDefault(); add(text); }
    else if (e.key === "Backspace" && !text && value.length) onChange(value.slice(0, -1));
  };
  const paste = (e: ClipboardEvent<HTMLInputElement>) => { const t = e.clipboardData.getData("text"); if (/[,;\s]/.test(t.trim())) { e.preventDefault(); add(t); } };

  return (
    <div className="chips" onClick={() => input.current?.focus()}>
      <ul className="chips-list" aria-label="Email addresses to send to">
        {value.map((a) => (
          <li key={a} className="chip-email"><Icon name="mail" size={13} /><span>{a}</span>
            <button type="button" aria-label={`Remove ${a}`} onClick={(e) => { e.stopPropagation(); onChange(value.filter((x) => x !== a)); }}><Icon name="close" size={13} /></button></li>
        ))}
        <li className="chips-entry">
          <input ref={input} id={id} type="email" inputMode="email" autoComplete="off" value={text} disabled={value.length >= max}
            placeholder={value.length ? (value.length >= max ? `Limit of ${max} reached` : "Add another address…") : "name@example.bt"}
            onChange={(e) => { setText(e.target.value); if (problem) setProblem(""); }} onKeyDown={key} onPaste={paste} onBlur={() => text.trim() && add(text)} aria-invalid={!!problem} />
        </li>
      </ul>
      <small className="chips-count">{value.length} of {max}</small>
      {problem && <p className="error chips-problem" role="alert">{problem}</p>}
    </div>
  );
}
