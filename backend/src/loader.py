"""Load real VNP46A4 .h5 files for each year and crop to Jharkhand."""
import glob
import numpy as np
from . import config
from .fake_data import crop_slices


def _scalar(x, default):
    if x is None:
        return default
    return np.asarray(x).ravel()[0]


def load_year(year, bbox=config.BBOX):
    import h5py  # imported here so fake-data mode works without h5py

    matches = sorted(glob.glob(str(config.RAW_DIR / f"VNP46A4.A{year}001.*.h5")))
    if not matches:
        raise FileNotFoundError(f"No file for {year} in {config.RAW_DIR}")
    rows, cols = crop_slices(bbox)

    with h5py.File(matches[0], "r") as f:
        rad_ds = f[config.RADIANCE_LAYER]
        qual_ds = f[config.QUALITY_LAYER]
        scale = float(_scalar(rad_ds.attrs.get("scale_factor"), 1.0))
        offset = float(_scalar(rad_ds.attrs.get("add_offset"), 0.0))
        raw = rad_ds[rows, cols].astype(np.float32)
        qual = qual_ds[rows, cols]

    bad = np.isin(qual, config.DROP_QUALITY_VALUES)
    bad |= raw <= config.RADIANCE_FILL_MAX      # -999.9 fill value
    out = raw * scale + offset
    out[bad] = np.nan
    out = np.clip(out, 0, None)                 # tiny negatives are sensor noise
    return out


def load_stack(years=config.YEARS, bbox=config.BBOX):
    arrays, ok_years = [], []
    for y in years:
        try:
            arrays.append(load_year(y, bbox))
            ok_years.append(y)
        except FileNotFoundError as e:
            print("skipping:", e)
    return np.stack(arrays), ok_years
