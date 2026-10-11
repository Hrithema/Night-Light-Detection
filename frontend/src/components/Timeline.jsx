import { useEffect, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceDot, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fmt } from "../util";

export default function Timeline({ series, idx, setIdx }) {
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing || series.length === 0) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % series.length), 900);
    return () => clearInterval(t);
  }, [playing, series.length, setIdx]);

  useEffect(() => setPlaying(false), [series]);

  if (series.length === 0) {
    return <p className="empty">Pick a location to see its last 10 years of night-time brightness.</p>;
  }

  const cur = series[idx] ?? series[series.length - 1];
  const first = series[0];
  const delta =
    cur.radiance != null && first.radiance != null ? cur.radiance - first.radiance : null;
  const pct =
    delta != null && first.radiance > 0 ? (delta / first.radiance) * 100 : null;

  return (
    <div className="timeline">
      <div className="tl-controls">
        <button className="play" onClick={() => setPlaying((p) => !p)}>
          {playing ? "Pause" : "Play"}
        </button>
        <input
          type="range"
          min={0}
          max={series.length - 1}
          value={idx}
          onChange={(e) => { setPlaying(false); setIdx(Number(e.target.value)); }}
          aria-label="Year"
        />
        <div className="years">
          {series.map((s, i) => (
            <button
              key={s.year}
              className={i === idx ? "on" : ""}
              onClick={() => { setPlaying(false); setIdx(i); }}
            >
              {s.year}
            </button>
          ))}
        </div>
      </div>

      <div className="tl-read">
        <div>
          <span>{cur.year}</span>
          <strong>{cur.radiance == null ? "no data" : `${cur.radiance}`}</strong>
          <small>nW/cm²/sr</small>
        </div>
        <div>
          <span>Change since {first.year}</span>
          <strong>{delta == null ? "n/a" : `${delta >= 0 ? "+" : ""}${fmt(delta, 1)}`}</strong>
          <small>{pct == null ? "" : `${pct >= 0 ? "+" : ""}${pct.toFixed(0)}%`}</small>
        </div>
      </div>

      <div className="tl-chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={series}
            margin={{ top: 8, right: 16, bottom: 0, left: -12 }}
            onClick={(s) => s?.activeTooltipIndex != null && setIdx(s.activeTooltipIndex)}
          >
            <CartesianGrid stroke="#2a3857" strokeDasharray="3 5" vertical={false} />
            <XAxis dataKey="year" stroke="#93a0bd" tickLine={false} />
            <YAxis stroke="#93a0bd" tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ background: "#18233a", border: "1px solid #2a3857", borderRadius: 6 }}
              labelStyle={{ color: "#e8ecf5" }}
              formatter={(v) => [`${v} nW/cm²/sr`, "Radiance"]}
            />
            <Line type="monotone" dataKey="radiance" stroke="#f4a93b" strokeWidth={2.5} dot={{ r: 3, fill: "#f4a93b" }} />
            <ReferenceLine x={cur.year} stroke="#e8ecf5" strokeDasharray="4 4" />
            {cur.radiance != null && (
              <ReferenceDot x={cur.year} y={cur.radiance} r={6} fill="#fff" stroke="#f4a93b" strokeWidth={2} />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
