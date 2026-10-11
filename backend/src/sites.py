"""Turn flagged pixels into 'sites' and export them for the website + labelling."""
import csv
import json
import numpy as np
from scipy import ndimage
from . import config
from .geo import pixel_centers, pixel_size_deg


def _pixel_area_km2(lat_deg):
    px_km = pixel_size_deg() * 111.32
    return px_km * px_km * np.cos(np.radians(lat_deg))


def extract_sites(feats, growth_flag, emerge_flag, mask=None, bbox=config.BBOX):
    """Group neighbouring flagged pixels into sites. Returns (list of dicts, label image)."""
    flag = growth_flag | emerge_flag
    if mask is not None:
        flag = flag & mask
    labels, n = ndimage.label(flag, structure=np.ones((3, 3)))   # 8-connectivity
    lon, lat = pixel_centers(bbox)

    sites = []
    for sid in range(1, n + 1):
        rr, cc = np.where(labels == sid)
        if len(rr) < config.MIN_SITE_PIXELS:
            continue
        area = float(sum(_pixel_area_km2(lat[r]) for r in rr))
        first = float(np.nanmean(feats["first_mean"][rr, cc]))
        last = float(np.nanmean(feats["last_mean"][rr, cc]))
        n_emerge = int(emerge_flag[rr, cc].sum())
        sites.append({
            "site_id": len(sites) + 1,
            "lat": round(float(lat[rr].mean()), 5),
            "lon": round(float(lon[cc].mean()), 5),
            "n_pixels": int(len(rr)),
            "area_km2": round(area, 2),
            "first_radiance": round(first, 2),
            "last_radiance": round(last, 2),
            "diff": round(last - first, 2),
            "log_ratio": round(float(np.log1p(last) - np.log1p(first)), 3),
            "slope": round(float(np.nanmean(feats["slope"][rr, cc])), 3),
            "peak_last": round(float(np.nanmax(feats["last_mean"][rr, cc])), 2),
            "total_gain": round(float(np.nansum(feats["diff"][rr, cc])), 1),
            "type": "emergence" if n_emerge > len(rr) / 2 else "growth",
            "_label_id": sid,
        })
    return sites, labels


def save_geojson(sites, path):
    features = []
    for s in sites:
        props = {k: v for k, v in s.items() if k not in ("lat", "lon", "_label_id")}
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
            "properties": props,
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)


def _maps_link(lat, lon):
    return f"https://www.google.com/maps/@{lat},{lon},2000m/data=!3m1!1e3"


def save_label_sheet(sites, feats, flag_any, mask, path, seed=0):
    """CSV for hand labelling: top sites by size*gain, plus random negatives."""
    ranked = sorted(sites, key=lambda s: s["total_gain"], reverse=True)
    top = ([s for s in ranked if s["type"] == "growth"][:30]
           + [s for s in ranked if s["type"] == "emergence"][:30])

    rows = []
    for s in top:
        rows.append({
            "site_id": s["site_id"], "candidate": s["type"],
            "lat": s["lat"], "lon": s["lon"],
            "area_km2": s["area_km2"], "first_radiance": s["first_radiance"],
            "last_radiance": s["last_radiance"],
            "maps_link": _maps_link(s["lat"], s["lon"]),
            "label": "", "notes": "",
        })

    # Random negatives: inside the state, not flagged, with a little change at most
    lon, lat = pixel_centers()
    ok = ~flag_any & np.isfinite(feats["diff"]) & (np.abs(feats["diff"]) < 1.0)
    if mask is not None:
        ok &= mask
    rr, cc = np.where(ok)
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(rr), size=min(config.N_NEGATIVE_SAMPLES, len(rr)), replace=False)
    for k, i in enumerate(pick):
        la, lo = round(float(lat[rr[i]]), 5), round(float(lon[cc[i]]), 5)
        rows.append({
            "site_id": f"neg{k+1}", "candidate": "negative_sample",
            "lat": la, "lon": lo, "area_km2": "", "first_radiance": "",
            "last_radiance": "", "maps_link": _maps_link(la, lo),
            "label": "", "notes": "",
        })

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            already = any((r.get("label") or "").strip() for r in csv.DictReader(f))
        if already:
            path = path.with_name("label_sheet_new.csv")
            print("NOTE: label_sheet.csv already has labels, so it was NOT overwritten. "
                  "New sheet saved as", path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return len(rows)
