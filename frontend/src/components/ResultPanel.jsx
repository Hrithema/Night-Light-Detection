import { fmt, isChange, pretty } from "../util";

export default function ResultPanel({ result, name }) {
  const { lat, lon, label, label_source, change_score, probabilities, features } = result;
  const changed = isChange(label);
  const probs = probabilities ? Object.entries(probabilities).sort((a, b) => b[1] - a[1]) : [];

  return (
    <section className="result">
      <h2>{changed ? "Lights grew here" : "No clear change"}</h2>
      {name && <p className="place">{name}</p>}
      <p className="coords">
        {fmt(lat, 4)}, {fmt(lon, 4)}
      </p>

      <div className="verdict">
        <span className={`badge ${changed ? "hot" : "cool"}`}>{pretty(label)}</span>
        <span className="src">
          {label_source === "model" ? "Random Forest prediction" : "Rule-based estimate (no model loaded)"}
        </span>
      </div>

      <div className="meter" aria-label={`Change score ${fmt(change_score, 2)} out of 1`}>
        <div className="meter-head">
          <span>Change score</span>
          <strong>{fmt(change_score, 2)}</strong>
        </div>
        <div className="track">
          <div className="fill" style={{ width: `${Math.round(change_score * 100)}%` }} />
        </div>
      </div>

      {probs.length > 0 && (
        <div className="probs">
          <h3>Model probabilities</h3>
          {probs.map(([k, p]) => (
            <div className="prob" key={k}>
              <span>{pretty(k)}</span>
              <div className="track small"><div className="fill" style={{ width: `${p * 100}%` }} /></div>
              <em>{(p * 100).toFixed(0)}%</em>
            </div>
          ))}
        </div>
      )}

      <details className="features">
        <summary>Brightness-change features</summary>
        <dl>
          {Object.entries(features).map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{fmt(v, 3)}</dd>
            </div>
          ))}
        </dl>
      </details>
    </section>
  );
}
