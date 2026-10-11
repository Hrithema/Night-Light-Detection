"""Night-Light API (Flask). One server for the whole project.

Run:   python api.py                      -> http://localhost:5001   (region: jharkhand)
       python api.py --region karnataka

Needs: python run_pipeline.py --real has been run for the region, so that
       data/<region>/processed/{features.npz, stack.npy, years.json} and
       outputs/<region>/sites.geojson exist. The classifier and the AI summary are optional.

Routes
  GET /api/health                              status, region, model loaded
  GET /api/meta                                project / region facts for the About tab
  GET /api/sites?type=&min_area=&limit=        detected sites (GeoJSON)
  GET /api/analyze?lat=&lon=                   change score, label, features, yearly radiance
  GET /api/timeseries?lat=&lon=                yearly radiance
  GET /api/plot/difference.png?lat=&lon=&radius_km=   matplotlib: matrix difference dashboard
  GET /api/insight?lat=&lon=&radius_km=&ai=1   area report: growth type + AI / web context
  GET /api/labels, /api/lookup, /api/plot/site.png, /api/plot/overview.png   hand labels
  GET /api/images/<name>.png                   pipeline figures
"""
import json
import os
from functools import lru_cache

import numpy as np
from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, request, send_from_directory

load_dotenv()

from src import config  # noqa: E402
from src import figures, insight, window  # noqa: E402
from src.labels_bp import labels_bp  # noqa: E402
from src.site_features import FEATURE_NAMES, load_feature_maps, location_features, to_rowcol  # noqa: E402

app = Flask(__name__)
app.register_blueprint(labels_bp)
_cache = {}
MIN_RADIUS_KM, MAX_RADIUS_KM = 2.0, 40.0


@app.after_request
def add_cors(resp):  # dev only: lets a separately hosted front end call this API
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


# ------------------------------------------------------------------ helpers
def _maps():
    if "maps" not in _cache:
        _cache["maps"] = load_feature_maps()
    return _cache["maps"]


def _model():
    if "model" not in _cache:
        path = config.MODEL_DIR / "site_classifier.joblib"
        if path.exists():
            import joblib
            _cache["model"] = joblib.load(path)
        else:
            _cache["model"] = None
    return _cache["model"]


def _latlon():
    try:
        lat, lon = float(request.args["lat"]), float(request.args["lon"])
    except (KeyError, ValueError):
        abort(400, "lat and lon are required numbers")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        abort(400, "Coordinates are out of range")
    r, c = to_rowcol(lat, lon)
    H, W = _maps()["last_mean"].shape
    if not (0 <= r < H and 0 <= c < W):
        abort(400, f"That point is outside the {config.STATE_NAME} study area.")
    return lat, lon, r, c


def _radius():
    try:
        r = float(request.args.get("radius_km", 10))
    except ValueError:
        abort(400, "radius_km must be a number")
    return min(max(r, MIN_RADIUS_KM), MAX_RADIUS_KM)


def _timeseries(r, c, half=1):
    st, years = window.stack()
    win = np.asarray(st[:, max(r - half, 0):r + half + 1, max(c - half, 0):c + half + 1], dtype=np.float32)
    vals = np.nanmean(win.reshape(len(years), -1), axis=1)
    return [{"year": y, "radiance": None if np.isnan(v) else round(float(v), 2)}
            for y, v in zip(years, vals)]


# ------------------------------------------------------------------ status
@app.get("/api/health")
def health():
    return jsonify(status="ok", region=config.REGION, model_loaded=_model() is not None,
                   ai_available=bool(os.environ.get("ANTHROPIC_API_KEY")))


@app.get("/api/meta")
def meta():
    sites_path = config.OUTPUT_DIR / "sites.geojson"
    n_sites = None
    if sites_path.exists():
        try:
            n_sites = len(json.load(open(sites_path, encoding="utf-8"))["features"])
        except Exception:
            pass
    years = None
    try:
        years = window.stack()[1]
    except Exception:
        pass
    return jsonify(region=config.REGION, state=config.STATE_NAME, tile=config.TILE_CODE,
                   bbox=list(config.BBOX), years=years, sites_detected=n_sites,
                   model_loaded=_model() is not None,
                   ai_available=bool(os.environ.get("ANTHROPIC_API_KEY")),
                   radius_km={"min": MIN_RADIUS_KM, "max": MAX_RADIUS_KM, "default": 10})


# ------------------------------------------------------------------ data routes
@app.get("/api/sites")
def sites():
    """GeoJSON of detected sites. Optional: ?type=growth|emergence &min_area=km2 &limit=n"""
    path = config.OUTPUT_DIR / "sites.geojson"
    if not path.exists():
        abort(404, "sites.geojson not found - run run_pipeline.py first")
    gj = json.load(open(path, encoding="utf-8"))
    feats = gj["features"]
    t, min_area = request.args.get("type"), float(request.args.get("min_area", 0))
    feats = [f for f in feats
             if (not t or f["properties"]["type"] == t) and f["properties"]["area_km2"] >= min_area]
    feats.sort(key=lambda f: f["properties"]["total_gain"], reverse=True)
    if "limit" in request.args:
        feats = feats[: int(request.args["limit"])]
    return jsonify(type="FeatureCollection", features=feats)


@app.get("/api/timeseries")
def timeseries():
    _, _, r, c = _latlon()
    return jsonify(timeseries=_timeseries(r, c))


@app.get("/api/analyze")
def analyze():
    """Everything the front end needs for one clicked point."""
    lat, lon, r, c = _latlon()
    x = location_features(_maps(), lat, lon)
    f = dict(zip(FEATURE_NAMES, x))
    rule_score = float(np.clip(f["log_ratio_w"] / 2.0, 0, 1))   # how strongly the lights rose (0..1)
    out = {"lat": lat, "lon": lon, "change_score": round(rule_score, 3), "label": "unclassified",
           "label_source": "rule", "features": {k: round(v, 3) for k, v in f.items()},
           "timeseries": _timeseries(r, c)}
    bundle = _model()
    if bundle is not None:
        proba = bundle["model"].predict_proba([x])[0]
        classes = bundle["classes"]
        out["label"] = classes[int(np.argmax(proba))]
        out["label_source"] = "model"
        out["probabilities"] = {k: round(float(p), 3) for k, p in zip(classes, proba)}
        if "no_change" in classes:
            out["change_score"] = round(1 - float(proba[classes.index("no_change")]), 3)
    elif rule_score >= 0.5:
        out["label"] = "likely_change"
    else:
        out["label"] = "no_clear_change"
    return jsonify(out)


# ------------------------------------------------------------------ matplotlib, drawn on request
@lru_cache(maxsize=64)
def _difference_png(region, lat3, lon3, radius):
    win = window.cut_window(lat3, lon3, radius)
    m = window.measure(win)
    return figures.to_png(figures.difference_figure(lat3, lon3, win, m))


@app.get("/api/plot/difference.png")
def plot_difference():
    """Matrix-difference dashboard for the entered coordinates (generated fresh by matplotlib)."""
    lat, lon, _, _ = _latlon()
    png = _difference_png(config.REGION, round(lat, 4), round(lon, 4), _radius())
    return Response(png, mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=300",
                             "Content-Disposition": f'inline; filename="difference_{lat:.4f}_{lon:.4f}.png"'})


# ------------------------------------------------------------------ area report (AI / web context)
@app.get("/api/insight")
def area_insight():
    """What kind of growth happened around the point over the last ~10 years."""
    lat, lon, _, _ = _latlon()
    radius = _radius()
    use_ai = request.args.get("ai", "1") not in ("0", "false", "no")
    win = window.cut_window(lat, lon, radius)
    m = window.measure(win)
    data = insight.build_report(round(lat, 4), round(lon, 4), radius, m, use_ai=use_ai)
    data["query"] = {"lat": lat, "lon": lon, "radius_km": radius, "ai": use_ai}
    return jsonify(data)


# ------------------------------------------------------------------ pipeline images
@app.get("/api/images/<path:name>")
def images(name):
    """change_maps.png / sites_map.png written by the pipeline (falls back to assets/)."""
    if not name.lower().endswith(".png"):
        abort(404)
    for folder in (config.OUTPUT_DIR, config.ROOT / "assets"):
        if (folder / name).is_file():
            return send_from_directory(folder, name)
    abort(404, f"{name} not found. Run run_pipeline.py first.")


# ------------------------------------------------------------------ errors (always JSON)
@app.errorhandler(window.OutsideAreaError)
def outside(e):
    return jsonify(error=str(e)), 400


@app.errorhandler(FileNotFoundError)
def not_ready(e):
    return jsonify(error=f"Data not ready: {e}"), 503


@app.errorhandler(400)
@app.errorhandler(404)
def err(e):
    return jsonify(error=e.description), e.code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
