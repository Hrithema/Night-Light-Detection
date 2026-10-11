// Free place-name search using OpenStreetMap Nominatim (no API key).
// Usage policy: max 1 request/second, so we only search on submit (not per keystroke).
const NOMINATIM = "https://nominatim.openstreetmap.org/search";

export async function geocode(query) {
  const params = new URLSearchParams({
    q: query,
    format: "jsonv2",
    limit: "5",
    countrycodes: "in",
    // west,north,east,south: bias results toward Jharkhand
    viewbox: "83.3,25.4,88.0,21.9",
  });
  const res = await fetch(`${NOMINATIM}?${params}`, {
    headers: { "Accept-Language": "en" },
  });
  if (!res.ok) throw new Error(`Place search failed (${res.status})`);
  const rows = await res.json();
  return rows.map((r) => ({ lat: Number(r.lat), lon: Number(r.lon), name: r.display_name }));
}
