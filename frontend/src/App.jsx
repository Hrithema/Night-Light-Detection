import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import SearchBar from "./components/SearchBar.jsx";
import MapView from "./components/MapView.jsx";
import ResultPanel from "./components/ResultPanel.jsx";
import Timeline from "./components/Timeline.jsx";
import Gallery from "./components/Gallery.jsx";
import LabelPanel from "./components/LabelPanel.jsx";
import Coordinates from "./components/Coordinates.jsx";
import AreaReport from "./components/AreaReport.jsx";
import About from "./components/About.jsx";

export default function App() {
  const [health, setHealth] = useState(null); // null = checking, false = offline
  const [point, setPoint] = useState(null); // {lat, lon, name}
  const [result, setResult] = useState(null); // /api/analyze response (optional, needs the full api.py)
  const [labelData, setLabelData] = useState(null); // /api/lookup response (label_sheet.csv)
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [idx, setIdx] = useState(0); // selected year index in the 10-year series
  const [tab, setTab] = useState("mpl");
  const [meta, setMeta] = useState(null); // /api/meta: region, years, sites, ai availability
  const [radius, setRadius] = useState(10); // km, shared by the graph and the area report
  const [expanded, setExpanded] = useState(false); // taller bottom panel for big graphs
  const [sites, setSites] = useState(null);
  const [showSites, setShowSites] = useState(false);
  const reqId = useRef(0);

  // Is the Flask API reachable?
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(false));
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  // Load detected sites the first time the overlay is switched on.
  useEffect(() => {
    if (!showSites || sites) return;
    api
      .sites({ limit: 300 })
      .then(setSites)
      .catch((e) => setError(`Could not load sites: ${e.message}`));
  }, [showSites, sites]);

  const analyze = useCallback(async (lat, lon, name = "") => {
    const id = ++reqId.current; // ignore stale responses if the user clicks quickly
    setPoint({ lat, lon, name });
    setLoading(true);
    setError("");
    // 1) labels from the sheet (the main feature)
    const labelReq = api.lookup(lat, lon);
    // 2) model analysis from the full api.py; optional, ignored if that API isn't running
    const analyzeReq = api.analyze(lat, lon).catch(() => null);
    try {
      const labels = await labelReq;
      if (id !== reqId.current) return;
      setLabelData(labels);
    } catch (e) {
      if (id !== reqId.current) return;
      setLabelData(null);
      setError(e.message);
    }
    const data = await analyzeReq;
    if (id !== reqId.current) return;
    setResult(data);
    if (data) setIdx(Math.max(Math.min(data.timeseries.length, 10) - 1, 0));
    setLoading(false);
  }, []);

  // Last 10 years of yearly radiance
  const series = useMemo(() => (result?.timeseries || []).slice(-10), [result]);
  const maxRad = useMemo(
    () => Math.max(1, ...series.map((s) => s.radiance ?? 0)),
    [series]
  );
  const current = series[idx];

  return (
    <div className="app">
      <aside className="side">
        <header className="brand">
          <h1>Night-Light</h1>
          <p>
            See where the lights of {meta?.state || "Jharkhand"} grew between{" "}
            {meta?.years?.[0] ?? 2013} and {meta?.years?.at(-1) ?? 2024}.
          </p>
          <span className={`status ${health ? "ok" : health === false ? "bad" : ""}`}>
            {health === null && "Connecting to API"}
            {health === false && "API offline. Run python api.py in backend/ (port 5001)"}
            {health && "API connected"}
          </span>
        </header>

        <SearchBar onPick={analyze} busy={loading} />

        <label className="check">
          <input
            type="checkbox"
            checked={showSites}
            onChange={(e) => setShowSites(e.target.checked)}
          />
          Show the {meta?.sites_detected ?? ""} detected sites on the map
        </label>

        {error && <div className="error" role="alert">{error}</div>}
        {!point && !error && (
          <p className="hint">
            Search a place (for example “Dhanbad, Jharkhand”), type coordinates
            (23.79, 86.43), or click anywhere on the map.
          </p>
        )}
        {loading && <p className="hint">Analysing this location…</p>}
        {labelData && !loading && <LabelPanel data={labelData} />}
        {result && !loading && <ResultPanel result={result} name={point?.name} />}
      </aside>

      <main className={`main ${expanded ? "expanded" : ""}`}>
        <section className="map-wrap">
          <MapView
            point={point}
            radiance={current?.radiance}
            maxRadiance={maxRad}
            sites={sites}
            showSites={showSites}
            onPick={(lat, lon) => analyze(lat, lon)}
          />
          {current && (
            <div className="map-year">
              <strong>{current.year}</strong>
              <span>
                {current.radiance == null ? "no data" : `${current.radiance} nW/cm²/sr`}
              </span>
            </div>
          )}
        </section>

        <section className="bottom">
          <div className="tabs" role="tablist">
            {[
              ["mpl", "Matplotlib"],
              ["report", "Area report"],
              ["timeline", "10-year timeline"],
              ["coords", "Saved coordinates"],
              ["about", "About"],
            ].map(([k, label]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>
                {label}
              </button>
            ))}
            <button className="expand" onClick={() => setExpanded((v) => !v)} aria-pressed={expanded}>
              {expanded ? "Collapse panel" : "Expand panel"}
            </button>
          </div>
          <div className="tab-body">
            {tab === "mpl" && (
              <Gallery point={point} onPick={analyze} radius={radius} setRadius={setRadius} />
            )}
            {tab === "report" && (
              <AreaReport point={point} onPick={analyze} radius={radius} setRadius={setRadius} meta={meta} />
            )}
            {tab === "timeline" && <Timeline series={series} idx={idx} setIdx={setIdx} />}
            {tab === "coords" && <Coordinates onPick={analyze} />}
            {tab === "about" && <About meta={meta} />}
          </div>
        </section>
      </main>
    </div>
  );
}
