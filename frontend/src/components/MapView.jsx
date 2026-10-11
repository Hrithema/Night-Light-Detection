import { useEffect, useRef } from "react";
import L from "leaflet";
import { brightnessColor } from "../util";

// Rough bounds of the Jharkhand study area used by the backend
const JH_BOUNDS = [
  [21.95, 83.3],
  [25.35, 87.95],
];
// The backend averages a 3x3 pixel window (~500 m pixels) around the point
const HALF_WINDOW_DEG = 0.00675;

export default function MapView({ point, radiance, maxRadiance, sites, showSites, onPick }) {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const layers = useRef({});
  const pickRef = useRef(onPick);
  pickRef.current = onPick;

  // Create the map once
  useEffect(() => {
    const map = L.map(elRef.current).fitBounds(JH_BOUNDS);

    const dark = L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { subdomains: "abcd", maxZoom: 19, attribution: "© OpenStreetMap contributors © CARTO" }
    );
    const streets = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors",
    });
    const satellite = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 18, attribution: "Tiles © Esri" }
    );
    dark.addTo(map);
    L.control.layers({ Dark: dark, Streets: streets, Satellite: satellite }, {}, { position: "topright" }).addTo(map);

    L.rectangle(JH_BOUNDS, {
      color: "#f4a93b", weight: 1, dashArray: "6 6", fill: false, interactive: false,
    }).addTo(map);

    map.on("click", (e) => pickRef.current(e.latlng.lat, e.latlng.lng));
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Detected-sites overlay
  useEffect(() => {
    const map = mapRef.current;
    if (layers.current.sites) {
      map.removeLayer(layers.current.sites);
      layers.current.sites = null;
    }
    if (!showSites || !sites) return;
    const color = (t) => (t === "emergence" ? "#5bb8d4" : "#f4a93b");
    layers.current.sites = L.geoJSON(sites, {
      style: (f) => ({ color: color(f.properties.type), weight: 1.5, fillOpacity: 0.25 }),
      pointToLayer: (f, ll) =>
        L.circleMarker(ll, { radius: 5, color: color(f.properties.type), weight: 1.5, fillOpacity: 0.4 }),
      onEachFeature: (f, layer) => {
        const p = f.properties;
        layer.bindPopup(
          `<b>${p.type}</b><br>Area: ${Number(p.area_km2).toFixed(2)} km²<br>Total gain: ${Number(p.total_gain).toFixed(0)}`
        );
      },
    }).addTo(map);
  }, [showSites, sites]);

  // Selected point: analysed window + context ring
  useEffect(() => {
    const map = mapRef.current;
    ["rect", "ring", "dot"].forEach((k) => {
      if (layers.current[k]) map.removeLayer(layers.current[k]);
      layers.current[k] = null;
    });
    if (!point) return;
    const { lat, lon } = point;
    const dLon = HALF_WINDOW_DEG / Math.cos((lat * Math.PI) / 180);
    layers.current.rect = L.rectangle(
      [[lat - HALF_WINDOW_DEG, lon - dLon], [lat + HALF_WINDOW_DEG, lon + dLon]],
      { color: "#ffffff", weight: 1.5, fillOpacity: 0.75, fillColor: "#3a4663" }
    ).addTo(map);
    layers.current.ring = L.circle([lat, lon], {
      radius: 5000, color: "#ffffff", weight: 1, dashArray: "4 6", fill: false, interactive: false,
    }).addTo(map);
    layers.current.dot = L.circleMarker([lat, lon], {
      radius: 3, color: "#101826", weight: 1, fillColor: "#fff", fillOpacity: 1, interactive: false,
    }).addTo(map);
    map.flyTo([lat, lon], Math.max(map.getZoom(), 12), { duration: 1.1 });
  }, [point]);

  // Colour the analysed window by the radiance of the selected year (timeline)
  useEffect(() => {
    layers.current.rect?.setStyle({ fillColor: brightnessColor(radiance, maxRadiance) });
  }, [radiance, maxRadiance, point]);

  return <div ref={elRef} className="map" />;
}
