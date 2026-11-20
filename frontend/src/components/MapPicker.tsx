import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Bhutan, roughly centred
const CENTER: [number, number] = [27.47, 89.64];
const icon = L.icon({ iconUrl: new URL("leaflet/dist/images/marker-icon.png", import.meta.url).href, iconRetinaUrl: new URL("leaflet/dist/images/marker-icon-2x.png", import.meta.url).href, shadowUrl: new URL("leaflet/dist/images/marker-shadow.png", import.meta.url).href, iconSize: [25, 41], iconAnchor: [12, 41] });

/** Click the map to drop a pin; the pin follows the latitude / longitude boxes. */
export function MapPicker({ lat, lng, onPick }: { lat: string; lng: string; onPick: (lat: string, lng: string) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const pin = useRef<L.Marker | null>(null);
  const cb = useRef(onPick);
  cb.current = onPick;

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current).setView(CENTER, 8);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "&copy; OpenStreetMap contributors" }).addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => cb.current(e.latlng.lat.toFixed(6), e.latlng.lng.toFixed(6)));
    map.current = m;
    return () => { m.remove(); map.current = null; pin.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current, a = parseFloat(lat), b = parseFloat(lng);
    if (!m) return;
    if (Number.isFinite(a) && Number.isFinite(b) && Math.abs(a) <= 90 && Math.abs(b) <= 180) {
      if (pin.current) pin.current.setLatLng([a, b]); else pin.current = L.marker([a, b], { icon }).addTo(m);
      m.setView([a, b], Math.max(m.getZoom(), 12));
    } else if (pin.current) { pin.current.remove(); pin.current = null; }
  }, [lat, lng]);

  return <div ref={el} role="application" aria-label="Map: click to mark the place of the issue" style={{ height: 280, borderRadius: 8, marginBottom: 12 }} />;
}
