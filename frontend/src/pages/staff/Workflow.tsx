import { useEffect, useState } from "react";
import { api, ApiError } from "../../api";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/Toast";
import { PageHeader, PanelTitle } from "../../components/ui";
import { useList } from "../../useList";

interface Step { key: string; label: string; detail: string; enabled: boolean; locked: boolean }
const ORDER = ["triage", "investigation", "supervisor", "closure"];  // the only order the status rules allow

function orderOk(steps: Step[]) {
  const keys = steps.map((s) => s.key);
  return ORDER.every((k, i) => keys.indexOf(k) === i);
}

/** A flow chart of how a complaint moves with the current switches, including the side paths. */
function FlowDiagram({ steps }: { steps: Step[] }) {
  const on = (k: string) => steps.find((s) => s.key === k)?.enabled ?? true;
  const triage = on("triage"), sup = on("supervisor");
  const X = 140, W = 220, H = 50, CX = X + W / 2, SX = 405, SW = 165, GAP = 42;
  const yA = 10, yB = yA + H + GAP, yC = yB + H + GAP, yD = yC + H + GAP;
  const yE = yD + H + GAP, yF = sup ? yE + H + GAP : yE, yG = yF + H + GAP, total = yG + H + 14;
  const fill = { start: "#e8f1fb", step: "#ffffff", auto: "#e1f5e9", side: "#fff6e5", end: "#e9ecf1" };
  const box = (x: number, y: number, w: number, h: number, title: string, sub: string, tone: keyof typeof fill, dashed = false) => (
    <g key={`${x}-${y}-${title}`}>
      <rect x={x} y={y} width={w} height={h} rx={9} fill={fill[tone]} stroke="#8a94a6" strokeWidth={1.2} strokeDasharray={dashed ? "5 3" : undefined} />
      <text x={x + w / 2} y={y + h / 2 - (sub ? 3 : -4)} textAnchor="middle" fontSize={12.5} fontWeight={700} fill="#1f2937">{title}</text>
      {sub && <text x={x + w / 2} y={y + h / 2 + 12} textAnchor="middle" fontSize={10} fill="#4b5563">{sub}</text>}
    </g>
  );
  const line = (d: string, label?: { x: number; y: number; t: string; anchor?: "start" | "middle" | "end" }, dashed = false) => (
    <g key={d}>
      <path d={d} fill="none" stroke="#5b6475" strokeWidth={1.4} strokeDasharray={dashed ? "4 3" : undefined} markerEnd="url(#arr)" />
      {label && <text x={label.x} y={label.y} fontSize={9.5} fill="#5b6475" textAnchor={label.anchor ?? "middle"}>{label.t}</text>}
    </g>
  );
  const down = (y1: number, y2: number) => line(`M${CX},${y1} V${y2}`);
  return (
    <svg viewBox={`0 0 580 ${total}`} width="100%" role="img" aria-label="Flow chart of how a complaint moves from received to closed" style={{ maxWidth: 620 }}>
      <defs><marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="#5b6475" /></marker></defs>
      {box(X, yA, W, H, "Complaint received", "Portal or staff registration", "start")}
      {down(yA + H, yB)}
      {triage ? box(X, yB, W, H, "Division Head triage", "Category, priority, pick officer", "step") : box(X, yB, W, H, "Sent straight to an officer", "Automatic: fewest open cases", "auto")}
      {down(yB + H, yC)}
      {box(X, yC, W, H, "Investigating Officer", "Assigned, then Under review", "step")}
      {down(yC + H, yD)}
      {box(X, yD, W, H, "Findings submitted", "Officer proposes the outcome", "step")}
      {sup ? <>{down(yD + H, yE)}{box(X, yE, W, H, "Supervisor approval", "Optional: Division Head chooses", "step")}{down(yE + H, yF)}</> : down(yD + H, yF)}
      {box(X, yF, W, H, "Division Head closure", sup ? "Approves and closes" : "Approves and closes directly", "step")}
      {down(yF + H, yG)}
      {box(X, yG, W, H, "Closed", "Complainant sees the outcome", "end")}
      {/* side paths */}
      {triage && <>
        {line(`M${X + W},${yB + 14} H${SX}`, { x: X + W + 6, y: yB + 8, t: "refer", anchor: "start" })}{box(SX, yB - 4, SW, 36, "Another division", "Referred, then triaged there", "side")}
        {line(`M${X + W},${yB + 38} H${SX}`, { x: X + W + 6, y: yB + 50, t: "outside mandate", anchor: "start" })}{box(SX, yB + 38 - 2, SW, 30, "Closed: not in mandate", "", "side")}
      </>}
      {line(`M${X + W},${yC + 14} H${SX}`, { x: X + W + 6, y: yC + 8, t: "needs info", anchor: "start" })}
      {box(SX, yC - 4, SW, 36, "Awaiting information", "Complainant replies, back on", "side")}
      {line(`M${X},${yC + 14} H112 V${yB + 36} H${X}`, { x: 108, y: yC - 6, t: "returned", anchor: "end" }, true)}
      {sup && <>{line(`M${X + W},${yE + 25} H${SX}`, { x: X + W + 6, y: yE + 19, t: "not accepted", anchor: "start" })}{box(SX, yE + 7, SW, 36, "Returned by supervisor", "Head sends it back to officer", "side")}</>}
      {line(`M${X},${yF + 25} H88 V${yC + 38} H${X}`, { x: 84, y: yF - 6, t: "rejected", anchor: "end" }, true)}
      {line(`M${X + W},${yG + 25} H${SX}`, { x: X + W + 6, y: yG + 19, t: "reopen", anchor: "start" }, true)}
      {box(SX, yG + 7, SW, 36, "Reopened", "Back to Under review", "side", true)}
    </svg>
  );
}

export function WorkflowPage() {
  const toast = useToast();
  const { data, err, reload } = useList<{ steps: Step[] }>("/admin/workflow/");
  const [steps, setSteps] = useState<Step[]>([]);
  const [drag, setDrag] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (data) setSteps(data.steps); }, [data]);

  function move(from: number, to: number) {
    if (from === to) return;
    const next = [...steps];
    next.splice(to, 0, next.splice(from, 1)[0]);
    if (!orderOk(next)) {
      setNote("That order does not work. Triage comes first, then the Investigating Officer, then Supervisor approval, and the Division Head closes last. The card went back.");
      return;
    }
    setNote(""); setSteps(next);
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
  const triageOff = steps.some((s) => s.key === "triage" && !s.enabled);

  return (<>
    <PageHeader icon="refresh" title="Workflow" subtitle="Switch steps on or off and drag them to set how a complaint moves." />
    {err && <p className="error">{err}</p>}
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16, alignItems: "start", maxWidth: 1100 }}>
    <section className="card">
      <PanelTitle icon="complaint">Complaint steps</PanelTitle>
      <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10 }} aria-label="Workflow steps, in order">
        {steps.map((s, i) => (
          <li key={s.key} draggable onDragStart={() => setDrag(i)} onDragEnd={() => setDrag(null)}
              onDragOver={(e) => e.preventDefault()} onDrop={() => { if (drag !== null) move(drag, i); setDrag(null); }}
              style={{ display: "flex", gap: 12, alignItems: "center", padding: "12px 14px", border: "1px solid var(--line, #d6dbe3)", borderRadius: 10, background: "var(--surface, #fff)", opacity: s.enabled ? 1 : 0.55, outline: drag === i ? "2px dashed #888" : "none", cursor: "grab" }}>
            <span aria-hidden="true" title="Drag to reorder" style={{ fontSize: 20, lineHeight: 1, userSelect: "none" }}>⠿</span>
            <span style={{ fontWeight: 700, minWidth: 22 }}>{i + 1}</span>
            <div style={{ flex: 1 }}>
              <strong>{s.label}</strong>
              <div className="muted" style={{ fontSize: ".85rem" }}>{s.detail}</div>
            </div>
            <span className="row-actions" style={{ display: "flex", gap: 4 }}>
              <button type="button" className="btn secondary" aria-label={`Move ${s.label} up`} disabled={i === 0} onClick={() => move(i, i - 1)}>↑</button>
              <button type="button" className="btn secondary" aria-label={`Move ${s.label} down`} disabled={i === steps.length - 1} onClick={() => move(i, i + 1)}>↓</button>
            </span>
            <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input type="checkbox" checked={s.enabled} disabled={s.locked} onChange={() => toggle(s.key)} aria-label={`${s.label} is ${s.enabled ? "on" : "off"}`} />
              {s.locked ? "Always on" : s.enabled ? "On" : "Off"}
            </label>
          </li>
        ))}
      </ol>
      {note && <p className="notice" role="status" style={{ marginTop: 12 }}>{note}</p>}
      {triageOff && <p className="notice" role="status" style={{ marginTop: 12 }}><Icon name="users" size={16} /> With triage off, each new complaint goes straight to the Investigating Officer of its division who has the fewest open cases. If a division has no officer, it waits for the Division Head as before.</p>}
      <p style={{ marginTop: 16 }}><button type="button" className="btn" disabled={!dirty || saving} onClick={save}><Icon name="check" />{saving ? "Saving…" : "Save workflow"}</button></p>
    </section>
    <aside className="card" aria-label="Flow preview">
      <PanelTitle icon="division">Flow preview</PanelTitle>
      <p className="muted" style={{ marginTop: 0 }}>Updates as you change the steps. Not saved until you press Save workflow.</p>
      <FlowDiagram steps={steps} />
    </aside>
    </div>
    <p className="muted">Cases already in progress keep going from where they are. Only new complaints and the options offered to staff change.</p>
  </>);
}
