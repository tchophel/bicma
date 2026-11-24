/** A Yes / No question as two tick boxes. Ticking one unticks the other; ticking the chosen one again clears the answer. */
export function YesNoBoxes({ name, value, onChange, invalid, labelledBy }: {
  name: string; value: "Yes" | "No" | ""; onChange: (v: "Yes" | "No" | "") => void; invalid?: boolean; labelledBy?: string;
}) {
  return (
    <div className="yn-options" role="group" aria-labelledby={labelledBy} aria-invalid={invalid || undefined}>
      {(["Yes", "No"] as const).map((opt) => (
        <label key={opt} className="yn-option">
          <input type="checkbox" name={`${name}-${opt}`} checked={value === opt} onChange={() => onChange(value === opt ? "" : opt)} />
          <span>{opt}</span>
        </label>
      ))}
    </div>
  );
}
