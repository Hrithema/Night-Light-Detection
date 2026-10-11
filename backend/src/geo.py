"""Pixel <-> lon/lat helpers and the state-border mask (no geopandas needed)."""
import json
import numpy as np
from matplotlib.path import Path
from . import config
from .fake_data import crop_slices


def pixel_size_deg():
    t_w, _, t_e, _ = config.TILE_BOUNDS
    return (t_e - t_w) / config.TILE_SIZE


def pixel_centers(bbox=config.BBOX):
    """lon[W], lat[H] of pixel centres for the cropped array."""
    rows, cols = crop_slices(bbox)
    px = pixel_size_deg()
    t_w, _, _, t_n = config.TILE_BOUNDS
    lon = t_w + (np.arange(cols.start, cols.stop) + 0.5) * px
    lat = t_n - (np.arange(rows.start, rows.stop) + 0.5) * px
    return lon, lat


def list_properties(geojson_path):
    """Print the property names/values so you can find the state name column."""
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    feats = gj["features"] if gj.get("type") == "FeatureCollection" else [gj]
    print(len(feats), "features. Properties of the first 3:")
    for ft in feats[:3]:
        print(ft.get("properties"))


def _polygons(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    return []


def border_mask(geojson_path, state_name=None, state_key=None, bbox=config.BBOX):
    """Boolean mask (H, W): True inside the state polygon(s)."""
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    feats = gj["features"] if gj.get("type") == "FeatureCollection" else [gj]

    if state_name:
        def matches(ft):
            props = ft.get("properties") or {}
            vals = [props.get(state_key)] if state_key else props.values()
            return any(str(v).strip().lower() == state_name.lower() for v in vals)
        feats = [ft for ft in feats if matches(ft)]
    if not feats:
        raise ValueError("No feature matched. Use list_properties() to inspect the file.")

    lon, lat = pixel_centers(bbox)
    LON, LAT = np.meshgrid(lon, lat)
    pts = np.column_stack([LON.ravel(), LAT.ravel()])
    inside = np.zeros(len(pts), dtype=bool)

    for ft in feats:
        for poly in _polygons(ft["geometry"]):
            ring_in = Path(np.asarray(poly[0])[:, :2]).contains_points(pts)
            for hole in poly[1:]:
                ring_in &= ~Path(np.asarray(hole)[:, :2]).contains_points(pts)
            inside |= ring_in
    return inside.reshape(LON.shape)
