import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from . import config


def save_change_maps(feats, flag, years, path=None):
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = path or config.OUTPUT_DIR / "change_maps.png"
    fig, ax = plt.subplots(2, 2, figsize=(13, 11))

    vmax = np.nanpercentile(feats["last_mean"], 99.5)
    for a, key, title in [
        (ax[0, 0], "first_mean", f"Radiance ~{years[0]}"),
        (ax[0, 1], "last_mean", f"Radiance ~{years[-1]}"),
    ]:
        im = a.imshow(np.log1p(feats[key]), cmap="magma", vmin=0, vmax=np.log1p(vmax))
        a.set_title(title + " (log scale)")
        fig.colorbar(im, ax=a, fraction=0.04)

    lim = np.nanpercentile(np.abs(feats["diff"]), 99.5)
    im = ax[1, 0].imshow(feats["diff"], cmap="RdBu_r", vmin=-lim, vmax=lim)
    ax[1, 0].set_title("Difference (last - first)")
    fig.colorbar(im, ax=ax[1, 0], fraction=0.04)

    ax[1, 1].imshow(flag, cmap="gray_r")
    ax[1, 1].set_title(f"Flagged as big change: {int(flag.sum())} pixels")

    for a in ax.ravel():
        a.set_xticks([]); a.set_yticks([])
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def save_sites_map(feats, sites, path=None, top_n=30):
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = path or config.OUTPUT_DIR / "sites_map.png"
    from .geo import pixel_centers
    lon, lat = pixel_centers()
    px = (lon[1] - lon[0])

    fig, ax = plt.subplots(figsize=(11, 9))
    vmax = np.nanpercentile(feats["last_mean"], 99.5)
    ax.imshow(np.log1p(feats["last_mean"]), cmap="Greys_r", vmin=0, vmax=np.log1p(vmax))
    ranked = sorted(sites, key=lambda s: s["total_gain"], reverse=True)[:top_n]
    for s in ranked:
        x = (s["lon"] - lon[0]) / px
        y = (lat[0] - s["lat"]) / px
        color = "tab:red" if s["type"] == "growth" else "tab:cyan"
        ax.plot(x, y, "o", ms=7, mfc="none", mec=color, mew=1.5)
        ax.text(x + 6, y - 6, str(s["site_id"]), color=color, fontsize=8)
    ax.set_title(f"Top {len(ranked)} sites (red = growth, cyan = emergence)")
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
