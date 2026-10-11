import warnings
import numpy as np
from . import config

warnings.filterwarnings("ignore", message="Mean of empty slice")
warnings.filterwarnings("ignore", message="Degrees of freedom")
warnings.filterwarnings("ignore", message="All-NaN slice")


def linear_slope(stack, years):
    """Per-pixel least-squares slope (radiance per year), ignoring NaN."""
    x = np.asarray(years, dtype=np.float32)[:, None, None]
    valid = ~np.isnan(stack)
    n = valid.sum(axis=0)
    safe_n = np.maximum(n, 1)
    xmean = (x * valid).sum(axis=0) / safe_n
    ymean = np.nansum(stack, axis=0) / safe_n
    dx = (x - xmean) * valid
    dy = np.where(valid, stack - ymean, 0.0)
    denom = (dx ** 2).sum(axis=0)
    slope = (dx * dy).sum(axis=0) / np.where(denom == 0, np.nan, denom)
    slope[n < 3] = np.nan
    return slope


def compute_features(stack, years, n_edge=2):
    first = np.nanmean(stack[:n_edge], axis=0)
    last = np.nanmean(stack[-n_edge:], axis=0)
    return {
        "first_mean": first,
        "last_mean": last,
        "diff": last - first,
        "slope": linear_slope(stack, years),
        "std": np.nanstd(stack, axis=0),
    }


def baseline_change_flag(feats):
    """Rule-based 'big increase in lights' flag. Returns bool array."""
    f = feats
    flag = (
        (f["last_mean"] >= config.MIN_LAST_RADIANCE)
        & (f["diff"] >= config.MIN_DIFF)
        & (f["slope"] >= config.MIN_SLOPE)
    )
    return np.nan_to_num(flag, nan=False).astype(bool)


def emergence_flag(feats):
    """Dark in the early years, clearly lit now: new sites (dim-to-bright)."""
    f = feats
    flag = (
        (f["first_mean"] <= config.EMERGE_FIRST_MAX)
        & (f["last_mean"] >= config.EMERGE_LAST_MIN)
        & (f["slope"] >= config.EMERGE_SLOPE_MIN)
    )
    return np.nan_to_num(flag, nan=False).astype(bool)
