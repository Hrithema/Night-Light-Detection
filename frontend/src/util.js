// "23.79, 86.43" or "23.79 86.43" -> {lat, lon}; anything else -> null
export function parseCoords(text) {
  const m = text.trim().match(/^(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)$/);
  if (!m) return null;
  const lat = Number(m[1]);
  const lon = Number(m[2]);
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return { lat, lon };
}

const STOPS = [
  [0, [30, 42, 82]],
  [0.35, [74, 96, 168]],
  [0.65, [244, 169, 59]],
  [1, [255, 247, 214]],
];

// Radiance -> colour on a log scale, dark blue (dim) to pale yellow (bright).
export function brightnessColor(rad, max) {
  if (rad == null) return "#3a4663";
  const t = Math.min(1, Math.log1p(Math.max(rad, 0)) / Math.log1p(Math.max(max, 1)));
  for (let i = 1; i < STOPS.length; i++) {
    const [t1, c1] = STOPS[i];
    const [t0, c0] = STOPS[i - 1];
    if (t <= t1) {
      const k = (t - t0) / (t1 - t0);
      const rgb = c0.map((v, j) => Math.round(v + (c1[j] - v) * k));
      return `rgb(${rgb.join(",")})`;
    }
  }
  return "rgb(255,247,214)";
}

const LABELS = {
  likely_change: "Likely land change",
  no_clear_change: "No clear change",
  change: "Land change",
  no_change: "No change",
  unclassified: "Unclassified",
  urban_growth: "Urban growth",
  mining: "Mining",
  industrial: "Industrial",
};
export const pretty = (k) => LABELS[k] || String(k).replace(/_/g, " ");
export const isChange = (k) => !["no_change", "no_clear_change", "unclassified"].includes(k);
export const fmt = (n, d = 2) => (n == null || Number.isNaN(n) ? "n/a" : Number(n).toFixed(d));
