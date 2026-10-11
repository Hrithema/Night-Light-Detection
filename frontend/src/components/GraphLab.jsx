import { useEffect, useRef, useState } from "react";
import { fetchDifferencePlot } from "../api";
import { parseCoords } from "../util";

export const RADII = [5, 10, 20, 30];

// "Generate graph": asks the backend to draw a matplotlib dashboard for the typed coordinates
// (first/last year matrices, the difference matrix, the difference of every year, hotspot).
export default function GraphLab({ point, radius, setRadius, onPick }) {
  const [text, setText] = useState("");
  const [state, setState] = useState({ status: "idle" });
  const [open, setOpen] = useState(false);
  const urlRef = useRef(null);

  // Keep the box in sync with the point picked on the map / search bar
  useEffect(() => {
    if (point) setText(`${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`);
  }, [point]);
  useEffect(() => () => urlRef.current && URL.revokeObjectURL(urlRef.current), []);

  async function generate(e) {
    e?.preventDefault();
    const c = parseCoords(text);
    if (!c) {
      setState({ status: "error", message: "Enter coordinates like 23.79, 86.43" });
      return;
    }
    if (!point || point.lat !== c.lat || point.lon !== c.lon) onPick(c.lat, c.lon, ""); // sync the map
    setState({ status: "loading" });
    const t0 = performance.now();
    try {
      const url = await fetchDifferencePlot(c.lat, c.lon, radius);
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      urlRef.current = url;
      setState({
        status: "ok", url, lat: c.lat, lon: c.lon, radius,
        seconds: ((performance.now() - t0) / 1000).toFixed(1),
      });
    } catch (err) {
      setState({ status: "error", message: err.message });
    }
  }

  const busy = state.status === "loading";
  return (
    <section className="lab">
      <form className="lab-form" onSubmit={generate}>
        <div className="field grow">
          <label htmlFor="lab-coords">Coordinates (latitude, longitude)</label>
          <input
            id="lab-coords"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="23.64751, 85.28968"
            autoComplete="off"
          />
        </div>
        <div className="field">
          <label htmlFor="lab-radius">Area radius</label>
          <select id="lab-radius" value={radius} onChange={(e) => setRadius(Number(e.target.value))}>
            {RADII.map((r) => (
              <option key={r} value={r}>{r} km</option>
            ))}
          </select>
        </div>
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Generating…" : "Generate graph"}
        </button>
      </form>

      <p className="lab-help">
        Draws, with matplotlib, the night-light matrix of the first and last years, their
        difference, and the difference of <em>every</em> year, then marks where the lights
        changed the most (yellow star).
      </p>

      {state.status === "idle" && (
        <div className="lab-empty">Pick a place on the map (or type coordinates) and press <b>Generate graph</b>.</div>
      )}
      {busy && (
        <div className="lab-empty" role="status">
          <span className="spinner" /> matplotlib is drawing the matrices for this area…
        </div>
      )}
      {state.status === "error" && <div className="error" role="alert">{state.message}</div>}

      {state.status === "ok" && (
        <figure className="lab-result">
          <img
            src={state.url}
            alt={`Night-light change dashboard around ${state.lat}, ${state.lon}`}
            onClick={() => setOpen(true)}
          />
          <figcaption>
            <span>
              {state.lat.toFixed(4)}, {state.lon.toFixed(4)} · {state.radius} km · drawn in {state.seconds}s
            </span>
            <span className="lab-actions">
              <button type="button" onClick={() => setOpen(true)}>Full screen</button>
              <a
                className="btn"
                href={state.url}
                download={`night-light_${state.lat.toFixed(4)}_${state.lon.toFixed(4)}_${state.radius}km.png`}
              >
                Download PNG
              </a>
            </span>
          </figcaption>
        </figure>
      )}

      {open && state.status === "ok" && (
        <div className="lightbox" onClick={() => setOpen(false)} role="dialog" aria-label="Generated graph">
          <img src={state.url} alt="Generated graph, full size" />
          <button onClick={() => setOpen(false)}>Close</button>
        </div>
      )}
    </section>
  );
}
