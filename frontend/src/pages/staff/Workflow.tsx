import { useEffect, useState } from "react";
import { api, ApiError } from "../../api";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/Toast";
import { PageHeader, PanelTitle } from "../../components/ui";
import { useList } from "../../useList";
import "../../styles/MasterTheme.css";

interface Step { key: string; label: string; detail: string; enabled: boolean; locked: boolean }
/** Why an arrangement cannot work ("" when it can). Mirrors the server rule in backend/core/workflowconfig.py. */
function orderError(steps: Step[]): string {
  const keys = steps.map((s) => s.key), at = (k: string) => keys.indexOf(k);
  if (at("closure") !== keys.length - 1) return "Division Head closure stays last: only the Division Head can close a case.";
  if (at("supervisor") < at("investigation")) return "Supervisor approval needs the officer's findings, so it comes after the Investigating Officer.";
  if (at("supervisor") < at("triage")) return "Supervisor approval comes after triage, because the Division Head sets the category and priority first.";
  return "";
}

/** The plain-language effect of an arrangement. */
function summary(steps: Step[]) {
  const on = (k: string) => steps.find((s) => s.key === k)?.enabled ?? true;
  const keys = steps.map((s) => s.key);
  const officerFirst = on("triage") && keys.indexOf("investigation") < keys.indexOf("triage");
  return {
    "New complaint": !on("triage")
      ? "Goes straight to the Investigating Officer with the fewest open cases. There is no Division Head triage."
      : officerFirst
        ? "Goes straight to the Investigating Officer with the fewest open cases. The Division Head confirms triage afterwards and can reassign."
        : "Waits in Received. The Division Head triages it and picks the officer.",
    "Officer submits findings": on("supervisor")
      ? "The Division Head may send them to the Supervisor before closing."
      : "The Division Head approves and closes directly.",
    "Closing": "Always the Division Head, always last.",
  } as Record<string, string>;
}

/** A flow chart of how a complaint moves in the arranged order, including the side paths. */
function FlowDiagram({ steps }: { steps: Step[] }) {
  const on = (k: string) => steps.find((s) => s.key === k)?.enabled ?? true;
  const keys = steps.map((s) => s.key);
  const triage = on("triage"), sup = on("supervisor");
  const officerFirst = triage && keys.indexOf("investigation") < keys.indexOf("triage");
  type Tone = "start" | "step" | "auto" | "end";
  const nodes: { id: string; title: string; sub: string; tone: Tone }[] = [{ id: "recv", title: "Complaint received", sub: "Portal or staff registration", tone: "start" }];
  const auto = { id: "auto", title: "Sent straight to an officer", sub: "Automatic: fewest open cases", tone: "auto" as Tone };
  const officer = { id: "officer", title: "Investigating Officer", sub: "Assigned, then Under review", tone: "step" as Tone };
  if (!triage) nodes.push(auto, officer);
  else if (!officerFirst) nodes.push({ id: "triage", title: "Division Head triage", sub: "Category, priority, pick officer", tone: "step" }, officer);
  else nodes.push(auto, officer, { id: "triage", title: "Division Head triage", sub: "Confirms category and priority; can reassign", tone: "step" });
  nodes.push({ id: "found", title: "Findings submitted", sub: "Officer proposes the outcome", tone: "step" });
  if (sup) nodes.push({ id: "sup", title: "Supervisor approval", sub: "Optional: Division Head chooses", tone: "step" });
  nodes.push({ id: "close", title: "Division Head closure", sub: sup ? "Approves and closes" : "Approves and closes directly", tone: "step" },
             { id: "closed", title: "Closed", sub: "Complainant sees the outcome", tone: "end" });
  const X = 140, W = 220, H = 50, CX = X + W / 2, SX = 460, SW = 165, GAP = 42;
  const y = (id: string) => 10 + nodes.findIndex((n) => n.id === id) * (H + GAP);
  const total = 10 + nodes.length * (H + GAP) - GAP + 14;
  const fill = { start: "#e8f1fb", step: "#ffffff", auto: "#e1f5e9", side: "#fff6e5", end: "#e9ecf1" };
  const box = (x: number, yy: number, w: number, h: number, title: string, sub: string, tone: keyof typeof fill, dashed = false) => (
    <g key={`${x}-${yy}-${title}`}>
      <rect x={x} y={yy} width={w} height={h} rx={9} fill={fill[tone]} stroke="#8a94a6" strokeWidth={1.2} strokeDasharray={dashed ? "5 3" : undefined} />
      <text x={x + w / 2} y={yy + h / 2 - (sub ? 3 : -4)} textAnchor="middle" fontSize={12.5} fontWeight={700} fill="#1f2937">{title}</text>
      {sub && <text x={x + w / 2} y={yy + h / 2 + 12} textAnchor="middle" fontSize={10} fill="#4b5563">{sub}</text>}
    </g>
  );
  const line = (d: string, label?: { x: number; y: number; t: string; anchor?: "start" | "middle" | "end" }, dashed = false) => (
    <g key={d}>
      <path d={d} fill="none" stroke="#5b6475" strokeWidth={1.4} strokeDasharray={dashed ? "4 3" : undefined} markerEnd="url(#arr)" />
      {label && <text x={label.x} y={label.y} fontSize={9.5} fill="#5b6475" textAnchor={label.anchor ?? "middle"}>{label.t}</text>}
    </g>
  );
  const yT = y("triage"), yO = y("officer"), yClose = y("close"), yS = y("sup"), yEnd = y("closed");
  return (
    <svg viewBox={`0 0 640 ${total}`} width="100%" role="img" aria-label="Flow chart of how a complaint moves from received to closed" style={{ maxWidth: 680 }}>
      <defs><marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="#5b6475" /></marker></defs>
      {nodes.map((n, i) => box(X, 10 + i * (H + GAP), W, H, n.title, n.sub, n.tone))}
      {nodes.slice(0, -1).map((_, i) => line(`M${CX},${10 + i * (H + GAP) + H} V${10 + (i + 1) * (H + GAP)}`))}
      {triage && <>
        {line(`M${X + W},${yT + 14} H${SX}`, { x: X + W + 6, y: yT + 8, t: "refer", anchor: "start" })}{box(SX, yT - 4, SW, 36, "Another division", "Referred, then triaged there", "side")}
        {line(`M${X + W},${yT + 38} H${SX}`, { x: X + W + 6, y: yT + 50, t: "outside mandate", anchor: "start" })}{box(SX, yT + 36, SW, 30, "Closed: not in mandate", "", "side")}
      </>}
      {line(`M${X + W},${yO + 14} H${SX}`, { x: X + W + 6, y: yO + 8, t: "needs info", anchor: "start" })}
      {box(SX, yO - 4, SW, 36, "Awaiting information", "Complainant replies, back on", "side")}
      {triage && !officerFirst && line(`M${X},${yO + 14} H112 V${yT + 36} H${X}`, { x: 108, y: yO - 6, t: "returned", anchor: "end" }, true)}
      {sup && <>{line(`M${X + W},${yS + 25} H${SX}`, { x: X + W + 6, y: yS + 19, t: "not accepted", anchor: "start" })}{box(SX, yS + 7, SW, 36, "Returned by supervisor", "Head sends it back to officer", "side")}</>}
      {line(`M${X},${yClose + 25} H88 V${yO + 38} H${X}`, { x: 84, y: yClose - 6, t: "rejected", anchor: "end" }, true)}
      {line(`M${X + W},${yEnd + 25} H${SX}`, { x: X + W + 6, y: yEnd + 19, t: "reopen", anchor: "start" }, true)}
      {box(SX, yEnd + 7, SW, 36, "Reopened", "Back to Under review", "side", true)}
    </svg>
  );
}

export function WorkflowPage() {
  const toast = useToast();
  const { data, err, reload } = useList<{ steps: Step[] }>("/admin/workflow/");
  const [steps, setSteps] = useState<Step[]>([]);
  const [drag, setDrag] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (data) setSteps(data.steps); }, [data]);

  function move(from: number, to: number) {
    if (from === to) return;
    const next = [...steps];
    next.splice(to, 0, next.splice(from, 1)[0]);
    setSteps(next);  // always accepted: the page shows what it does, or why it cannot be saved
  }
  const toggle = (key: string) => setSteps((p) => p.map((s) => (s.key === key && !s.locked ? { ...s, enabled: !s.enabled } : s)));
  async function save() {
    setSaving(true);
    try {
      await api("/admin/workflow/", { method: "PUT", json: { steps: steps.map(({ key, enabled }) => ({ key, enabled })) } });
      toast.success("Workflow saved. It applies to complaints from now on."); reload();
    } catch (x) { toast.error((x as ApiError).message); }
    finally { setSaving(false); }
  }
  const dirty = JSON.stringify(steps.map((s) => [s.key, s.enabled])) !== JSON.stringify((data?.steps ?? []).map((s) => [s.key, s.enabled]));
  const error = steps.length ? orderError(steps) : "";
  const now = steps.length ? summary(steps) : {}, saved = data ? summary(data.steps) : {};
  const changes = Object.keys(now).filter((k) => now[k] !== saved[k]);

  return (<div className="master-page">
    <PageHeader icon="refresh" title="Workflow" subtitle="Switch steps on or off and drag them to set how a complaint moves." />
    {err && <p className="error">{err}</p>}
    <div style={{ display: "grid", gap: 16, maxWidth: 1100 }}>
    <section className="card">
      <PanelTitle icon="complaint">Complaint steps</PanelTitle>
      <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "stretch" }} aria-label="Workflow steps, in order">
        {steps.map((s, i) => (
          <li key={s.key} draggable onDragStart={() => setDrag(i)} onDragEnd={() => setDrag(null)}
              onDragOver={(e) => e.preventDefault()} onDrop={() => { if (drag !== null) move(drag, i); setDrag(null); }}
              style={{ flex: "1 1 200px", minWidth: 190, display: "flex", flexDirection: "column", gap: 8, padding: "12px 14px", border: "1px solid var(--line, #d6dbe3)", borderRadius: 10, background: "var(--surface, #fff)", opacity: s.enabled ? 1 : 0.55, outline: drag === i ? "2px dashed #888" : "none", cursor: "grab" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span aria-hidden="true" title="Drag to reorder" style={{ fontSize: 20, lineHeight: 1, userSelect: "none" }}>⠿</span>
              <span style={{ fontWeight: 700 }}>Step {i + 1}</span>
            </div>
            <div style={{ flex: 1 }}>
              <strong>{s.label}</strong>
              <div className="muted" style={{ fontSize: ".85rem" }}>{s.detail}</div>
            </div>
            <span className="row-actions" style={{ display: "flex", gap: 4, justifyContent: "space-between" }}>
              <button type="button" className="btn secondary" aria-label={`Move ${s.label} earlier`} disabled={i === 0} onClick={() => move(i, i - 1)}>←</button>
              <button type="button" className="btn secondary" aria-label={`Move ${s.label} later`} disabled={i === steps.length - 1} onClick={() => move(i, i + 1)}>→</button>
            </span>
            <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input type="checkbox" checked={s.enabled} disabled={s.locked} onChange={() => toggle(s.key)} aria-label={`${s.label} is ${s.enabled ? "on" : "off"}`} />
              {s.locked ? "Always on" : s.enabled ? "On" : "Off"}
            </label>
          </li>
        ))}
      </ol>
      {error && <p className="error" role="alert" style={{ marginTop: 12 }}><strong>This order can't be saved.</strong> {error} Drag a card to a different place.</p>}
      <p style={{ marginTop: 16 }}><button type="button" className="btn" disabled={!dirty || saving || !!error} onClick={save}><Icon name="check" />{saving ? "Saving…" : "Save workflow"}</button></p>
    </section>
    <aside className="card" aria-label="Flow preview">
      <PanelTitle icon="division">How it will work</PanelTitle>
      <p className="muted" style={{ marginTop: 0 }}>The chart follows the order of the cards. Not saved until you press Save workflow.</p>
      {!error && (
        <div style={{ margin: "0 0 14px", padding: "10px 14px", border: "1px solid var(--line, #d6dbe3)", borderRadius: 10 }} aria-label="What changes">
          <strong>{changes.length ? "What changes when you save" : "How complaints move now"}</strong>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            {(changes.length ? changes : Object.keys(now)).map((k) => (
              <li key={k}><strong>{k}:</strong> {changes.length && saved[k] ? <><s style={{ opacity: 0.6 }}>{saved[k]}</s> <span aria-hidden="true">→</span> </> : null}{now[k]}</li>
            ))}
          </ul>
        </div>
      )}
      {error ? <p className="notice" role="status">The chart is hidden until the order works. {error}</p>
        : <div style={{ display: "flex", justifyContent: "center" }}><FlowDiagram steps={steps} /></div>}
    </aside>
    </div>
    <p className="muted">Cases already in progress keep going from where they are. Only new complaints and the options offered to staff change.</p>
  </div>);
}
