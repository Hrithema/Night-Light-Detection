"""Per-location features for the classifier, read from data/processed/features.npz."""
import numpy as np
from . import config
from .geo import pixel_centers, pixel_size_deg

FEATURE_NAMES = [
    "first_w", "last_w", "diff_w", "slope_w", "std_w", "log_ratio_w",
    "last_max_w", "diff_max_w", "diff_min_w",
    "first_ctx", "last_ctx", "diff_ctx",
]


def load_feature_maps(path=None):
    path = path or config.PROCESSED_DIR / "features.npz"
    d = np.load(path)
    return {k: d[k] for k in ("first_mean", "last_mean", "diff", "slope", "std")}


def _window(arr, r, c, half):
    r0, r1 = max(r - half, 0), min(r + half + 1, arr.shape[0])
    c0, c1 = max(c - half, 0), min(c + half + 1, arr.shape[1])
    return arr[r0:r1, c0:c1]


def to_rowcol(lat, lon):
    lons, lats = pixel_centers()
    px = pixel_size_deg()
    c = int(round((lon - lons[0]) / px))
    r = int(round((lats[0] - lat) / px))
    return r, c


def location_features(maps, lat, lon, half=3, ctx_half=15):
    """Feature vector (list in FEATURE_NAMES order) for one lat/lon."""
    r, c = to_rowcol(lat, lon)
    H, W = maps["last_mean"].shape
    if not (0 <= r < H and 0 <= c < W):
        raise ValueError(f"({lat}, {lon}) is outside the cropped area")

    def m(key, h):
        return float(np.nanmean(_window(maps[key], r, c, h)))

    first_w, last_w = m("first_mean", half), m("last_mean", half)
    first_c, last_c = m("first_mean", ctx_half), m("last_mean", ctx_half)
    vals = {
        "first_w": first_w, "last_w": last_w, "diff_w": last_w - first_w,
        "slope_w": m("slope", half), "std_w": m("std", half),
        "log_ratio_w": float(np.log1p(last_w) - np.log1p(first_w)),
        "last_max_w": float(np.nanmax(_window(maps["last_mean"], r, c, half))),
        "diff_max_w": float(np.nanmax(_window(maps["diff"], r, c, half))),
        "diff_min_w": float(np.nanmin(_window(maps["diff"], r, c, half))),
        "first_ctx": first_c, "last_ctx": last_c, "diff_ctx": last_c - first_c,
    }
    return [vals[k] for k in FEATURE_NAMES]
