import { useEffect, useRef } from "react";
import { Control, DivIcon, Icon, LatLngBounds, Map as LeafletMap, Marker, Polygon, Polyline, Popup, TileLayer, type LeafletMouseEvent } from "leaflet";
import { BHUTAN_BORDER } from "../data/bhutanBorder";
import { DZONGKHAG_LINES } from "../data/bhutanDzongkhagLines";
import "leaflet/dist/leaflet.css";

// Bhutan's own border: the map shows nothing else, and only places inside it can be picked
export const BHUTAN = { lat: [26.69, 28.33], lng: [88.74, 92.13] } as const;  // bounding box, also checked by the server
const BOUNDS = new LatLngBounds(BHUTAN_BORDER);
export function inBhutan(lat: number, lng: number): boolean {
  if (lat < BHUTAN.lat[0] || lat > BHUTAN.lat[1] || lng < BHUTAN.lng[0] || lng > BHUTAN.lng[1]) return false;
  let inside = false;  // ray casting against the border
  for (let i = 0, j = BHUTAN_BORDER.length - 1; i < BHUTAN_BORDER.length; j = i++) {
    const [yi, xi] = BHUTAN_BORDER[i], [yj, xj] = BHUTAN_BORDER[j];
    if (yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
const pin = new Icon({
  iconUrl: new URL("leaflet/dist/images/marker-icon.png", import.meta.url).href,
  iconRetinaUrl: new URL("leaflet/dist/images/marker-icon-2x.png", import.meta.url).href,
  shadowUrl: new URL("leaflet/dist/images/marker-shadow.png", import.meta.url).href,
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
});

/** A map of Bhutan: click to drop a marker; the marker follows the latitude / longitude boxes. */
export function MapPicker({ lat, lng, onPick }: { lat: string; lng: string; onPick: (lat: string, lng: string) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const marker = useRef<Marker | null>(null);
  const cb = useRef(onPick);
  cb.current = onPick;

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = new LeafletMap(el.current, { maxBounds: BOUNDS.pad(0.7), maxBoundsViscosity: 0.8, zoomSnap: 0.05, zoomDelta: 0.5 });
    m.fitBounds(BOUNDS, { padding: [0, 0], animate: false });  // opens at 100%: the whole country fills the frame
    const home = { center: m.getCenter(), zoom: m.getZoom() };
    m.setMinZoom(m.getZoom() - 1.5);  // zoom out a little to see the neighbouring countries
    // "reset view": back to the 100% view after zooming or panning
    const reset = new Control({ position: "topleft" });
    reset.onAdd = () => {
      const box = document.createElement("div");
      box.className = "leaflet-bar map-reset";
      const b = document.createElement("a");
      b.href = "#"; b.title = "Reset to the full view of Bhutan"; b.setAttribute("role", "button"); b.setAttribute("aria-label", "Reset to the full view of Bhutan"); b.textContent = "\u2316";
      b.onclick = (e) => { e.preventDefault(); e.stopPropagation(); m.setView(home.center, home.zoom, { animate: true }); };
      box.appendChild(b);
      return box;
    };
    reset.addTo(m);
    // free base maps (no key): satellite by default; light, streets and topographic on the switcher
    const esri = (name: string, maxZoom: number) => new TileLayer(`https://server.arcgisonline.com/ArcGIS/rest/services/${name}/MapServer/tile/{z}/{y}/{x}`, {
      maxZoom, attribution: "Tiles &copy; Esri",
    });
    const light = esri("Canvas/World_Light_Gray_Base", 16);  // no place names, so only the Dzongkhag names show
    const streets = esri("World_Street_Map", 19);
    const satellite = esri("World_Imagery", 18);
    const topo = esri("World_Topo_Map", 19);
    satellite.addTo(m);  // default: satellite imagery has no place names, so only the Dzongkhag names show
    new Control.Layers({ Satellite: satellite, Light: light, Streets: streets, Topographic: topo }, undefined, { position: "topright" }).addTo(m);
    m.getContainer().classList.add("on-satellite");  // Dzongkhag names turn light on satellite imagery
    m.on("baselayerchange", (e: { layer: unknown }) => { const sat = e.layer === satellite; m.getContainer().classList.toggle("on-satellite", sat); styleLines(sat); });
    m.attributionControl.addAttribution("Boundaries: OCHA ROAP / HDX 2019 via geoBoundaries (CC BY 3.0 IGO)");
    // cover everything outside Bhutan (a huge outer ring with Bhutan cut out), then draw the border line
    new Polygon([[[-85, -180], [-85, 180], [85, 180], [85, -180]], BHUTAN_BORDER], { stroke: false, fillColor: "#e9ecef", fillOpacity: 0.5, interactive: false }).addTo(m);
    // the 20 Dzongkhags: clear outlines (a light line with a dark edge shows on satellite imagery; dark lines on the light maps),
    // hover to highlight (a click still drops the marker), and their names
    const casings: Polyline[] = [], lines: Polyline[] = [];
    for (const dz of DZONGKHAG_LINES) {
      const shape = new Polygon(dz.ring, { stroke: false, fill: true, fillColor: "#ffffff", fillOpacity: 0 }).addTo(m);
      shape.on("mouseover", () => shape.setStyle({ fillOpacity: 0.18 })).on("mouseout", () => shape.setStyle({ fillOpacity: 0 }));
      const ring = [...dz.ring, dz.ring[0]];
      casings.push(new Polyline(ring, { weight: 4, opacity: 0.55, interactive: false }).addTo(m));
      lines.push(new Polyline(ring, { weight: 1.8, opacity: 1, interactive: false }).addTo(m));
      new Marker(dz.at, { icon: new DivIcon({ className: "dz-label", html: `<span>${dz.name.replace(/[<>&]/g, "")}</span>`, iconSize: [0, 0] }), interactive: false, keyboard: false }).addTo(m);
    }
    const styleLines = (onSatellite: boolean) => {
      casings.forEach((c) => c.setStyle({ color: onSatellite ? "#000000" : "#ffffff" }));
      lines.forEach((l) => l.setStyle({ color: onSatellite ? "#ffffff" : "#4a3b2e" }));
    };
    styleLines(true);
    new Polyline([...BHUTAN_BORDER, BHUTAN_BORDER[0]], { color: "#f58220", weight: 3, interactive: false }).addTo(m);
    // Neighbouring land is visible but cannot be picked: the cursor says so and a click explains why
    for (const [name, at] of [["INDIA", [26.45, 90.6]], ["CHINA (TIBET)", [28.62, 90.4]], ["INDIA", [27.95, 88.9]], ["INDIA", [27.0, 92.0]]] as [string, [number, number]][]) {
      new Marker(at, { icon: new DivIcon({ className: "country-label", html: `<span>${name}</span>`, iconSize: [0, 0] }), interactive: false, keyboard: false }).addTo(m);
    }
    m.on("mousemove", (e: LeafletMouseEvent) => m.getContainer().classList.toggle("outside-bhutan", !inBhutan(e.latlng.lat, e.latlng.lng)));
    m.on("click", (e: LeafletMouseEvent) => {
      if (inBhutan(e.latlng.lat, e.latlng.lng)) { cb.current(e.latlng.lat.toFixed(6), e.latlng.lng.toFixed(6)); return; }
      new Popup({ closeButton: false, className: "outside-popup" }).setLatLng(e.latlng).setContent("This place is outside Bhutan. Click inside the border.").openOn(m);
    });
    map.current = m;
    return () => { m.remove(); map.current = null; marker.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current, a = parseFloat(lat), b = parseFloat(lng);
    if (!m) return;
    if (Number.isFinite(a) && Number.isFinite(b) && inBhutan(a, b)) {
      const text = `Issue location<br>${a.toFixed(6)}, ${b.toFixed(6)}`;
      if (marker.current) marker.current.setLatLng([a, b]).setPopupContent(text);
      else marker.current = new Marker([a, b], { icon: pin }).addTo(m).bindPopup(text);
      marker.current.openPopup();
      m.setView([a, b], Math.max(m.getZoom(), 12));
    } else if (marker.current) { marker.current.remove(); marker.current = null; }
  }, [lat, lng]);

  return <div ref={el} role="application" aria-label="Map of Bhutan: click to mark the place of the issue" style={{ height: 360, borderRadius: 8, marginBottom: 12 }} />;
}
