"""Smoke test of the whole API on SYNTHETIC data (region "demo"), with the web services and the AI mocked.

Run from backend/:
    python run_pipeline.py --fake --region demo
    python tests/smoke_test.py
"""
import json, os, sys, types
os.environ["NL_REGION"] = "demo"   # synthetic data only; never touches your real region
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("ANTHROPIC_API_KEY", None)
import api
from src import insight

c = api.app.test_client()
ok = lambda cond, msg: print(("PASS " if cond else "FAIL ") + msg)

# ---- status
h = c.get("/api/health").get_json(); ok(h["status"] == "ok" and h["region"] == "demo", f"health {h}")
m = c.get("/api/meta").get_json(); ok(m["years"][0] == 2013 and m["radius_km"]["max"] == 40, f"meta years {m['years'][:2]} sites {m['sites_detected']}")

# ---- matplotlib difference graph
r = c.get("/api/plot/difference.png?lat=23.314&lon=86.218&radius_km=10")
ok(r.status_code == 200 and r.mimetype == "image/png" and r.data[:4] == b"\x89PNG", f"difference.png 200, {len(r.data)} bytes")
r2 = c.get("/api/plot/difference.png?lat=23.314&lon=86.218&radius_km=10"); ok(r2.data == r.data, "second call served from cache")
r = c.get("/api/plot/difference.png?lat=23.314&lon=86.218&radius_km=999"); ok(r.status_code == 200, "radius clamps to max instead of failing")
r = c.get("/api/plot/difference.png?lat=10&lon=10"); ok(r.status_code == 400 and "outside" in r.get_json()["error"], f"outside area -> 400 {r.get_json()}")
r = c.get("/api/plot/difference.png?lat=abc&lon=1"); ok(r.status_code == 400, "bad input -> 400 json")
r = c.get("/api/plot/difference.png?lat=23.4&lon=85.3&radius_km=3"); ok(r.status_code == 200, "small radius (3 km) works")

# ---- insight, no network + no key (rule-based)
class Boom:
    def get(self, *a, **k): raise ConnectionError("offline")
    post = get
insight.requests = Boom()
insight.CACHE_DIR = insight.CACHE_DIR.parent / "t1"
j = c.get("/api/insight?lat=23.314&lon=86.218&radius_km=10").get_json()
ok(j["report"]["source"] == "rules" and len(j["warnings"]) >= 3, f"offline: rule-based report + {len(j['warnings'])} warnings")
ok(j["measurements"]["growth_type"]["key"] in ("intensification", "new_development", "gradual_growth"), f"growth type {j['measurements']['growth_type']['key']}")
ok("_arrays" not in json.dumps(j), "no numpy arrays leaked into JSON")

# ---- insight with mocked web + mocked Claude
class R:
    def __init__(s, d): s.d = d
    def raise_for_status(s): pass
    def json(s): return s.d
class Web:
    def get(self, url, params=None, **k):
        if "nominatim" in url:
            return R({"display_name": "Bokaro, Jharkhand, India", "address": {"city": "Bokaro Steel City", "state_district": "Bokaro", "state": "Jharkhand"}})
        if params.get("list") == "geosearch":
            return R({"query": {"geosearch": [{"pageid": 1, "title": "Bokaro Steel City", "dist": 2300}]}})
        return R({"query": {"pages": {"1": {"extract": "Bokaro Steel City is an industrial city."}}}})
    def post(self, url, data=None, **k):
        return R({"elements": [{"tags": {"landuse": "industrial"}}, {"tags": {"landuse": "industrial"}},
                               {"tags": {"landuse": "residential"}}, {"tags": {"power": "plant"}}]})
insight.requests = Web()
insight.CACHE_DIR = insight.CACHE_DIR.parent / "t2"
j = c.get("/api/insight?lat=23.314&lon=86.218&radius_km=10&ai=0").get_json()
ok(j["place"]["locality"] == "Bokaro Steel City" and j["land_use"]["Industrial land"] == 2 and j["nearby_articles"][0]["distance_km"] == 2.3, "OSM + Wikipedia parsed")
ok("industrial land" in j["report"]["summary"].lower() or "industrial" in " ".join(j["report"]["likely_drivers"]).lower(), "rule-based report uses the land-use context")

os.environ["ANTHROPIC_API_KEY"] = "test"
class FakeMsgs:
    def __init__(s, text): s.text = text
    def create(s, **k):
        assert "claude" in k["model"] and "Use ONLY" in k["system"]
        user = json.loads(k["messages"][0]["content"]); assert "measurements" in user and "land_use" in user
        return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=s.text)])
def fake_anthropic(text):
    mod = types.ModuleType("anthropic")
    mod.Anthropic = lambda api_key=None: types.SimpleNamespace(messages=FakeMsgs(text))
    sys.modules["anthropic"] = mod
good = '```json\n{"headline":"Industrial intensification","summary":"Lights rose sharply.","growth_type":"intensification","likely_drivers":["industrial land mapped nearby"],"confidence":"medium"}\n```'
fake_anthropic(good)
j = c.get("/api/insight?lat=23.314&lon=86.218&radius_km=12&ai=1").get_json()
ok(j["report"]["source"] == "claude" and "Claude" in " ".join(j["sources"]), f"AI path: {j['report']['headline']}")
fake_anthropic("sorry I cannot")
j = c.get("/api/insight?lat=23.314&lon=86.218&radius_km=14&ai=1").get_json()
ok(j["report"]["source"] == "rules" and any("AI summary failed" in w for w in j["warnings"]), "bad AI output -> falls back to rules with a warning")
j2 = c.get("/api/insight?lat=23.314&lon=86.218&radius_km=14&ai=1").get_json(); ok(j2["cached"] is True, "second identical request is cached")

# ---- hand-label routes (bundled labelled sheet)
j = c.get("/api/lookup?lat=23.64751&lon=85.28968").get_json()
ok("match" in j and len(j["nearest"]) == 5, f"lookup match={j['match']} label={(j['site'] or {}).get('label')}")
ok(len(c.get("/api/labels").get_json()) == 85, "labels route returns 85 rows")
for u in ("/api/plot/site.png?lat=23.64751&lon=85.28968", "/api/plot/overview.png", "/api/images/change_maps.png", "/api/images/sites_map.png"):
    r = c.get(u); ok(r.status_code == 200 and r.data[:4] == b"\x89PNG", f"{u} -> {r.status_code}")
r = c.get("/api/images/nope.png"); ok(r.status_code == 404 and "error" in r.get_json(), "missing image -> 404 json")

# ---- existing routes still work
a = c.get("/api/analyze?lat=23.314&lon=86.218").get_json(); ok("change_score" in a and len(a["timeseries"]) == 12, "analyze + timeseries still fine")
s = c.get("/api/sites?limit=2").get_json(); ok(len(s["features"]) >= 1, "sites route fine")
