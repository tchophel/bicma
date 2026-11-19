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

const SHOW_AFTER_MS = 400; // requests that finish sooner never show the spinner
const MIN_VISIBLE_MS = 400; // once shown it stays a moment so it doesn't flash

/** The one loading spinner: big, in the middle of the screen, shown only when the server is slow. A fast response
 *  shows nothing. It sits in the browser's top layer so it also shows above popup dialogs. */
export function GlobalLoader() {
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let shownAt = 0;
    let showTimer: ReturnType<typeof setTimeout> | undefined;
    let hideTimer: ReturnType<typeof setTimeout> | undefined;
    const update = () => {
      if (pendingCount() > 0) {
        if (hideTimer) { clearTimeout(hideTimer); hideTimer = undefined; }
        if (!shownAt && !showTimer) showTimer = setTimeout(() => { showTimer = undefined; shownAt = Date.now(); setBusy(true); }, SHOW_AFTER_MS);
      } else {
        if (showTimer) { clearTimeout(showTimer); showTimer = undefined; } // finished quickly: nothing was shown
        if (shownAt && !hideTimer) {
          hideTimer = setTimeout(() => { shownAt = 0; hideTimer = undefined; setBusy(false); }, Math.max(0, MIN_VISIBLE_MS - (Date.now() - shownAt)));
        }
      }
    };
    const off = subscribePending(update);
    return () => { off(); if (showTimer) clearTimeout(showTimer); if (hideTimer) clearTimeout(hideTimer); };
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
