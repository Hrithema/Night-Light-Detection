"""
Hand-label routes (the friend's label_api.py, merged into the main API as a Flask blueprint).

  GET /api/labels                    every row of the label sheet (JSON)
  GET /api/lookup?lat=..&lon=..      labels for the typed coordinates (JSON)
  GET /api/plot/site.png?lat=&lon=   matplotlib: radiance first vs last + location map
  GET /api/plot/overview.png         matplotlib: overview of the whole sheet

The sheet is data/<region>/processed/label_sheet.csv; if it is missing or has no labels,
the copy bundled in assets/label_sheet.csv is used so the front end always has data.
"""
import io
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no GUI window; we only write PNG bytes
import numpy as np
import pandas as pd
from flask import Blueprint, Response, jsonify, request
from matplotlib.figure import Figure  # Figure (not pyplot) is thread-safe

from . import config

BUNDLED_CSV = config.ROOT / "assets" / "label_sheet.csv"

# A typed point counts as "this site" when it is within EXACT_KM of a sheet row,
# and as "near" this site when it is within NEAR_KM.
EXACT_KM = 0.5
NEAR_KM = 5.0

LABEL_COLORS = {
    "no_change": "#7f8aa3",
    "urban_growth": "#f4a93b",
    "industrial": "#e5604d",
    "mining": "#9b6bd3",
}

labels_bp = Blueprint("labels", __name__)


# ----------------------------------------------------------------- data
_sheet = {"path": None, "mtime": None, "df": None}


def _csv_path() -> Path:
    mine = config.PROCESSED_DIR / "label_sheet.csv"
    if mine.exists():
        try:
            if pd.read_csv(mine)["label"].notna().any():
                return mine
        except Exception:
            pass
    return BUNDLED_CSV


def load_sites() -> pd.DataFrame:
    path = _csv_path()
    mtime = path.stat().st_mtime
    if _sheet["path"] != path or _sheet["mtime"] != mtime:
        df = pd.read_csv(path, dtype={"site_id": str})
        df["label"] = df["label"].fillna("unlabelled").str.strip().str.lower()
        df["notes"] = df["notes"].fillna("")
        _sheet.update(path=path, mtime=mtime, df=df)
    return _sheet["df"]


class _Sites:
    """Module-level handle so the old code that used SITES keeps working."""
    def __getattr__(self, name):
        return getattr(load_sites(), name)
    def __getitem__(self, key):
        return load_sites()[key]
    def __len__(self):
        return len(load_sites())
    def groupby(self, *a, **k):
        return load_sites().groupby(*a, **k)
    @property
    def iloc(self):
        return load_sites().iloc


SITES = _Sites()


def km_between(lat1, lon1, lat2, lon2):
    """Great-circle distance in km (works on numpy arrays)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def clean(v):
    """NaN -> None so jsonify produces valid JSON."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v.item() if hasattr(v, "item") else v


def row_to_dict(row, dist_km=None):
    d = {
        "site_id": row["site_id"],
        "candidate": row["candidate"],
        "lat": clean(row["lat"]),
        "lon": clean(row["lon"]),
        "area_km2": clean(row["area_km2"]),
        "first_radiance": clean(row["first_radiance"]),
        "last_radiance": clean(row["last_radiance"]),
        "label": row["label"],
        "notes": row["notes"],
        "maps_link": row["maps_link"],
    }
    f, l = d["first_radiance"], d["last_radiance"]
    d["change"] = None if f is None or l is None else round(l - f, 2)
    d["change_pct"] = None if f is None or l is None or f <= 0 else round((l - f) / f * 100, 1)
    if dist_km is not None:
        d["distance_km"] = round(float(dist_km), 3)
    return d


def parse_point():
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except (KeyError, ValueError):
        return None, None, (jsonify(error="Give numeric ?lat= and ?lon="), 400)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None, (jsonify(error="Coordinates out of range"), 400)
    return lat, lon, None


def nearest(lat, lon, n=5):
    dist = km_between(lat, lon, SITES["lat"].to_numpy(), SITES["lon"].to_numpy())
    order = np.argsort(dist)[:n]
    return [(SITES.iloc[i], float(dist[i])) for i in order]


# ----------------------------------------------------------------- JSON routes
@labels_bp.get("/api/labels")
def all_labels():
    return jsonify([row_to_dict(r) for _, r in SITES.iterrows()])


@labels_bp.get("/api/lookup")
def lookup():
    lat, lon, err = parse_point()
    if err:
        return err
    near = nearest(lat, lon, n=5)
    best, best_d = near[0]
    if best_d <= EXACT_KM:
        match = "exact"
    elif best_d <= NEAR_KM:
        match = "near"
    else:
        match = "none"
    return jsonify(
        query={"lat": lat, "lon": lon},
        match=match,
        site=row_to_dict(best, best_d) if match != "none" else None,
        nearest=[row_to_dict(r, d) for r, d in near],
        thresholds_km={"exact": EXACT_KM, "near": NEAR_KM},
    )


# ----------------------------------------------------------------- matplotlib
def png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return Response(buf.getvalue(), mimetype="image/png",
                    headers={"Cache-Control": "no-store"})


def style(fig, axes):
    fig.patch.set_facecolor("#18233a")
    for ax in np.atleast_1d(axes):
        ax.set_facecolor("#101826")
        for s in ax.spines.values():
            s.set_color("#2a3857")
        ax.tick_params(colors="#93a0bd", labelsize=8)
        ax.xaxis.label.set_color("#93a0bd")
        ax.yaxis.label.set_color("#93a0bd")
        ax.title.set_color("#e8ecf5")


@labels_bp.get("/api/plot/site.png")
def plot_site():
    """Two panels: radiance first vs last (left) and where the point sits (right)."""
    lat, lon, err = parse_point()
    if err:
        return err
    site, dist = nearest(lat, lon, n=1)[0]
    matched = dist <= NEAR_KM
    color = LABEL_COLORS.get(site["label"], "#5bb8d4")

    fig = Figure(figsize=(9, 3.8), dpi=130)
    ax1, ax2 = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1, 1.3]})
    style(fig, [ax1, ax2])

    # ---- left: radiance over time (the sheet stores the first and last year)
    f, l = site["first_radiance"], site["last_radiance"]
    if matched and not (pd.isna(f) or pd.isna(l)):
        bars = ax1.bar(["~2013", "~2024"], [f, l], color=["#4a60a8", color], width=0.55)
        ax1.bar_label(bars, fmt="%.1f", color="#e8ecf5", fontsize=9, padding=3)
        pct = f"{(l - f) / f * 100:+.0f}%" if f > 0 else "from ~0"
        ax1.set_title(f"Site {site['site_id']}: {site['label'].replace('_', ' ')} ({pct})", fontsize=10)
        ax1.set_ylabel("Radiance (nW/cm$^2$/sr)")
        ax1.set_ylim(0, max(f, l) * 1.2)
    else:
        msg = ("Negative sample:\nno radiance recorded" if matched
               else "No labelled site\nwithin %.0f km" % NEAR_KM)
        ax1.text(0.5, 0.5, msg, ha="center", va="center", color="#93a0bd", fontsize=11,
                 transform=ax1.transAxes)
        ax1.set_xticks([]); ax1.set_yticks([])
        ax1.set_title("Radiance", fontsize=10)

    # ---- right: map of every site in the sheet, selected one highlighted
    for lab, grp in SITES.groupby("label"):
        ax2.scatter(grp["lon"], grp["lat"], s=16, color=LABEL_COLORS.get(lab, "#5bb8d4"),
                    alpha=0.55, label=lab.replace("_", " "), linewidths=0)
    if matched:
        ax2.scatter([site["lon"]], [site["lat"]], s=140, facecolors="none",
                    edgecolors="#ffffff", linewidths=1.8, zorder=5)
    ax2.scatter([lon], [lat], marker="x", s=60, color="#ff4d6d", zorder=6, label="your point")
    ax2.set_xlabel("Longitude"); ax2.set_ylabel("Latitude")
    ax2.set_title(f"Your point ({lat:.4f}, {lon:.4f})", fontsize=10)
    ax2.set_aspect("equal", adjustable="datalim")
    ax2.grid(alpha=0.15)
    leg = ax2.legend(fontsize=7, loc="lower left", facecolor="#18233a", edgecolor="#2a3857")
    for t in leg.get_texts():
        t.set_color("#e8ecf5")
    fig.tight_layout()
    return png(fig)


@labels_bp.get("/api/plot/overview.png")
def plot_overview():
    """Whole sheet: label map + first-vs-last radiance scatter."""
    fig = Figure(figsize=(10, 4.2), dpi=130)
    ax1, ax2 = fig.subplots(1, 2)
    style(fig, [ax1, ax2])

    for lab, grp in SITES.groupby("label"):
        c = LABEL_COLORS.get(lab, "#5bb8d4")
        ax1.scatter(grp["lon"], grp["lat"], s=30, color=c, alpha=0.85,
                    label=f"{lab.replace('_', ' ')} ({len(grp)})", linewidths=0)
        g = grp.dropna(subset=["first_radiance", "last_radiance"])
        ax2.scatter(g["first_radiance"], g["last_radiance"], s=30, color=c, alpha=0.85, linewidths=0)
    ax1.set_title(f"Hand labels across {config.STATE_NAME}", fontsize=10)
    ax1.set_xlabel("Longitude"); ax1.set_ylabel("Latitude")
    ax1.set_aspect("equal", adjustable="datalim"); ax1.grid(alpha=0.15)
    leg = ax1.legend(fontsize=7, loc="lower left", facecolor="#18233a", edgecolor="#2a3857")
    for t in leg.get_texts():
        t.set_color("#e8ecf5")

    top = float(np.nanmax(SITES[["first_radiance", "last_radiance"]].to_numpy())) * 1.05
    ax2.plot([0, top], [0, top], ls="--", color="#5d6b8b", lw=1)
    ax2.text(top * 0.62, top * 0.5, "no change", color="#5d6b8b", fontsize=8, rotation=35)
    ax2.set_xlim(0, top); ax2.set_ylim(0, top)
    ax2.set_xlabel("Radiance ~2013"); ax2.set_ylabel("Radiance ~2024")
    ax2.set_title("Growth over time (above the line = brighter now)", fontsize=10)
    ax2.grid(alpha=0.15)
    fig.tight_layout()
    return png(fig)
