import { useState } from "react";
import { geocode } from "../geocode";
import { parseCoords } from "../util";

export default function SearchBar({ onPick, busy }) {
  const [text, setText] = useState("");
  const [options, setOptions] = useState([]);
  const [msg, setMsg] = useState("");
  const [searching, setSearching] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setMsg("");
    setOptions([]);
    const q = text.trim();
    if (!q) return;

    // 1) coordinates typed directly
    const c = parseCoords(q);
    if (c) return onPick(c.lat, c.lon, `${c.lat}, ${c.lon}`);

    // 2) otherwise treat it as a place name and geocode it
    setSearching(true);
    try {
      const rows = await geocode(q);
      if (rows.length === 0) setMsg("No place found. Try adding “Jharkhand” or use coordinates.");
      else if (rows.length === 1) onPick(rows[0].lat, rows[0].lon, rows[0].name);
      else setOptions(rows);
    } catch (err) {
      setMsg(err.message);
    } finally {
      setSearching(false);
    }
  }

  return (
    <form className="search" onSubmit={submit}>
      <label htmlFor="q">Place name or coordinates</label>
      <div className="row">
        <input
          id="q"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Bokaro Steel City  or  23.67, 86.15"
          autoComplete="off"
        />
        <button type="submit" disabled={busy || searching}>
          {searching ? "Searching" : "Analyse"}
        </button>
      </div>
      {msg && <p className="msg">{msg}</p>}
      {options.length > 0 && (
        <ul className="options">
          {options.map((o) => (
            <li key={`${o.lat},${o.lon}`}>
              <button
                type="button"
                onClick={() => {
                  setOptions([]);
                  onPick(o.lat, o.lon, o.name);
                }}
              >
                {o.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
