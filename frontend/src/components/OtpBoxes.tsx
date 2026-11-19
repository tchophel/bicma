import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";
import "../styles/OtpBoxes.css";

/** A one-time code entered in separate boxes: one digit each, auto-advance, backspace goes back, paste fills them all. */
export function OtpBoxes({ value, onChange, length = 6, label = "One-time code", autoFocus = false, invalid = false }: {
  value: string; onChange: (v: string) => void; length?: number; label?: string; autoFocus?: boolean; invalid?: boolean;
}) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const digits = Array.from({ length }, (_, i) => value[i] ?? "");
  const focus = (i: number) => refs.current[Math.max(0, Math.min(length - 1, i))]?.focus();
  const set = (i: number, d: string) => {
    const next = digits.slice();
    next[i] = d;
    onChange(next.join("").slice(0, length));
  };
  function onInput(i: number, raw: string) {
    const typed = raw.replace(/\D/g, "");
    if (!typed) { set(i, ""); return; }
    if (typed.length > 1) {  // several digits at once (autofill or fast typing): spread them from this box
      const next = digits.slice();
      typed.slice(0, length - i).split("").forEach((d, k) => { next[i + k] = d; });
      onChange(next.join("").slice(0, length));
      focus(i + typed.length);
      return;
    }
    set(i, typed);
    focus(i + 1);
  }
  function onKey(i: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !digits[i]) { e.preventDefault(); set(Math.max(0, i - 1), ""); focus(i - 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); focus(i - 1); }
    else if (e.key === "ArrowRight") { e.preventDefault(); focus(i + 1); }
  }
  function onPaste(e: ClipboardEvent<HTMLInputElement>) {
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
    if (!pasted) return;
    e.preventDefault();
    onChange(pasted);
    focus(pasted.length);
  }
  return (
    <div className="otp-boxes" role="group" aria-label={label}>
      {digits.map((d, i) => (
        <input key={i} ref={(el) => { refs.current[i] = el; }} className={invalid ? "otp-box invalid" : "otp-box"} value={d} inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"} maxLength={length} pattern="\d" aria-label={`${label}, digit ${i + 1} of ${length}`}
          autoFocus={autoFocus && i === 0} onChange={(e) => onInput(i, e.target.value)} onKeyDown={(e) => onKey(i, e)} onPaste={onPaste} onFocus={(e) => e.target.select()} />
      ))}
    </div>
  );
}
