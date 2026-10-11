"""Cut a window out of the stack around a point and measure how the lights changed.

Everything here works on the matrices produced by run_pipeline.py:
    data/<region>/processed/stack.npy     (years, rows, cols) radiance, NaN = no data
    data/<region>/processed/years.json
    data/<region>/processed/features.npz  (for the region-wide change threshold)
"""
import json
import math
import warnings

import numpy as np
from scipy import ndimage

from . import config
from .geo import pixel_centers, pixel_size_deg
from .site_features import to_rowcol

KM_PER_DEG = 111.32
_cache = {}
warnings.filterwarnings("ignore", message="Mean of empty slice")
warnings.filterwarnings("ignore", message="All-NaN slice")


class OutsideAreaError(ValueError):
    """The point is outside the processed area, or has no data (masked / outside the border)."""


# ------------------------------------------------------------------ loading
def stack():
    if "stack" not in _cache:
        path = config.PROCESSED_DIR / "stack.npy"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Run: python run_pipeline.py --real")
        _cache["stack"] = np.load(path, mmap_mode="r")
        with open(config.PROCESSED_DIR / "years.json") as fh:
            _cache["years"] = json.load(fh)
    return _cache["stack"], _cache["years"]


def region_threshold(k=3.0):
    """Region-wide 'big change' thresholds from the whole difference matrix: mean +/- k * std."""
    key = ("thr", k)
    if key not in _cache:
        d = np.load(config.PROCESSED_DIR / "features.npz")["diff"]
        mu, sd = float(np.nanmean(d)), float(np.nanstd(d))
        _cache[key] = {"mean": mu, "std": sd, "up": mu + k * sd, "down": mu - k * sd, "k": k}
    return _cache[key]


# ------------------------------------------------------------------ window
def km_per_pixel(lat):
    ky = pixel_size_deg() * KM_PER_DEG
    return ky, ky * math.cos(math.radians(lat))


def cut_window(lat, lon, radius_km, n_years=11):
    """Return a dict with the cube (T, h, w), years, lat/lon edges of the window."""
    st, years = stack()
    r, c = to_rowcol(lat, lon)
    T, H, W = st.shape
    if not (0 <= r < H and 0 <= c < W):
        raise OutsideAreaError(f"That point is outside the {config.STATE_NAME} study area.")
    ky, kx = km_per_pixel(lat)
    hr, hc = max(int(math.ceil(radius_km / ky)), 2), max(int(math.ceil(radius_km / kx)), 2)
    r0, r1 = max(r - hr, 0), min(r + hr + 1, H)
    c0, c1 = max(c - hc, 0), min(c + hc + 1, W)

    t0 = max(T - n_years, 0)
    cube = np.asarray(st[t0:, r0:r1, c0:c1], dtype=np.float32)
    if not np.isfinite(cube).any():
        raise OutsideAreaError(
            f"No night-light data here. The point is outside the {config.STATE_NAME} border "
            "(pixels outside it are masked).")

    lons, lats = pixel_centers()
    px = pixel_size_deg()
    return {
        "cube": cube,
        "years": [int(y) for y in years[t0:]],
        "row0": r0, "col0": c0,
        "point_rc": (r - r0, c - c0),
        # extent for imshow: left, right, bottom, top  (pixel edges, in degrees)
        "extent": (lons[c0] - px / 2, lons[c1 - 1] + px / 2, lats[r1 - 1] - px / 2, lats[r0] + px / 2),
        "lons": lons[c0:c1], "lats": lats[r0:r1],
        "radius_km": radius_km,
    }


def _nanmean_stack(a):
    with np.errstate(all="ignore"):
        return np.nanmean(a, axis=0)


def yearly_differences(cube):
    """(T-1, h, w): each year minus the year before."""
    return np.diff(cube, axis=0)


def _smooth(m):
    """3x3 mean that ignores NaN, so single noisy pixels don't win."""
    ok = np.isfinite(m)
    num = ndimage.uniform_filter(np.where(ok, m, 0.0), size=3, mode="nearest")
    den = ndimage.uniform_filter(ok.astype(float), size=3, mode="nearest")
    with np.errstate(all="ignore"):
        out = num / den
    out[den < 0.5] = np.nan
    return out


# ------------------------------------------------------------------ measurements
def measure(win):
    """Numbers that describe how the lights changed inside the window."""
    cube, years = win["cube"], win["years"]
    n_edge = 2 if len(years) >= 4 else 1
    first, last = _nanmean_stack(cube[:n_edge]), _nanmean_stack(cube[-n_edge:])
    diff = last - first                      # the difference matrix D = last - first
    yearly = yearly_differences(cube)

    with np.errstate(all="ignore"):
        means = np.nanmean(cube.reshape(len(years), -1), axis=1)
        yr_change = np.nanmean(yearly.reshape(len(yearly), -1), axis=1)
    f_mean, l_mean = float(np.nanmean(first)), float(np.nanmean(last))

    smooth = _smooth(diff)
    if np.isfinite(smooth).any():
        hr, hc = np.unravel_index(np.nanargmax(smooth), smooth.shape)
        hot = {
            "lat": round(float(win["lats"][hr]), 5), "lon": round(float(win["lons"][hc]), 5),
            "gain": round(float(smooth[hr, hc]), 2), "rc": (int(hr), int(hc)),
            "first": round(float(first[hr, hc]), 2), "last": round(float(last[hr, hc]), 2),
        }
    else:
        hot = None

    thr = region_threshold()
    finite = np.isfinite(diff)
    n = max(int(finite.sum()), 1)
    up, down = int((diff > thr["up"]).sum()), int((diff < thr["down"]).sum())
    emerged = int(((first < 1.0) & (last >= 3.0)).sum())

    x = np.array(years, dtype=float)
    ok = np.isfinite(means)
    slope = float(np.polyfit(x[ok], means[ok], 1)[0]) if ok.sum() >= 3 else None

    j = int(np.nanargmax(yr_change)) if np.isfinite(yr_change).any() else None
    d = int(np.nanargmin(yr_change)) if np.isfinite(yr_change).any() else None
    pct = None if f_mean < 0.5 else round((l_mean - f_mean) / f_mean * 100, 1)

    out = {
        "years": years,
        "period": f"{years[0]}-{years[-1]}",
        "radius_km": win["radius_km"],
        "pixels": n,
        "area_km2": round(float(n * np.prod(km_per_pixel(float(win["lats"].mean())))), 1),
        "mean_first": round(f_mean, 2), "mean_last": round(l_mean, 2),
        "change": round(l_mean - f_mean, 2), "change_pct": pct,
        "slope_per_year": None if slope is None else round(slope, 3),
        "share_brighter_pct": round(100 * up / n, 1),
        "share_darker_pct": round(100 * down / n, 1),
        "share_new_light_pct": round(100 * emerged / n, 1),
        "yearly_means": [None if np.isnan(v) else round(float(v), 2) for v in means],
        "yearly_change": [None if np.isnan(v) else round(float(v), 3) for v in yr_change],
        "biggest_jump": None if j is None else {"year": years[j + 1], "change": round(float(yr_change[j]), 2)},
        "biggest_drop": (None if d is None or yr_change[d] >= 0
                         else {"year": years[d + 1], "change": round(float(yr_change[d]), 2)}),
        "hotspot": None if hot is None else {k: v for k, v in hot.items() if k != "rc"},
        "threshold": {"up": round(thr["up"], 2), "down": round(thr["down"], 2), "k": thr["k"]},
    }
    out["growth_type"] = classify_growth(out)
    # arrays needed by the figures (not JSON-serialised)
    out["_arrays"] = {"first": first, "last": last, "diff": diff, "yearly": yearly,
                      "smooth": smooth, "hot_rc": None if hot is None else hot["rc"]}
    return out


def classify_growth(m):
    """Plain-language growth type from the light measurements alone (rule-based)."""
    f, l, ch = m["mean_first"], m["mean_last"], m["change"]
    br, new = m["share_brighter_pct"], m["share_new_light_pct"]
    if m["share_darker_pct"] > max(br, 2) and ch < 0:
        return {"key": "decline", "label": "Decline in lighting",
                "why": "Most of the strongly changed pixels got darker."}
    if new >= 8 or (f < 1.0 and l >= 2.0):
        return {"key": "new_development", "label": "New development in a previously dark area",
                "why": f"{new:.0f}% of the area went from almost dark to clearly lit."}
    if br >= 5 and f >= 3.0:
        return {"key": "intensification", "label": "Intensification of an already-lit area",
                "why": "Existing lights became much brighter (densification, new industry or housing)."}
    if br >= 2 or ch >= 1.0:
        return {"key": "gradual_growth", "label": "Gradual growth in lighting",
                "why": "A modest, widespread rise in brightness (typical of electrification and road lighting)."}
    return {"key": "stable", "label": "Little or no change",
            "why": "Brightness stayed within normal year-to-year variation."}
