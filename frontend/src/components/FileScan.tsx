import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Icon } from "./Icon";

export type ScanState = { state: "scanning" } | { state: "ok" } | { state: "blocked"; reason: string } | { state: "error" };
export const scanKey = (f: File) => `${f.name}|${f.size}|${f.lastModified}`;

/** Scans each chosen file as soon as it is picked and remembers the result. The server checks again on submit. */
export function useFileScan(files: File[]): { of: (f: File) => ScanState | undefined; scanning: boolean; blocked: boolean } {
  const [results, setResults] = useState<Record<string, ScanState>>({});
  const asked = useRef(new Set<string>());
  useEffect(() => {
    for (const f of files) {
      const key = scanKey(f);
      if (asked.current.has(key)) continue;
      asked.current.add(key);
      setResults((r) => ({ ...r, [key]: { state: "scanning" } }));
      const fd = new FormData();
      fd.append("files", f);
      api<{ results: { ok: boolean; reason: string }[] }>("/public/scan/", { form: fd })
        .then((res) => {
          const one = res.results[0];
          setResults((r) => ({ ...r, [key]: one?.ok ? { state: "ok" } : { state: "blocked", reason: one?.reason || "It cannot be uploaded." } }));
        })
        .catch(() => setResults((r) => ({ ...r, [key]: { state: "error" } })));
    }
  }, [files]);
  const states = files.map((f) => results[scanKey(f)]);
  return {
    of: (f) => results[scanKey(f)],
    scanning: states.some((s) => !s || s.state === "scanning"),
    blocked: states.some((s) => s?.state === "blocked"),
  };
}

/** The scan result shown under a file. */
export function ScanBadge({ scan }: { scan?: ScanState }) {
  if (!scan || scan.state === "scanning")
    return <span className="scan-badge scanning" role="status"><span className="scan-spin" aria-hidden="true"><Icon name="refresh" size={14} /></span>Scanning for viruses and harmful content…</span>;
  if (scan.state === "ok") return <span className="scan-badge ok" role="status"><Icon name="check" size={14} />Scanned: no threats found</span>;
  if (scan.state === "blocked") return <span className="scan-badge blocked" role="alert"><Icon name="alert" size={14} />Blocked: {scan.reason}. Remove it and choose a clean copy.</span>;
  return <span className="scan-badge unknown" role="status"><Icon name="help" size={14} />Could not scan just now. It will be checked again when you submit.</span>;
}
