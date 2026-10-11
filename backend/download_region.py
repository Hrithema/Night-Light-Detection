"""Download the annual VNP46A4 tiles for a region, one file at a time, with retries.

Usage:
    python download_region.py --region karnataka
    python download_region.py --region karnataka --start 2013 --end 2024

Needs EARTHDATA_TOKEN in your .env file. Files land in data/<region>/raw/.
Regions that share a tile (for example jharkhand, bihar, west_bengal) can reuse
the same files: copy the .h5 files into data/<region>/raw/ instead of downloading again.
"""
import argparse
import os
import time

from dotenv import load_dotenv

load_dotenv()

from src import config  # noqa: E402  (after load_dotenv so --region is handled first)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", help="region name from regions.json")
    ap.add_argument("--start", type=int, default=config.YEARS[0])
    ap.add_argument("--end", type=int, default=config.YEARS[-1])
    args = ap.parse_args()

    import earthaccess

    earthaccess.login(strategy="environment")
    print("region:", config.REGION, "| tile", config.TILE_CODE, "| bbox", config.BBOX)

    results = earthaccess.search_data(
        short_name="VNP46A4",
        bounding_box=config.BBOX,
        temporal=(f"{args.start}-01-01", f"{args.end}-12-31"),
    )
    print(len(results), "granules found")

    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    bad_tiles = 0
    for i, r in enumerate(results):
        name = r.data_links()[0].split("/")[-1]
        if config.TILE_CODE not in name:
            bad_tiles += 1
            print(f"[{i+1}/{len(results)}] SKIP {name}: not tile {config.TILE_CODE}")
            continue
        path = config.RAW_DIR / name
        if path.exists() and path.stat().st_size > 10_000_000:
            print(f"[{i+1}/{len(results)}] already have {name}")
            continue
        for attempt in range(5):
            try:
                print(f"[{i+1}/{len(results)}] downloading {name} (try {attempt+1})", flush=True)
                earthaccess.download([r], str(config.RAW_DIR), threads=1)
                break
            except Exception as e:  # network drops are common; retry
                print("   failed:", e, flush=True)
                time.sleep(10)
    if bad_tiles:
        print(f"\nNOTE: {bad_tiles} granules were from other tiles. The region's box may span "
              "more than one tile; the pipeline handles one tile at a time.")


if __name__ == "__main__":
    main()
