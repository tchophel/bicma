import { useEffect, useState, type CSSProperties } from "react";
import "../styles/WalkingMascot.css";

/** The BICMA mascot walks along the top of the progress tracker to the current stage, then stands there.
 *  While he moves the animated walking cycle plays (mascot-walk.webp); once he arrives a still frame is shown.
 *  `stage` is the step he walks to (0-based); `steps` is how many steps the tracker has. */
export function WalkingMascot({ stage, steps = 3, done = false, repeat = false, durationMs = 7000, speech, speechStatus }: { stage: number; steps?: number; done?: boolean; repeat?: boolean; durationMs?: number; speech?: string; speechStatus?: string }) {
  const [at, setAt] = useState(0);        // 0..1 along the tracker
  const [walking, setWalking] = useState(false);
  const target = (Math.min(stage, steps - 1) + 0.5) / steps;  // centre of the step's column
  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setAt(target); setWalking(false); return; }
    if (repeat) { setAt(target); setWalking(true); return; }
    let firstFrame = 0;
    let secondFrame = 0;
    let arrivalTimer: ReturnType<typeof setTimeout>;
    let repeatTimer: ReturnType<typeof setTimeout>;
    function walk() {
      setWalking(false);
      setAt(0.5 / steps);
      firstFrame = requestAnimationFrame(() => {
        secondFrame = requestAnimationFrame(() => { setWalking(true); setAt(target); });
      });
      arrivalTimer = setTimeout(() => {
        setWalking(false);
        if (repeat) repeatTimer = setTimeout(walk, 2400);
      }, durationMs + 100);
    }
    walk();
    return () => { cancelAnimationFrame(firstFrame); cancelAnimationFrame(secondFrame); clearTimeout(arrivalTimer); clearTimeout(repeatTimer); };
  }, [target, steps, repeat, durationMs]);
  const walkerClass = `walker ${walking ? "walking" : done ? "arrived done" : "arrived"}${repeat && walking ? " walker-repeating" : ""}`;
  const motionStyle = { left: `${at * 100}%`, transitionDuration: walking ? `${durationMs}ms` : "0ms", "--walker-start": `${0.5 / steps * 100}%`, "--walker-end": `${target * 100}%`, "--walker-cycle": `${durationMs + 2400}ms` } as CSSProperties;
  const imageSource = walking ? "/mascot-walk.webp" : "/mascot-stand.png";
  const arrive = (e: React.TransitionEvent) => { if (!repeat && e.propertyName === "left") setWalking(false); };
  return (
    <div className={`walker-lane${speech ? " walker-lane-speaking" : ""}`} aria-hidden="true">
      {speech ? <div className={`${walkerClass} walker-with-speech`} style={motionStyle} onTransitionEnd={arrive}>
        {!walking && <span data-status={speechStatus} className={`walker-speech${done ? " walker-speech-done" : ""}`}>{speech}</span>}
        <img className="walker-portrait" src={imageSource} alt="" />
      </div> : <img src={imageSource} alt="" className={walkerClass} style={motionStyle} onTransitionEnd={arrive} />}
    </div>
  );
}
