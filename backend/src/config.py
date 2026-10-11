import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---- Region (set with  --region <name>  or the NL_REGION environment variable) ----
REGION = os.environ.get("NL_REGION", "jharkhand").strip().lower()
with open(ROOT / "regions.json", encoding="utf-8") as _f:
    _REGIONS = json.load(_f)
if REGION not in _REGIONS:
    raise SystemExit(f"Unknown region '{REGION}'. Known: {', '.join(_REGIONS)} "
                     "(add new ones to regions.json)")
_R = _REGIONS[REGION]

RAW_DIR = ROOT / "data" / REGION / "raw"
PROCESSED_DIR = ROOT / "data" / REGION / "processed"
OUTPUT_DIR = ROOT / "outputs" / REGION
MODEL_DIR = ROOT / "models" / REGION

STATE_NAME = _R["state_name"]
TILE_CODE = _R["tile"]
BBOX = tuple(_R["bbox"])                    # west, south, east, north (degrees)
TILE_BOUNDS = tuple(_R["tile_bounds"])      # a tile is 10 x 10 degrees = 2400 x 2400 pixels
TILE_SIZE = 2400
YEARS = _R.get("years", list(range(2013, 2025)))

# India district boundaries (shared by all regions)
BOUNDARY_FILE = ROOT / "data" / "india.geojson"
BOUNDARY_STATE_KEY = "st_nm"

# Internal HDF5 paths. CHECK THESE against the output of inspect_h5.py
# and edit if the printed names are different.
RADIANCE_LAYER = (
    "HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields/"
    "AllAngle_Composite_Snow_Free"
)
QUALITY_LAYER = (
    "HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields/"
    "AllAngle_Composite_Snow_Free_Quality"
)
# Quality values to DROP (255 = fill; 2 = poor quality as far as I recall,
# confirm in Table 9 of the Black Marble user guide).
DROP_QUALITY_VALUES = (2, 255)
RADIANCE_FILL_MAX = -900.0   # radiance fill value is -999.9

# Baseline change rules (tune these once you see real maps)
MIN_LAST_RADIANCE = 5.0    # new/brighter place must be at least this bright
MIN_DIFF = 5.0             # last mean minus first mean
MIN_SLOPE = 0.5            # radiance gain per year

# "Emergence": places that were dark and became clearly lit
EMERGE_FIRST_MAX = 1.0
EMERGE_LAST_MIN = 3.0
EMERGE_SLOPE_MIN = 0.2

# Sites
MIN_SITE_PIXELS = 3          # ignore specks smaller than this
N_LABEL_SITES = 50           # top sites exported for hand-labelling
N_NEGATIVE_SAMPLES = 25      # random unflagged places exported as negatives

# Per-region overrides of any threshold above, e.g. {"thresholds": {"MIN_DIFF": 8.0}}
for _k, _v in _R.get("thresholds", {}).items():
    globals()[_k] = _v
