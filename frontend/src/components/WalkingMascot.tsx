import { useEffect, useState } from "react";
import "../styles/WalkingMascot.css";

/** The BICMA mascot walks along the top of the progress tracker to the current stage, then stands there.
 *  While he moves the animated walking cycle plays (mascot-walk.webp); once he arrives a still frame is shown.
 *  `stage` is the step he walks to (0-based); `steps` is how many steps the tracker has. */
export function WalkingMascot({ stage, steps = 3, done = false }: { stage: number; steps?: number; done?: boolean }) {
  const [at, setAt] = useState(0);        // 0..1 along the tracker
  const [walking, setWalking] = useState(false);
  const target = (Math.min(stage, steps - 1) + 0.5) / steps;  // centre of the step's column
  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setAt(target); return; }
    setAt(0.5 / steps);                  // start above the first step
    const id = requestAnimationFrame(() => requestAnimationFrame(() => { setWalking(true); setAt(target); }));
    return () => cancelAnimationFrame(id);
  }, [target, steps]);
  return (
    <div className="walker-lane" aria-hidden="true">
      <img src={walking ? "/mascot-walk.webp" : "/mascot-stand.png"} alt="" className={`walker ${walking ? "walking" : done ? "arrived done" : "arrived"}`}
        style={{ left: `${at * 100}%` }} onTransitionEnd={(e) => { if (e.propertyName === "left") setWalking(false); }} />
    </div>
  );
}
