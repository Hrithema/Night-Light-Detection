const STEPS = [
  ["1", "Acquire", "NASA Black Marble VNP46A4 annual night-light composites, 2013–2024 (~500 m pixels)"],
  ["2", "Preprocess", "Crop to the state, mask bad pixels and everything outside the border"],
  ["3", "Difference", "Subtract the matrices: D = B − A, plus yearly differences and trend slope"],
  ["4", "Detect", "Flag unusually large changes, group neighbouring pixels into sites"],
  ["5", "Classify", "Random Forest, trained on 85 hand-labelled sites, filters false alarms"],
  ["6", "Explain", "Area report from the matrices, OpenStreetMap, Wikipedia and an AI summary"],
];

const RESULTS = [
  ["Detected sites (Jharkhand)", "271"],
  ["Hand-labelled locations", "85"],
  ["Rule alone: flagged sites that are real change", "65%"],
  ["Binary classifier, spatial cross-validation", "accuracy 0.73 · macro F1 0.73"],
  ["Change class: precision / recall", "0.68 / 0.80"],
  ["Industrial vs mining (4 vs 6 labels)", "not learnable with night lights"],
];

export default function About({ meta }) {
  return (
    <div className="about">
      <section>
        <h3>Night-Light: land-change detection from night-time satellite imagery</h3>
        <p>
          Finds where night-time lights changed strongly between 2013 and 2024
          {meta?.state ? ` in ${meta.state}` : ""}: a signal linked to industrialisation, rapid urban
          development and mining. Every graph on this site is computed from the real matrices of the
          satellite product, not pre-drawn.
        </p>
        <ol className="steps">
          {STEPS.map(([n, t, d]) => (
            <li key={n}><span>{n}</span><div><b>{t}</b><p>{d}</p></div></li>
          ))}
        </ol>
      </section>

      <section>
        <h3>How to read the graphs</h3>
        <ul className="bul">
          <li><b>Matrix A / B:</b> the radiance grid of the first and last years (log colour scale; one number per ~500 m pixel).</li>
          <li><b>Difference matrix D = B − A:</b> red pixels got brighter, blue got darker. The dashed outline marks the top 5% of increases.</li>
          <li><b>Yellow star / ring:</b> the largest smoothed increase in the area. The ring repeats on every yearly panel so you can see when it grew.</li>
          <li><b>Yearly panels:</b> each year minus the year before, on one shared colour scale.</li>
        </ul>
      </section>

      <section>
        <h3>Results (version 1)</h3>
        <table className="res">
          <tbody>{RESULTS.map(([k, v]) => (<tr key={k}><th>{k}</th><td>{v}</td></tr>))}</tbody>
        </table>
        <p className="muted">Measured inside Jharkhand with spatial cross-validation. The model has not been validated in other states.</p>
      </section>

      <section>
        <h3>Limitations</h3>
        <ul className="bul">
          <li>Lights show <i>where</i> lighting changed, not <i>why</i>. Road lighting and village electrification look like growth.</li>
          <li>Pixels are ~500 m wide; small sites are not resolved and many mines are barely lit at night.</li>
          <li>Nothing here says whether an activity is legal or illegal.</li>
          <li>Small training set (85 labels, one region, one annotator).</li>
        </ul>
      </section>

      <section>
        <h3>Built with</h3>
        <div className="chips">
          {["Python", "NumPy", "SciPy", "scikit-learn", "matplotlib", "Flask", "React", "Vite", "Leaflet", "Recharts", "NASA Earthdata", "OpenStreetMap", "Wikipedia API", "Claude API"].map((t) => (<span key={t} className="chip">{t}</span>))}
        </div>
      </section>
    </div>
  );
}
