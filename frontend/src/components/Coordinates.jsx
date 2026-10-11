import { useMemo, useState } from "react";
import SITES from "../data/sites.json";
import { pretty } from "../util";

const fmtCoord = (s) => `${s.lat}, ${s.lon}`;

// Every coordinate from the label sheet, saved in the frontend.
// "Copy" puts "lat, lon" on the clipboard, ready to paste into the search box.
export default function Coordinates({ onPick }) {
  const [filter, setFilter] = useState("all");
  const [copied, setCopied] = useState("");

  const labels = useMemo(() => ["all", ...new Set(SITES.map((s) => s.label))], []);
  const rows = SITES.filter((s) => filter === "all" || s.label === filter);

  async function copy(text, key) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const t = document.createElement("textarea"); // fallback for http / old browsers
      t.value = text; document.body.appendChild(t); t.select();
      document.execCommand("copy"); t.remove();
    }
    setCopied(key);
    setTimeout(() => setCopied(""), 1200);
  }

  return (
    <div className="coords-tab">
      <div className="coords-bar">
        <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter by label">
          {labels.map((l) => (
            <option key={l} value={l}>{l === "all" ? `All labels (${SITES.length})` : pretty(l)}</option>
          ))}
        </select>
        <button onClick={() => copy(rows.map(fmtCoord).join("\n"), "all")}>
          {copied === "all" ? "Copied" : `Copy all ${rows.length}`}
        </button>
      </div>
      <div className="coords-scroll">
        <table>
          <thead>
            <tr><th>ID</th><th>Coordinates</th><th>Label</th><th></th></tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id}>
                <td>{s.id}</td>
                <td>
                  <button className="link" onClick={() => onPick(s.lat, s.lon, `Site ${s.id}`)} title="Analyse this point">
                    {fmtCoord(s)}
                  </button>
                </td>
                <td><span className={`badge small ${s.label === "no_change" ? "cool" : "hot"}`}>{pretty(s.label)}</span></td>
                <td><button className="copy" onClick={() => copy(fmtCoord(s), s.id)}>{copied === s.id ? "Copied" : "Copy"}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
