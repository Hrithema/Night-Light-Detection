"""List every layer in the newest .h5 file of a region.
    python inspect_h5.py --region jharkhand
"""
import glob

import h5py

from src import config

files = sorted(glob.glob(str(config.RAW_DIR / "*.h5")))
print(len(files), "files found in", config.RAW_DIR)
with h5py.File(files[-1], "r") as f:
    def show(name, obj):
        if hasattr(obj, "shape"):
            print(name, obj.shape, obj.dtype)
    f.visititems(show)
