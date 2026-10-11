import { useEffect, useState } from "react";
import { api } from "../api";
import { fmt } from "../util";
import { RADII } from "./GraphLab.jsx";

const GROWTH = {
  new_development: "New development",
  intensification: "Intensification",
  gradual_growth: "Gradual growth",
  decline: "Decline",
  stable: "Stable",
};

function toText(d) {
  const r = d.report, m = d.measurements;
  return [
    r.headline,
    `${d.place?.display_name || `${d.query.lat}, ${d.query.lon}`} · ${m.radius_km} km · ${m.period}`,
    "",
    r.summary,
    "",
    "Likely drivers: " + (r.likely_drivers || []).join("; "),
    `Brightness ${m.mean_first} → ${m.mean_last} nW/cm²/sr (${m.change_pct ?? "n/a"}%). Source: ${r.source === "claude" ? "Claude" : "rule-based"}.`,
    d.disclaimer,
  ].join("\n");
}

// "Area report": growth type for the area around the point over the last ~10 years,
// written from the night-light matrices plus OpenStreetMap / Wikipedia context (and Claude if enabled).
export default function AreaReport({ point, radius, setRadius, meta, onPick }) {
  const [useAi, setUseAi] = useState(true);
  const [state, setState] = useState({ status: "idle" });
  const [copied, setCopied] = useState(false);

  useEffect(() => setState({ status: "idle" }), [point]); // a new point invalidates the old report

  async function generate() {
    if (!point) return;
    setState({ status: "loading" });
    try {
      const data = await api.insight(point.lat, point.lon, radius, useAi && meta?.ai_available !== false);
      setState({ status: "ok", data });
    } catch (err) {
      setState({ status: "error", message: err.message });
    }
  }

  async function copy(d) {
    try {
      await navigator.clipboard.writeText(toText(d));
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard blocked */
    }
  }

  const aiOff = meta && meta.ai_available === false;
  return (
    <section className="report">
      <div className="lab-form">
        <div className="field grow">
          <label>Selected location</label>
          <div className="static">
            {point ? `${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}${point.name ? ` · ${point.name.split(",")[0]}` : ""}` : "None yet. Search or click the map."}
          </div>
        </div>
        <div className="field">
          <label htmlFor="rep-radius">Area radius</label>
          <select id="rep-radius" value={radius} onChange={(e) => setRadius(Number(e.target.value))}>
            {RADII.map((r) => (<option key={r} value={r}>{r} km</option>))}
          </select>
        </div>
        <label className="check ai" title={aiOff ? "Set ANTHROPIC_API_KEY in backend/.env to enable" : ""}>
          <input type="checkbox" checked={useAi && !aiOff} disabled={aiOff} onChange={(e) => setUseAi(e.target.checked)} />
          AI summary{aiOff ? " (no key)" : ""}
        </label>
        <button className="primary" onClick={generate} disabled={!point || state.status === "loading"}>
          {state.status === "loading" ? "Generating…" : "Generate area report"}
        </button>
      </div>

      {state.status === "idle" && (
        <div className="lab-empty">
          Describes what kind of growth happened around this point over the last 10 years, using the
          night-light matrices, OpenStreetMap, Wikipedia and (optionally) an AI summary.
        </div>
      )}
      {state.status === "loading" && (
        <div className="lab-empty" role="status">
          <span className="spinner" /> Measuring brightness change, then looking up the place and its surroundings… (up to ~20 s)
        </div>
      )}
      {state.status === "error" && <div className="error" role="alert">{state.message}</div>}
      {state.status === "ok" && <Report d={state.data} onPick={onPick} onCopy={() => copy(state.data)} copied={copied} />}
    </section>
  );
}

function Report({ d, onPick, onCopy, copied }) {
  const r = d.report, m = d.measurements, place = d.place;
  const key = r.growth_type || m.growth_type.key;
  const land = Object.entries(d.land_use || {}).sort((a, b) => b[1] - a[1]);
  const hot = m.hotspot;
  return (
    <article className="rep-card">
      <header className="rep-head">
        <div>
          <h2>{r.headline}</h2>
          <p className="place">
            {place?.display_name || `${d.query.lat}, ${d.query.lon}`} · within {m.radius_km} km · {m.period}
          </p>
        </div>
        <div className="rep-badges">
          <span className={`gt gt-${key}`}>{GROWTH[key] || key}</span>
          <span className={`src-badge ${r.source}`}>
            {r.source === "claude" ? "AI summary (Claude)" : "Rule-based summary"}
          </span>
          {r.confidence && <span className="conf">confidence: {r.confidence}</span>}
        </div>
      </header>

      <p className="rep-summary">{r.summary}</p>

      <dl className="kv rep-kv">
        <div><dt>Average brightness</dt><dd>{fmt(m.mean_first, 1)} → {fmt(m.mean_last, 1)}</dd></div>
        <div><dt>Change</dt><dd>{m.change >= 0 ? "+" : ""}{fmt(m.change, 1)}{m.change_pct != null && ` (${m.change_pct >= 0 ? "+" : ""}${m.change_pct.toFixed(0)}%)`}</dd></div>
        <div><dt>Area much brighter</dt><dd>{fmt(m.share_brighter_pct, 1)}%</dd></div>
        <div><dt>Newly lit (dark → lit)</dt><dd>{fmt(m.share_new_light_pct, 1)}%</dd></div>
        <div><dt>Trend</dt><dd>{m.slope_per_year == null ? "n/a" : `${m.slope_per_year >= 0 ? "+" : ""}${fmt(m.slope_per_year, 2)} / year`}</dd></div>
        <div><dt>Biggest yearly rise</dt><dd>{m.biggest_jump ? `${m.biggest_jump.year} (${m.biggest_jump.change >= 0 ? "+" : ""}${fmt(m.biggest_jump.change, 1)})` : "n/a"}</dd></div>
      </dl>

      <div className="rep-cols">
        <section>
          <h3>Likely drivers</h3>
          <ul className="bul">{(r.likely_drivers || []).map((x) => (<li key={x}>{x}</li>))}</ul>
          {hot && (
            <p className="hot">
              Largest increase near <b>{hot.lat}, {hot.lon}</b> (+{fmt(hot.gain, 1)} nW/cm²/sr){" "}
              <button className="link" onClick={() => onPick(hot.lat, hot.lon, "Largest increase")}>show on map</button>
            </p>
          )}
        </section>
        <section>
          <h3>Mapped land use nearby <small>OpenStreetMap</small></h3>
          {land.length ? (
            <div className="chips">{land.map(([k, v]) => (<span key={k} className="chip">{k} <b>{v}</b></span>))}</div>
          ) : (<p className="empty">Nothing relevant mapped (or the service was unavailable).</p>)}
        </section>
        <section>
          <h3>Nearby places <small>Wikipedia</small></h3>
          {d.nearby_articles?.length ? (
            <ul className="wiki">
              {d.nearby_articles.map((a) => (
                <li key={a.url}>
                  <a href={a.url} target="_blank" rel="noreferrer">{a.title}</a> <em>{a.distance_km} km</em>
                  {a.summary && <p>{a.summary.split(". ")[0]}.</p>}
                </li>
              ))}
            </ul>
          ) : (<p className="empty">No articles found nearby.</p>)}
        </section>
      </div>

      {d.warnings?.length > 0 && (
        <ul className="warn">{d.warnings.map((w) => (<li key={w}>{w}</li>))}</ul>
      )}
      <footer className="rep-foot">
        <span>{d.disclaimer}</span>
        <span>Sources: {d.sources.join(" · ")}{d.cached ? " · cached" : ""}</span>
        <button onClick={onCopy}>{copied ? "Copied" : "Copy report text"}</button>
      </footer>
    </article>
  );
}
