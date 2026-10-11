"""Synthetic night-lights stack shaped like the real Jharkhand crop."""
import numpy as np
from . import config


def crop_shape():
    h, w = crop_slices()
    return h.stop - h.start, w.stop - w.start


def crop_slices(bbox=config.BBOX):
    west, south, east, north = bbox
    t_w, t_s, t_e, t_n = config.TILE_BOUNDS
    px = (t_e - t_w) / config.TILE_SIZE  # degrees per pixel
    c0 = int(round((west - t_w) / px))
    c1 = int(round((east - t_w) / px))
    r0 = int(round((t_n - north) / px))
    r1 = int(round((t_n - south) / px))
    return slice(r0, r1), slice(c0, c1)


def make_fake_stack(years=config.YEARS, seed=0):
    """Returns (radiance[T,H,W] float32 with NaN = bad, years)."""
    rng = np.random.default_rng(seed)
    H, W = crop_shape()
    yy, xx = np.mgrid[0:H, 0:W]
    T = len(years)
    stack = np.zeros((T, H, W), dtype=np.float32)

    def blob(cy, cx, r):
        return np.exp(-(((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r ** 2)))

    stable_city = blob(300, 300, 12) * 40          # bright, constant
    growing_city = blob(500, 700, 15)              # grows strongly
    growing_town = blob(800, 400, 8)               # grows mildly
    fading_site = blob(200, 900, 10) * 25          # gets darker

    for i in range(T):
        f = i / (T - 1)
        img = stable_city + 45 * f * growing_city + 12 * f * growing_town
        img += fading_site * (1 - 0.8 * f)
        img += rng.gamma(1.2, 0.15, size=(H, W))   # dim background noise
        stack[i] = img

    # Simulate bad pixels (clouds, no retrieval)
    for i in range(T):
        bad = rng.random((H, W)) < 0.03
        stack[i][bad] = np.nan
    return stack, list(years)
