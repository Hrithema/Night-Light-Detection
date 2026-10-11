import { fmt, pretty } from "../util";

// Shows the hand label(s) from label_sheet.csv for the coordinates the user entered.
export default function LabelPanel({ data }) {
  if (!data) return null;
  const { match, site, nearest, thresholds_km } = data;
  const s = site || null;

  return (
    <section className="result labelpanel">
      <h2>Label for these coordinates</h2>
      {match === "none" ? (
        <p className="hint">
          No labelled site within {thresholds_km.near} km. The closest one is site{" "}
          {nearest[0].site_id} ({pretty(nearest[0].label)}), {fmt(nearest[0].distance_km, 1)} km away.
        </p>
      ) : (
        <>
          <div className="verdict">
            <span className={`badge ${s.label === "no_change" ? "cool" : "hot"}`}>{pretty(s.label)}</span>
            <span className="src">
              {match === "exact" ? "Exact match" : `Nearest site, ${fmt(s.distance_km, 2)} km away`}
              {" · "}site {s.site_id} ({s.candidate.replace("_", " ")})
            </span>
          </div>
          {s.notes && <p className="place">Note: {s.notes}</p>}
          <dl className="kv">
            <div><dt>Radiance ~2013</dt><dd>{fmt(s.first_radiance, 2)}</dd></div>
            <div><dt>Radiance ~2024</dt><dd>{fmt(s.last_radiance, 2)}</dd></div>
            <div>
              <dt>Change</dt>
              <dd>
                {s.change == null ? "n/a" : `${s.change >= 0 ? "+" : ""}${fmt(s.change, 1)}`}
                {s.change_pct != null && ` (${s.change_pct >= 0 ? "+" : ""}${s.change_pct.toFixed(0)}%)`}
              </dd>
            </div>
            <div><dt>Area</dt><dd>{s.area_km2 == null ? "n/a" : `${fmt(s.area_km2, 1)} km²`}</dd></div>
          </dl>
          <a className="maplink" href={s.maps_link} target="_blank" rel="noreferrer">
            Open in Google Maps satellite
          </a>
        </>
      )}
    </section>
  );
}
