import { useState } from "react";
import { Loader } from "./Loader";
import { PanelTitle } from "./ui";
import { Icon } from "./Icon";
import { ComplaintMap, PieChart, RankBars } from "./Charts";
import type { Dashboard } from "../types";
import { useList } from "../useList";

type By = "by_status" | "by_category" | "by_division" | "by_provider" | "by_location";
const BYS: { key: By; label: string }[] = [{ key: "by_category", label: "Category" }, { key: "by_status", label: "Status" }, { key: "by_division", label: "Division" }, { key: "by_provider", label: "Service provider" }, { key: "by_location", label: "Dzongkhag" }];

/** Bar graph, pie chart and map, all shown together for the report you generated (same period and filters). */
export function ReportInsights({ query }: { query: string }) {
  const { data, err, loading } = useList<Dashboard>(`/dashboard/?${query}`);
  const [by, setBy] = useState<By>("by_category");
  const total = data?.by_category.reduce((sum, item) => sum + item.count, 0) ?? 0;
  const locations = data?.by_location.filter((item) => item.count > 0 && !/^(not stated|unknown|none|other)$/i.test(item.label)).length ?? 0;
  return (
    <section className="report-insights" aria-label="Report charts and map">
      {data && <div className="report-overview" aria-label="Report overview">
        <div><span className="report-overview-icon"><Icon name="complaint" size={21} /></span><div><span>Complaints in this report</span><strong>{total.toLocaleString()}</strong></div></div>
        <div><span className="report-overview-icon"><Icon name="map" size={21} /></span><div><span>Locations with reports</span><strong>{locations}</strong></div></div>
        <div><span className="report-overview-icon"><Icon name="category" size={21} /></span><div><span>Categories represented</span><strong>{data.by_category.filter((item) => item.count > 0).length}</strong></div></div>
      </div>}
      <div className="insight-toolbar">
        <div><span className="report-section-eyebrow">EXPLORE THE DATA</span><h2>Map and charts</h2></div>
        <label className="insight-by"><span>Graph and pie chart by</span><select value={by} onChange={(e) => setBy(e.target.value as By)}>{BYS.map((b) => <option key={b.key} value={b.key}>{b.label}</option>)}</select></label>
      </div>
      {err && <p className="error" role="alert">{err}</p>}
      {!data && loading && <Loader />}
      {data && (
        <div className="insight-grid">
          <section className="card insight-card insight-map-card" aria-label="Map"><PanelTitle icon="pin">Where complaints came from</PanelTitle><p className="insight-description">Explore the geographic spread of complaints across Bhutan.</p><ComplaintMap items={data.by_location} /></section>
          <section className="card insight-card" aria-label="Bar graph"><PanelTitle icon="chart">Bar graph</PanelTitle><p className="insight-description">Compare complaint volumes by {BYS.find((item) => item.key === by)?.label.toLowerCase()}.</p><RankBars items={data[by]} /></section>
          <section className="card insight-card" aria-label="Pie chart"><PanelTitle icon="dashboard">Pie chart</PanelTitle><p className="insight-description">See each group’s share of the selected complaints.</p><PieChart items={data[by]} /></section>
        </div>
      )}
    </section>
  );
}
