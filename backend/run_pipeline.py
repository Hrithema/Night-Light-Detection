"""Usage:
    python run_pipeline.py --real                       # region from regions.json (default jharkhand)
    python run_pipeline.py --real --region karnataka
    python run_pipeline.py --fake --region karnataka    # synthetic data, no downloads
    python run_pipeline.py --real --no-boundary         # skip the state-border mask
    python run_pipeline.py --inspect-boundary data/india.geojson   # list property names

The border mask uses data/india.geojson and the region's state name automatically.
"""
import argparse
import json
import numpy as np
from src import config
from src.features import compute_features, baseline_change_flag, emergence_flag
from src.plot import save_change_maps, save_sites_map
from src.sites import extract_sites, save_geojson, save_label_sheet


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fake", action="store_true")
    p.add_argument("--real", action="store_true")
    p.add_argument("--region", help="region name from regions.json (default: jharkhand)")
    p.add_argument("--boundary", help="GeoJSON with the state border (default: data/india.geojson)")
    p.add_argument("--state-name", help="state to select (default: the region's state)")
    p.add_argument("--state-key", help="property column holding the state name (default: st_nm)")
    p.add_argument("--no-boundary", action="store_true", help="do not mask to the state border")
    p.add_argument("--inspect-boundary", help="print property names of a GeoJSON and exit")
    args = p.parse_args()

    if args.inspect_boundary:
        from src.geo import list_properties
        list_properties(args.inspect_boundary)
        return
    if args.fake == args.real:
        p.error("choose exactly one of --fake / --real")

    print("region:", config.REGION, "| tile", config.TILE_CODE)
    if args.fake:
        from src.fake_data import make_fake_stack
        stack, years = make_fake_stack()
    else:
        from src.loader import load_stack
        stack, years = load_stack()

    print("stack shape:", stack.shape, "years:", years[0], "-", years[-1])
    print("share of NaN pixels:", round(float(np.isnan(stack).mean()), 4))

    mask = None
    boundary = args.boundary
    if not boundary and not args.no_boundary:
        if config.BOUNDARY_FILE.exists():
            boundary = str(config.BOUNDARY_FILE)
        else:
            print("NOTE: no border mask (data/india.geojson not found) - the whole rectangle is used.")
    if boundary:
        from src.geo import border_mask
        mask = border_mask(boundary,
                           args.state_name or config.STATE_NAME,
                           args.state_key or config.BOUNDARY_STATE_KEY)
        print("pixels inside border:", int(mask.sum()), "of", mask.size)
        stack = np.where(mask[None, :, :], stack, np.nan)

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    np.save(config.PROCESSED_DIR / "stack.npy", stack.astype(np.float16))  # for the API time series
    with open(config.PROCESSED_DIR / "years.json", "w") as fh:
        json.dump([int(y) for y in years], fh)

    feats = compute_features(stack, years)
    growth = baseline_change_flag(feats)
    emerge = emergence_flag(feats)
    flag_any = growth | emerge
    print("flagged pixels: growth", int(growth.sum()), "| emergence", int(emerge.sum()))

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(config.PROCESSED_DIR / "features.npz",
                        growth=growth, emergence=emerge, **feats)

    sites, _ = extract_sites(feats, growth, emerge, mask)
    print("sites found:", len(sites))

    save_geojson(sites, config.OUTPUT_DIR / "sites.geojson")
    n_rows = save_label_sheet(sites, feats, flag_any, mask,
                              config.PROCESSED_DIR / "label_sheet.csv")
    print("label sheet rows:", n_rows)

    print("saved:", save_change_maps(feats, flag_any, years))
    print("saved:", save_sites_map(feats, sites))
    print("saved:", config.OUTPUT_DIR / "sites.geojson")
    print("saved:", config.PROCESSED_DIR / "label_sheet.csv")


if __name__ == "__main__":
    main()
