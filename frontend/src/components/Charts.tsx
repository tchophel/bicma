import { useState } from "react";
import { BHUTAN_MAP, DZONGKHAG_SHAPES } from "../data/bhutanDzongkhags";
import type { StatItem } from "../types";
import { EmptyState } from "./ui";
import "../styles/Dashboard.css";

/** Slice i of n in one hue: lighter as it goes round, so the legend (not colour alone) names each slice. */
export const sliceColor = (i: number, n: number) => `var(--chart-slice-${i}, color-mix(in srgb, var(--c-primary) ${Math.round(100 - (i * 62) / Math.max(1, n - 1))}%, white))`;

export function arc(cx: number, cy: number, r: number, from: number, to: number) {
  const pt = (a: number) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
  const [x1, y1] = pt(from), [x2, y2] = pt(to);
  return `M${cx} ${cy} L${x1.toFixed(2)} ${y1.toFixed(2)} A${r} ${r} 0 ${to - from > Math.PI ? 1 : 0} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`;
}

/** Ranked horizontal bars (all items; the list scrolls when it is long). */
export function RankBars({ items }: { items: StatItem[] }) {
  const total = items.reduce((n, i) => n + i.count, 0);
  const max = Math.max(1, ...items.map((i) => i.count));
  if (!items.length) return <EmptyState icon="chart">No data for these filters.</EmptyState>;
  return (
    <ul className="rank-list insight-bars" tabIndex={0} aria-label="Complaints, scrollable list">
      {items.map((i) => {
        const pct = total ? Math.round((i.count / total) * 100) : 0;
        return (
          <li key={i.label} className="rank-row" title={`${i.label}: ${i.count} (${pct}%)`}>
            <div className="rank-top"><span className="rank-label">{i.label}</span><span className="rank-value"><strong>{i.count}</strong><small>{pct}%</small></span></div>
            <div className="rank-track" aria-hidden="true"><div className="rank-fill" style={{ width: `${Math.max(2, (i.count / max) * 100)}%` }} /></div>
          </li>
        );
      })}
    </ul>
  );
}

const MAX_SLICES = 6;  // more slices than this cannot be told apart: the rest are grouped as "Other"

/** Pie chart with a legend that names every slice with its count and share. */
export function PieChart({ items }: { items: StatItem[] }) {
  const sorted = items.filter((i) => i.count > 0).sort((a, b) => b.count - a.count);
  const parts = sorted.length > MAX_SLICES
    ? [...sorted.slice(0, MAX_SLICES - 1), { label: "Other", count: sorted.slice(MAX_SLICES - 1).reduce((n, i) => n + i.count, 0) }]
    : sorted;
  const total = parts.reduce((n, i) => n + i.count, 0);
  if (!total) return <EmptyState icon="chart">No data for these filters.</EmptyState>;
  let angle = 0;
  return (
    <div className="trend-pie">
      <svg viewBox="0 0 200 200" role="img" aria-label={`Share of complaints: ${parts.map((p) => `${p.label} ${p.count}`).join(", ")}`}>
        {parts.length === 1
          ? <circle cx="100" cy="100" r="92" fill={sliceColor(0, 1)}><title>{`${parts[0].label}: ${parts[0].count} (100%)`}</title></circle>
          : parts.map((p, i) => {
              const from = angle; angle += (p.count / total) * Math.PI * 2;
              return <path key={p.label} d={arc(100, 100, 92, from, angle)} fill={sliceColor(i, parts.length)} stroke="var(--c-surface)" strokeWidth="2"><title>{`${p.label}: ${p.count} (${Math.round((p.count / total) * 100)}%)`}</title></path>;
            })}
      </svg>
      <ul className="pie-legend">
        {parts.map((p, i) => <li key={p.label}><span className="pie-swatch" style={{ background: sliceColor(i, parts.length) }} aria-hidden="true" /><span>{p.label}</span><strong>{p.count}</strong><small>{Math.round((p.count / total) * 100)}%</small></li>)}
      </ul>
    </div>
  );
}

const mapKey = (name: string) => name.toLowerCase().replace(/[^a-z]/g, "");

/** Map of Bhutan drawn from its Dzongkhag boundaries: each Dzongkhag is shaded by how many complaints came from it. */
export function ComplaintMap({ items }: { items: StatItem[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const counts = new Map<string, number>();
  for (const i of items) counts.set(mapKey(i.label), (counts.get(mapKey(i.label)) ?? 0) + i.count);
  const known = new Set(DZONGKHAG_SHAPES.map((d) => d.key));
  const missing = items.filter((i) => i.count > 0 && !known.has(mapKey(i.label)));
  const total = items.reduce((n, i) => n + i.count, 0);
  const max = Math.max(1, ...DZONGKHAG_SHAPES.map((d) => counts.get(d.key) ?? 0));
  const fill = (n: number) => (n ? `color-mix(in srgb, var(--chart-map-color, #1f7a46) ${Math.round(22 + 78 * (n / max))}%, white)` : "var(--chart-map-empty, #f3eee8)");  // green, whatever dashboard colour the person chose
  const shown = DZONGKHAG_SHAPES.find((d) => d.key === hover);
  const shownN = shown ? counts.get(shown.key) ?? 0 : 0;
  const tip = (n: number) => `${n} complaint${n === 1 ? "" : "s"}${total ? ` (${Math.round((n / total) * 100)}%)` : ""}`;
  return (
    <figure className="bt-map">
      <div className="bt-map-stage">
        <svg viewBox={`0 0 ${BHUTAN_MAP.width} ${BHUTAN_MAP.height}`} role="group" aria-label="Map of Bhutan by Dzongkhag, shaded by number of complaints">
          {DZONGKHAG_SHAPES.map((d) => {
            const n = counts.get(d.key) ?? 0;
            return (
              <path key={d.key} d={d.d} className={`bt-dz${hover === d.key ? " on" : ""}`} fill={fill(n)} tabIndex={0} role="img" aria-label={`${d.name}: ${tip(n)}`}
                onMouseEnter={() => setHover(d.key)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(d.key)} onBlur={() => setHover(null)} />
            );
          })}
          {DZONGKHAG_SHAPES.map((d) => (
            <text key={d.key} x={d.cx} y={d.cy} textAnchor="middle" dominantBaseline="middle" className="bt-label" pointerEvents="none">{d.name}</text>
          ))}
        </svg>
        <div className="bt-readout" aria-live="polite">{shown ? <><strong>{shown.name}</strong><span>{tip(shownN)}</span></> : <span>Hover or tab to a Dzongkhag to see its complaints.</span>}</div>
      </div>
      <figcaption className="bt-legend">
        <span>Fewer</span><span className="bt-ramp" aria-hidden="true" /><span>More</span><span className="bt-none"><i aria-hidden="true" />No complaints</span>
        {missing.length > 0 && <span className="bt-missing">Not on the map: {missing.map((i) => `${i.label} (${i.count})`).join(", ")}</span>}
      </figcaption>
    </figure>
  );
}
