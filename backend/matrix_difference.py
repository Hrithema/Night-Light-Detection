"""Classic image differencing: matrix of year A, matrix of year B, difference matrix.

    python matrix_difference.py --region jharkhand --y1 2013 --y2 2024
    python matrix_difference.py --region bihar --k 3
    python matrix_difference.py --fake              # synthetic data, no files needed

Each year is a matrix (a grid of numbers): one night-light radiance value per pixel.
Subtracting the two matrices, B - A, gives a third matrix: positive = brighter now,
negative = darker now. A pixel counts as 'changed' when its difference is more than
k standard deviations away from the average difference (a statistical threshold,
instead of a hand-picked number).
"""
import argparse

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src import config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", help="region from regions.json (default: jharkhand)")
    ap.add_argument("--y1", type=int, default=config.YEARS[0], help="earlier year")
    ap.add_argument("--y2", type=int, default=config.YEARS[-1], help="later year")
    ap.add_argument("--k", type=float, default=3.0, help="threshold = mean + k * std of the difference")
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--no-boundary", action="store_true")
    args = ap.parse_args()

    if args.fake:
        from src.fake_data import make_fake_stack
        stack, years = make_fake_stack()
        A, B = stack[years.index(args.y1)], stack[years.index(args.y2)]
    else:
        from src.loader import load_year
        A, B = load_year(args.y1), load_year(args.y2)

    if not args.no_boundary and config.BOUNDARY_FILE.exists():
        from src.geo import border_mask
        m = border_mask(str(config.BOUNDARY_FILE), config.STATE_NAME, config.BOUNDARY_STATE_KEY)
        A, B = np.where(m, A, np.nan), np.where(m, B, np.nan)

    D = B - A
    print(f"region: {config.REGION}   matrix A = {args.y1}, matrix B = {args.y2}")
    print(f"each matrix has shape {A.shape}  (rows x columns = {A.size:,} pixels)\n")

    # show a small piece of the matrices as plain numbers, at the biggest increase
    r, c = np.unravel_index(np.nanargmax(D), D.shape)
    sl = (slice(max(r - 2, 0), r + 3), slice(max(c - 2, 0), c + 3))
    np.set_printoptions(precision=1, suppress=True, linewidth=120)
    print(f"A 5x5 piece around pixel (row {r}, col {c}), where the lights grew the most:")
    print(f"\nmatrix A ({args.y1}):\n{A[sl]}")
    print(f"\nmatrix B ({args.y2}):\n{B[sl]}")
    print(f"\ndifference D = B - A:\n{D[sl]}\n")

    mu, sd = float(np.nanmean(D)), float(np.nanstd(D))
    up_t, down_t = mu + args.k * sd, mu - args.k * sd
    up, down = D > up_t, D < down_t
    print(f"difference matrix: mean {mu:.2f}, std {sd:.2f}")
    print(f"threshold (k={args.k}): brighter if D > {up_t:.2f}, darker if D < {down_t:.2f}")
    print(f"pixels much brighter: {int(np.nansum(up)):,} | much darker: {int(np.nansum(down)):,}")

    fig, ax = plt.subplots(2, 2, figsize=(13, 11))
    vmax = np.log1p(np.nanpercentile(B, 99.5))
    for a, M, t in [(ax[0, 0], A, f"Matrix A: radiance {args.y1}"), (ax[0, 1], B, f"Matrix B: radiance {args.y2}")]:
        im = a.imshow(np.log1p(M), cmap="magma", vmin=0, vmax=vmax)
        a.set_title(t + " (log scale)")
        fig.colorbar(im, ax=a, fraction=0.04)
    lim = np.nanpercentile(np.abs(D), 99.5)
    im = ax[1, 0].imshow(D, cmap="RdBu_r", vmin=-lim, vmax=lim)
    ax[1, 0].set_title(f"Difference matrix D = B - A  ({args.y2} - {args.y1})")
    fig.colorbar(im, ax=ax[1, 0], fraction=0.04, label="change in radiance")
    flag = np.zeros(D.shape)
    flag[up] = 1
    flag[down] = -1
    ax[1, 1].imshow(flag, cmap="bwr", vmin=-1, vmax=1)
    ax[1, 1].set_title(f"Changed pixels (|D - mean| > {args.k:g} std): red = brighter, blue = darker")
    for a in ax.ravel():
        a.set_xticks([])
        a.set_yticks([])
    fig.tight_layout()
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = config.OUTPUT_DIR / "matrix_difference.png"
    fig.savefig(out, dpi=110)
    print("\nsaved:", out)


if __name__ == "__main__":
    main()
