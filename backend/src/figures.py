"""Matplotlib figures drawn on request (thread-safe: Figure objects, no pyplot)."""
import io
import math

import matplotlib

matplotlib.use("Agg")
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Circle

BG, PANEL, LINE = "#18233a", "#101826", "#2a3857"
TEXT, MUTED, SODIUM, COOL = "#e8ecf5", "#93a0bd", "#f4a93b", "#5bb8d4"
UNIT = "nW/cm²/sr"


def _cmap(name):
    cm = matplotlib.colormaps[name].copy()
    cm.set_bad("#0b1220")
    return cm


def _style(ax, small=False):
    ax.set_facecolor(PANEL)
    for s in ax.spines.values():
        s.set_color(LINE)
    ax.tick_params(colors=MUTED, labelsize=6 if small else 7, length=2)
    ax.title.set_color(TEXT)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)


def to_png(fig, dpi=110):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=fig.get_facecolor())
    return buf.getvalue()


def _lonlat(win, rc):
    r, c = rc
    return win["lons"][c], win["lats"][r]


def difference_figure(lat, lon, win, m):
    """Matrix-difference dashboard for one location.

    top    : first-years matrix, last-years matrix, difference D = last - first with hotspot
    middle : the difference matrix of every year (each year minus the year before)
    bottom : mean radiance per year, and the year-to-year change
    """
    A = m["_arrays"]
    years = m["years"]
    yearly = A["yearly"]                      # (T-1, h, w)
    n_diff = yearly.shape[0]
    per_row = 5
    d_rows = max(1, math.ceil(n_diff / per_row))
    ext = win["extent"]
    hot = A["hot_rc"]
    pr, pc = win["point_rc"]
    plon, plat = win["lons"][min(pc, len(win["lons"]) - 1)], win["lats"][min(pr, len(win["lats"]) - 1)]

    fig = Figure(figsize=(15, 4.6 + 2.5 * d_rows + 3.1), dpi=110)
    fig.patch.set_facecolor(BG)
    outer = fig.add_gridspec(3, 1, height_ratios=[4.0, 2.4 * d_rows, 3.0], hspace=0.42,
                             left=0.05, right=0.97, top=0.89, bottom=0.05)

    # ---------------- header
    g = m["growth_type"]
    fig.text(0.05, 0.955, f"Night-light change around {lat:.4f}, {lon:.4f}  ·  radius {m['radius_km']:g} km  ·  {m['period']}",
             color=TEXT, fontsize=15, fontweight="bold", va="center")
    fig.text(0.05, 0.925, f"{g['label']}  —  {g['why']}", color=SODIUM, fontsize=10, va="center")

    # ---------------- top row
    top = outer[0].subgridspec(1, 3, wspace=0.28)
    vmax = np.log1p(max(float(np.nanpercentile(A["last"], 99.5)), 1.0))
    n_edge = 2 if len(years) >= 4 else 1
    for i, (mat, ttl) in enumerate([
        (A["first"], f"Matrix A: radiance {years[0]}–{years[n_edge - 1]}"),
        (A["last"], f"Matrix B: radiance {years[-n_edge]}–{years[-1]}"),
    ]):
        ax = fig.add_subplot(top[0, i])
        _style(ax)
        im = ax.imshow(np.log1p(mat), cmap=_cmap("magma"), vmin=0, vmax=vmax, extent=ext, origin="upper")
        ax.set_title(ttl + " (log scale)", fontsize=9)
        ax.plot(plon, plat, "x", color=COOL, ms=7, mew=1.6)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cb.ax.tick_params(colors=MUTED, labelsize=6)
        cb.outline.set_edgecolor(LINE)

    ax = fig.add_subplot(top[0, 2])
    _style(ax)
    diff = A["diff"]
    lim = max(float(np.nanpercentile(np.abs(diff), 99.5)), 1.0)
    im = ax.imshow(diff, cmap=_cmap("RdBu_r"), vmin=-lim, vmax=lim, extent=ext, origin="upper")
    ax.set_title("Difference matrix D = B − A  (red = brighter, blue = darker)", fontsize=9)
    sm = A["smooth"]
    if np.isfinite(sm).sum() > 20:
        q = float(np.nanpercentile(sm, 95))
        if q > 0:
            ax.contour(win["lons"], win["lats"][::-1], sm[::-1], levels=[q], colors="white",
                       linewidths=1.0, linestyles="--")
    ax.plot(plon, plat, "x", color=COOL, ms=7, mew=1.6, label="your point")
    if hot is not None:
        hx, hy = _lonlat(win, hot)
        ax.plot(hx, hy, "*", color="#ffd84d", ms=14, mec="black", mew=0.8, label="largest increase")
        ax.annotate(f"largest gain\n+{m['hotspot']['gain']:.1f} {UNIT}", (hx, hy), xytext=(8, -26),
                    textcoords="offset points", color=TEXT, fontsize=7,
                    bbox=dict(boxstyle="round,pad=0.3", fc=BG, ec=LINE, alpha=0.9),
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    leg = ax.legend(loc="lower left", fontsize=6, facecolor=BG, edgecolor=LINE)
    for t in leg.get_texts():
        t.set_color(TEXT)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    cb.ax.tick_params(colors=MUTED, labelsize=6)
    cb.outline.set_edgecolor(LINE)
    cb.set_label(f"Δ {UNIT}", color=MUTED, fontsize=7)

    # ---------------- middle: the difference matrix of every year
    mid = outer[1].subgridspec(d_rows, per_row + 1, width_ratios=[1] * per_row + [0.06], wspace=0.12, hspace=0.35)
    ylim = max(float(np.nanpercentile(np.abs(yearly), 99)), 0.5)
    last_im = None
    for k in range(n_diff):
        ax = fig.add_subplot(mid[k // per_row, k % per_row])
        _style(ax, small=True)
        last_im = ax.imshow(yearly[k], cmap=_cmap("RdBu_r"), vmin=-ylim, vmax=ylim, extent=ext, origin="upper")
        mean_k = m["yearly_change"][k]
        col = SODIUM if (mean_k or 0) >= 0 else COOL
        ax.set_title(f"{years[k + 1]} − {years[k]}", fontsize=8, color=TEXT)
        ax.text(0.97, 0.04, "mean " + ("n/a" if mean_k is None else f"{mean_k:+.2f}"), transform=ax.transAxes,
                ha="right", va="bottom", fontsize=6.5, color=col,
                bbox=dict(boxstyle="round,pad=0.2", fc=BG, ec="none", alpha=0.8))
        if hot is not None:
            hx, hy = _lonlat(win, hot)
            rad = 1.6 * (win["lons"][1] - win["lons"][0])
            ax.add_patch(Circle((hx, hy), rad, fill=False, ec="#ffd84d", lw=1.0))
        ax.set_xticks([])
        ax.set_yticks([])
    if last_im is not None:
        cax = fig.add_subplot(mid[:, per_row])
        cb = fig.colorbar(last_im, cax=cax)
        cb.ax.tick_params(colors=MUTED, labelsize=6)
        cb.outline.set_edgecolor(LINE)
        cb.set_label(f"Δ {UNIT} (year − previous year)", color=MUTED, fontsize=7)

    # ---------------- bottom row
    bot = outer[2].subgridspec(1, 2, wspace=0.18)
    ax = fig.add_subplot(bot[0, 0])
    _style(ax)
    means = np.array([np.nan if v is None else v for v in m["yearly_means"]], dtype=float)
    ax.plot(years, means, "-o", color=SODIUM, lw=2, ms=4, label="window mean")
    if hot is not None:
        hs = win["cube"][:, hot[0], hot[1]]
        ax.plot(years, hs, "--s", color="#ffd84d", lw=1.3, ms=3, alpha=0.9, label="largest-increase pixel")
    ax.set_title("Radiance per year", fontsize=9)
    ax.set_ylabel(UNIT)
    ax.set_xticks(years)
    ax.tick_params(axis="x", labelrotation=45)
    ax.grid(alpha=0.15)
    leg = ax.legend(fontsize=7, facecolor=BG, edgecolor=LINE)
    for t in leg.get_texts():
        t.set_color(TEXT)

    ax = fig.add_subplot(bot[0, 1])
    _style(ax)
    yc = np.array([np.nan if v is None else v for v in m["yearly_change"]], dtype=float)
    xs = years[1:]
    bars = ax.bar(xs, np.nan_to_num(yc), color=[SODIUM if v >= 0 else COOL for v in np.nan_to_num(yc)], width=0.65)
    ax.axhline(0, color=MUTED, lw=0.8)
    if m["biggest_jump"]:
        j = m["biggest_jump"]
        idx = xs.index(j["year"])
        ax.annotate(f"biggest rise\n{j['year']}  {j['change']:+.2f}", (j["year"], yc[idx]), xytext=(0, 14),
                    textcoords="offset points", ha="center", color=TEXT, fontsize=7,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    top_v, bot_v = float(np.nanmax(yc, initial=0)), float(np.nanmin(yc, initial=0))
    pad = max(top_v - bot_v, 0.5) * 0.35
    ax.set_ylim(bot_v - (pad * 0.3 if bot_v < 0 else 0), top_v + pad)
    ax.set_title("Mean change from the previous year", fontsize=9)
    ax.set_ylabel(f"Δ {UNIT}")
    ax.set_xticks(xs)
    ax.tick_params(axis="x", labelrotation=45)
    ax.grid(alpha=0.15, axis="y")
    fig.text(0.97, 0.012, "Source: NASA Black Marble VNP46A4 (annual, ~500 m)  ·  generated with matplotlib",
             color=MUTED, fontsize=7, ha="right")
    return fig
