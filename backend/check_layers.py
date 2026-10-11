"""Print fill value, quality flags, grid extent and radiance range of the newest .h5 for a region.
    python check_layers.py --region jharkhand
"""
import glob

import h5py
import numpy as np

from src import config

path = sorted(glob.glob(str(config.RAW_DIR / "*.h5")))[-1]
base = "HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields/"
with h5py.File(path, "r") as f:
    rad = f[base + "AllAngle_Composite_Snow_Free"]
    print("file:", path)
    print("radiance attrs:", dict(rad.attrs))
    q = f[base + "AllAngle_Composite_Snow_Free_Quality"][:]
    vals, counts = np.unique(q, return_counts=True)
    print("quality values:", dict(zip(vals.tolist(), counts.tolist())))
    lat, lon = f[base + "lat"][:], f[base + "lon"][:]
    print("lat:", lat[0], "->", lat[-1], "| lon:", lon[0], "->", lon[-1])
    r = rad[:]
    print("radiance min/max:", np.nanmin(r), np.nanmax(r))
