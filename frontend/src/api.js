// All communication with the Python (Flask) backend lives in this one file.
// BASE is empty in development, so "/api/..." goes through the Vite proxy.
const BASE = import.meta.env.VITE_API_URL || "";

async function get(path, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== "" && v !== null)
  ).toString();
  const res = await fetch(`${BASE}${path}${qs ? `?${qs}` : ""}`);
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON response */
  }
  if (!res.ok) {
    // api.py returns {"error": "..."} for 400/404
    throw new Error(body?.error || `Request failed (${res.status})`);
  }
  return body;
}

export const api = {
  health: () => get("/api/health"),
  analyze: (lat, lon) => get("/api/analyze", { lat, lon }),
  timeseries: (lat, lon) => get("/api/timeseries", { lat, lon }),
  sites: (opts = {}) => get("/api/sites", opts),
  lookup: (lat, lon) => get("/api/lookup", { lat, lon }),
  meta: () => get("/api/meta"),
  // Area report: growth type + web/AI context. Can take several seconds.
  insight: (lat, lon, radius_km, ai = true) =>
    get("/api/insight", { lat, lon, radius_km, ai: ai ? 1 : 0 }),
};

// The graph is drawn by matplotlib on the server at request time. We fetch it as a blob
// (not a plain <img src>) so a server-side message such as "outside the study area" can be shown.
export async function fetchDifferencePlot(lat, lon, radius_km) {
  const qs = new URLSearchParams({ lat, lon, radius_km }).toString();
  const res = await fetch(`${BASE}/api/plot/difference.png?${qs}`);
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      msg = (await res.json()).error || msg;
    } catch {
      /* not JSON */
    }
    throw new Error(msg);
  }
  return URL.createObjectURL(await res.blob());
}

// Image URLs are used directly in <img src="...">; the browser fetches the PNG.
export const pipelineImage = (name) => `${BASE}/api/images/${name}`;
export const pointPlot = (lat, lon) =>
  `${BASE}/api/plot/timeseries.png?lat=${lat}&lon=${lon}`;
export const sitePlot = (lat, lon) => `${BASE}/api/plot/site.png?lat=${lat}&lon=${lon}`;
export const overviewPlot = () => `${BASE}/api/plot/overview.png`;
