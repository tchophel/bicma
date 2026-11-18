import { useEffect, useRef, useState } from "react";
import { pendingCount, subscribePending } from "../api";
import "../styles/Loader.css";

/** Placeholder that holds the space while data loads. The spinner itself is the one big centred GlobalLoader below,
 *  so a screen never shows two. */
export function Loader({ label = "Loading", size = 56, block = true }: { label?: string; size?: number; block?: boolean }) {
  return (
    <div className={block ? "loader loader-block" : "loader"} role="status" aria-live="polite" style={{ minHeight: block ? Math.max(size, 120) : size }}>
      <span className="sr-only">{label}…</span>
    </div>
  );
}

/** The one loading spinner: big, in the middle of the screen, while any request is waiting on the server. It appears
 *  at once and stays at least half a second so it is always seen, and it sits in the browser's top layer so it also
 *  shows above popup dialogs. */
export function GlobalLoader() {
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let shownAt = 0;
    let hideTimer: ReturnType<typeof setTimeout> | undefined;
    const update = () => {
      if (pendingCount() > 0) {
        if (hideTimer) { clearTimeout(hideTimer); hideTimer = undefined; }
        if (!shownAt) shownAt = Date.now();
        setBusy(true);
      } else if (shownAt && !hideTimer) {
        hideTimer = setTimeout(() => { shownAt = 0; hideTimer = undefined; setBusy(false); }, Math.max(0, 500 - (Date.now() - shownAt)));
      }
    };
    const off = subscribePending(update);
    return () => { off(); if (hideTimer) clearTimeout(hideTimer); };
  }, []);
  useEffect(() => { box.current?.setAttribute("popover", "manual"); }, []);
  useEffect(() => {
    const el = box.current as (HTMLDivElement & { showPopover?: () => void; hidePopover?: () => void }) | null;
    if (!el?.showPopover) return;
    try {
      if (el.matches(":popover-open")) el.hidePopover?.();
      if (busy) el.showPopover();
    } catch { /* popover API unavailable: fixed positioning still works */ }
  }, [busy]);
  return (
    <div ref={box} className="global-loader" role="status" aria-label="Working" hidden={!busy}>
      <span className="loader-spin" style={{ width: 104, height: 104 }}><img src="/bicma-logo.png" alt="" width={104} height={104} /></span>
    </div>
  );
}
