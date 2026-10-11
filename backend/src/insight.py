"""Area report: what kind of growth happened around a point over the last ~10 years.

Evidence is collected from three places, then written up either by Claude (if an
GEMINI_API_KEY is set) or by a deterministic rule-based writer:

  1. measurements from the night-light matrices (src/window.py)         - always
  2. OpenStreetMap: place name (Nominatim) and nearby land use (Overpass) - free, no key
  3. Wikipedia: articles near the coordinates (public API)               - free, no key

Every network call is optional: if one fails the report still works and says what was missing.
Results are cached on disk so repeated clicks do not hit the services again.
"""
import hashlib
import json
import os
import threading
import time
from pathlib import Path

from . import config

try:
    import requests
except ImportError:  # the report degrades to measurements only
    requests = None

CACHE_DIR = config.ROOT / "cache" / "insight"
CACHE_TTL_S = 7 * 24 * 3600
HTTP_TIMEOUT = 12

NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
WIKI_API = "https://en.wikipedia.org/w/api.php"
OVERPASS = "https://overpass-api.de/api/interpreter"

_last_nominatim = [0.0]
_lock = threading.Lock()


def _ua():
    contact = os.environ.get("CONTACT_EMAIL", "student-project@example.com")
    return {"User-Agent": f"NightLightStudentProject/1.0 ({contact})"}


# ------------------------------------------------------------------ cache
def _key(lat, lon, radius_km, use_ai):
    has_key = bool(os.environ.get("GEMINI_API_KEY"))
    raw = f"{config.REGION}|{lat:.3f}|{lon:.3f}|{radius_km:g}|{int(use_ai)}|{int(has_key)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def cache_get(lat, lon, radius_km, use_ai):
    p = CACHE_DIR / f"{_key(lat, lon, radius_km, use_ai)}.json"
    try:
        if p.exists() and time.time() - p.stat().st_mtime < CACHE_TTL_S:
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def cache_put(lat, lon, radius_km, use_ai, data):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{_key(lat, lon, radius_km, use_ai)}.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# ------------------------------------------------------------------ web sources
def reverse_geocode(lat, lon):
    """Place name and administrative area from OpenStreetMap Nominatim (max 1 request/second)."""
    if requests is None:
        return None
    with _lock:
        wait = 1.1 - (time.time() - _last_nominatim[0])
        if wait > 0:
            time.sleep(wait)
        _last_nominatim[0] = time.time()
    r = requests.get(NOMINATIM, params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 12,
                                        "addressdetails": 1, "accept-language": "en"},
                     headers=_ua(), timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    j = r.json()
    a = j.get("address", {})
    return {
        "display_name": j.get("display_name"),
        "locality": a.get("city") or a.get("town") or a.get("village") or a.get("suburb") or a.get("hamlet"),
        "district": a.get("state_district") or a.get("county") or a.get("district"),
        "state": a.get("state"),
    }


def wikipedia_nearby(lat, lon, radius_m=10000, limit=4):
    """Wikipedia articles near the coordinates, with a short plain-text intro each."""
    if requests is None:
        return []
    r = requests.get(WIKI_API, params={
        "action": "query", "list": "geosearch", "gscoord": f"{lat}|{lon}", "gsradius": radius_m,
        "gslimit": limit, "format": "json"}, headers=_ua(), timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    hits = r.json().get("query", {}).get("geosearch", [])
    if not hits:
        return []
    ids = "|".join(str(h["pageid"]) for h in hits)
    r = requests.get(WIKI_API, params={
        "action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1, "exsentences": 3,
        "pageids": ids, "format": "json"}, headers=_ua(), timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    out = []
    for h in hits:
        extract = (pages.get(str(h["pageid"])) or {}).get("extract", "") or ""
        out.append({
            "title": h["title"], "distance_km": round(h.get("dist", 0) / 1000, 1),
            "summary": extract.strip()[:450],
            "url": "https://en.wikipedia.org/wiki/" + h["title"].replace(" ", "_"),
        })
    return out


_OSM_GROUPS = [
    ("Industrial land", 'way["landuse"="industrial"]'),
    ("Quarries and mines", 'way["landuse"="quarry"]'),
    ("Power plants", 'way["power"="plant"]'),
    ("Factories and works", 'way["man_made"="works"]'),
    ("Residential land", 'way["landuse"="residential"]'),
    ("Commercial and retail", 'way["landuse"~"commercial|retail"]'),
    ("Under construction", 'way["landuse"="construction"]'),
    ("Railway stations", 'node["railway"="station"]'),
    ("Schools and colleges", 'nwr["amenity"~"school|college|university"]'),
    ("Hospitals", 'nwr["amenity"="hospital"]'),
]


def osm_land_use(lat, lon, radius_km):
    """Count mapped land-use features within the radius (OpenStreetMap via Overpass)."""
    if requests is None:
        return {}
    rad = int(radius_km * 1000)
    body = "".join(f'{sel}(around:{rad},{lat},{lon});' for _, sel in _OSM_GROUPS)
    # one query, tagged output, then count per group on our side
    q = f"[out:json][timeout:20];({body});out tags 400;"
    r = requests.post(OVERPASS, data={"data": q}, headers=_ua(), timeout=25)
    r.raise_for_status()
    counts = {name: 0 for name, _ in _OSM_GROUPS}
    for el in r.json().get("elements", []):
        t = el.get("tags", {})
        lu, am = t.get("landuse"), t.get("amenity")
        if lu == "industrial": counts["Industrial land"] += 1
        elif lu == "quarry": counts["Quarries and mines"] += 1
        elif lu == "residential": counts["Residential land"] += 1
        elif lu in ("commercial", "retail"): counts["Commercial and retail"] += 1
        elif lu == "construction": counts["Under construction"] += 1
        elif t.get("power") == "plant": counts["Power plants"] += 1
        elif t.get("man_made") == "works": counts["Factories and works"] += 1
        elif t.get("railway") == "station": counts["Railway stations"] += 1
        elif am in ("school", "college", "university"): counts["Schools and colleges"] += 1
        elif am == "hospital": counts["Hospitals"] += 1
    return {k: v for k, v in counts.items() if v}


# ------------------------------------------------------------------ writers
def rule_based_report(ev):
    """Deterministic write-up from the evidence (used when there is no AI key or the AI call fails)."""
    m, place = ev["measurements"], ev.get("place") or {}
    g = m["growth_type"]
    name = place.get("locality") or place.get("district") or "this area"
    where = ", ".join(x for x in [place.get("district"), place.get("state")] if x)
    parts = []
    pct = f" ({m['change_pct']:+.0f}%)" if m.get("change_pct") is not None else ""
    parts.append(
        f"Within {m['radius_km']:g} km of {name}{' (' + where + ')' if where else ''}, average night-time "
        f"brightness went from {m['mean_first']} to {m['mean_last']} nW/cm²/sr between {m['period'].split('-')[0]} "
        f"and {m['period'].split('-')[1]}{pct}. {g['why']}")
    if m["hotspot"]:
        h = m["hotspot"]
        parts.append(f"The strongest increase is near {h['lat']}, {h['lon']} (+{h['gain']} nW/cm²/sr).")
    if m["biggest_jump"]:
        parts.append(f"The largest single-year rise in the area average was in {m['biggest_jump']['year']}.")
    lu = ev.get("land_use") or {}
    drivers = []
    if lu.get("Industrial land") or lu.get("Factories and works") or lu.get("Power plants"):
        drivers.append("industrial land, factories or power plants are mapped nearby")
    if lu.get("Quarries and mines"):
        drivers.append("quarries or mines are mapped nearby")
    if lu.get("Residential land") or lu.get("Commercial and retail") or lu.get("Under construction"):
        drivers.append("residential, commercial or construction land is mapped nearby")
    if drivers:
        parts.append("Context from OpenStreetMap: " + "; ".join(drivers) + ".")
    return {
        "headline": g["label"],
        "summary": " ".join(parts),
        "growth_type": g["key"],
        "likely_drivers": drivers or ["No land-use features were found to explain the change."],
        "confidence": "low" if not lu else "medium",
        "source": "rules",
    }


SYSTEM_PROMPT = (
    "You write short, careful area reports for a night-lights change-detection project in India. "
    "You are given measurements from NASA Black Marble night-light data and context from OpenStreetMap and "
    "Wikipedia. Use ONLY the supplied evidence. Do not invent facts, dates, company names or projects. "
    "Night lights show where lighting changed, not why; say so, and never claim illegality. Mention that "
    "pixels are about 500 m wide. If the evidence is thin, say the explanation is uncertain. "
    "Reply with ONLY a JSON object with keys: headline (max 12 words), summary (max 110 words, plain "
    "prose), growth_type (one of: new_development, intensification, gradual_growth, decline, stable), "
    "likely_drivers (list of up to 4 short strings, each grounded in the evidence), confidence "
    "(low, medium or high)."
)


def ai_report(ev):
    """Ask Claude to write the report from the evidence. Returns None if no key / any failure."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    payload = {k: v for k, v in ev.items() if k != "measurements"}
    m = {k: v for k, v in ev["measurements"].items()}
    payload["measurements"] = m
    client = anthropic.Anthropic(api_key=key)
    resp = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        max_tokens=700,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    for k in ("headline", "summary"):
        if not isinstance(data.get(k), str):
            return None
    data["source"] = "claude"
    data["model"] = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    return data


# ------------------------------------------------------------------ main entry
def build_report(lat, lon, radius_km, measurements, use_ai=True):
    """Collect evidence, write the report, never raise because of a web failure."""
    cached = cache_get(lat, lon, radius_km, use_ai)
    if cached:
        cached["cached"] = True
        return cached

    warnings, ev = [], {"location": {"lat": lat, "lon": lon, "region": config.STATE_NAME}}
    public = {k: v for k, v in measurements.items() if not k.startswith("_")}
    ev["measurements"] = public

    for key, fn, label in [
        ("place", lambda: reverse_geocode(lat, lon), "place name (OpenStreetMap)"),
        ("land_use", lambda: osm_land_use(lat, lon, radius_km), "land use (OpenStreetMap)"),
        ("nearby_articles", lambda: wikipedia_nearby(lat, lon), "nearby places (Wikipedia)"),
    ]:
        try:
            ev[key] = fn()
        except Exception as e:  # network down, rate limited, timeout ...
            ev[key] = None if key == "place" else ({} if key == "land_use" else [])
            warnings.append(f"Could not load {label}: {type(e).__name__}")
    if requests is None:
        warnings.append("The 'requests' package is not installed, so web sources were skipped.")

    report, ai_error = None, None
    if use_ai:
        try:
            report = ai_report(ev)
        except Exception as e:
            ai_error = f"AI summary failed ({type(e).__name__}); showing the rule-based summary instead."
    if report is None:
        report = rule_based_report(ev)
        if use_ai and ai_error:
            warnings.append(ai_error)
        elif use_ai and not os.environ.get("GEMINI_API_KEY"):
            warnings.append("No GEMINI_API_KEY set, so the rule-based summary is shown.")

    out = {
        "report": report,
        "place": ev.get("place"),
        "land_use": ev.get("land_use") or {},
        "nearby_articles": ev.get("nearby_articles") or [],
        "measurements": public,
        "warnings": warnings,
        "sources": ["NASA Black Marble VNP46A4", "OpenStreetMap (Nominatim, Overpass)", "Wikipedia"]
                   + (["Anthropic Claude"] if report.get("source") == "claude" else []),
        "disclaimer": ("Night lights show where lighting changed, not why. The explanation is an informed "
                       "interpretation, not a ground-truth survey, and says nothing about legality."),
        "cached": False,
    }
    if not warnings or all("Could not load" not in w for w in warnings):
        cache_put(lat, lon, radius_km, use_ai, out)   # do not cache partial / failed lookups
    return out
