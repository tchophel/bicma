import { useState } from "react";
import { Loader } from "./Loader";
import { PanelTitle } from "./ui";
import { ComplaintMap, PieChart, RankBars } from "./Charts";
import type { Dashboard } from "../types";
import { useList } from "../useList";

type By = "by_status" | "by_category" | "by_division" | "by_provider" | "by_location";
const BYS: { key: By; label: string }[] = [{ key: "by_category", label: "Category" }, { key: "by_status", label: "Status" }, { key: "by_division", label: "Division" }, { key: "by_provider", label: "Service provider" }, { key: "by_location", label: "Dzongkhag" }];

/** Bar graph, pie chart and map, all shown together for the report you generated (same period and filters). */
export function ReportInsights({ query }: { query: string }) {
  const { data, err, loading } = useList<Dashboard>(`/dashboard/?${query}`);
  const [by, setBy] = useState<By>("by_category");
  return (
    <section className="report-insights" aria-label="Report charts and map">
      <div className="insight-toolbar">
        <h2>Map and charts</h2>
        <label className="insight-by"><span>Graph and pie chart by</span><select value={by} onChange={(e) => setBy(e.target.value as By)}>{BYS.map((b) => <option key={b.key} value={b.key}>{b.label}</option>)}</select></label>
      </div>
      {err && <p className="error" role="alert">{err}</p>}
      {!data && loading && <Loader />}
      {data && (
        <div className="insight-grid">
          <section className="card insight-card insight-map-card" aria-label="Map"><PanelTitle icon="pin">Where complaints came from</PanelTitle><ComplaintMap items={data.by_location} /></section>
          <section className="card insight-card" aria-label="Bar graph"><PanelTitle icon="chart">Bar graph</PanelTitle><RankBars items={data[by]} /></section>
          <section className="card insight-card" aria-label="Pie chart"><PanelTitle icon="dashboard">Pie chart</PanelTitle><PieChart items={data[by]} /></section>
        </div>
      )}
    </section>
  );
}
