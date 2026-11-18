import { useEffect, useState } from "react";
import { pendingCount, subscribePending } from "../api";
import "../styles/Loader.css";

/** The BICMA logo in a circle, turning clockwise. Use `size` for tables and buttons, the default for pages. */
export function Loader({ label = "Loading", size = 56, block = true }: { label?: string; size?: number; block?: boolean }) {
  return (
    <div className={block ? "loader loader-block" : "loader"} role="status" aria-live="polite">
      <span className="loader-spin" style={{ width: size, height: size }}><img src="/bicma-logo.png" alt="" width={size} height={size} /></span>
      <span className="sr-only">{label}…</span>
    </div>
  );
}

/** Small spinner shown while any request is waiting on the server (after a short delay, so quick calls don't flash). */
export function GlobalLoader() {
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const update = () => {
      if (pendingCount() > 0) { if (!timer) timer = setTimeout(() => setBusy(true), 350); }
      else { if (timer) clearTimeout(timer); timer = undefined; setBusy(false); }
    };
    const off = subscribePending(update);
    return () => { off(); if (timer) clearTimeout(timer); };
  }, []);
  if (!busy) return null;
  return <div className="global-loader" role="status" aria-label="Working"><span className="loader-spin" style={{ width: 44, height: 44 }}><img src="/bicma-logo.png" alt="" width={44} height={44} /></span></div>;
}
