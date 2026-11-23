/** Dashboard colours a signed-in user can pick on their profile. "orange" is the BICMA default (the values in tokens.css). */
export const THEMES: { key: string; label: string; primary: string; dark: string; soft: string; brand: string }[] = [
  { key: "orange", label: "Orange", primary: "#a8440a", dark: "#803007", soft: "#fff0e1", brand: "#f58220" },
  { key: "blue", label: "Blue", primary: "#1d4ed8", dark: "#1e3a8a", soft: "#e6eeff", brand: "#3b82f6" },
  { key: "green", label: "Green", primary: "#15803d", dark: "#14532d", soft: "#e3f5e9", brand: "#22c55e" },
  { key: "teal", label: "Teal", primary: "#0f766e", dark: "#134e4a", soft: "#dcf5f2", brand: "#14b8a6" },
  { key: "purple", label: "Purple", primary: "#7e22ce", dark: "#581c87", soft: "#f3e8ff", brand: "#a855f7" },
  { key: "red", label: "Red", primary: "#b91c1c", dark: "#7f1d1d", soft: "#fde8e8", brand: "#ef4444" },
  { key: "slate", label: "Slate", primary: "#334155", dark: "#1e293b", soft: "#e8edf3", brand: "#64748b" },
];

/** Sets (or, with no/unknown/default theme, clears) the colour variables on the page. */
export function applyTheme(key?: string | null) {
  const root = document.documentElement.style;
  const t = THEMES.find((x) => x.key === key);
  const vars: [string, string | undefined][] = [["--c-primary", t?.primary], ["--c-primary-dark", t?.dark], ["--c-primary-soft", t?.soft], ["--c-brand-orange", t?.brand]];
  for (const [name, value] of vars) { if (value && key !== "orange") root.setProperty(name, value); else root.removeProperty(name); }
}
