"""Pure-numpy measurement functions: line profile, signal/background/noise/area/CNR.

See PREPROCESSING.md sections 2-6 for the exact formulas and rationale.
No Qt/matplotlib imports here on purpose, so this module is independently testable
and is the single source of truth shared by the live GUI and batch.py.
"""
from __future__ import annotations

import numpy as np

Point = tuple[float, float]
Rect = tuple[float, float, float, float]


def sample_line_profile(image: np.ndarray, p0: Point, p1: Point, num_points: int | None = None) -> np.ndarray:
    x0, y0 = p0
    x1, y1 = p1
    if num_points is None:
        length = np.hypot(x1 - x0, y1 - y0)
        num_points = max(int(round(length)) + 1, 2)
    xs = np.linspace(x0, x1, num_points)
    ys = np.linspace(y0, y1, num_points)
    col_idx = np.clip(np.round(xs).astype(int), 0, image.shape[1] - 1)
    row_idx = np.clip(np.round(ys).astype(int), 0, image.shape[0] - 1)
    return image[row_idx, col_idx].astype(np.float64)


def find_signal_and_background(profile: np.ndarray, exclusion_margin: int) -> dict:
    n = len(profile)
    idx_min = int(np.argmin(profile))
    signal = float(profile[idx_min])

    a = max(int(exclusion_margin), 0)
    lo = max(idx_min - a, 0)
    hi = min(idx_min + a + 1, n)
    background_points = np.concatenate([profile[:lo], profile[hi:]])

    background_mean = float(np.mean(background_points)) if background_points.size else float("nan")

    return {
        "idx_min": idx_min,
        "signal": signal,
        "background_mean": background_mean,
        "background_points": background_points,
        "exclusion_lo": lo,
        "exclusion_hi": hi,
    }


def compute_noise(image: np.ndarray, rect: Rect) -> dict:
    x0, y0, x1, y1 = rect
    h, w = image.shape[:2]

    xa, xb = sorted((x0, x1))
    ya, yb = sorted((y0, y1))
    xa = int(np.clip(round(xa), 0, w))
    xb = int(np.clip(round(xb), 0, w))
    ya = int(np.clip(round(ya), 0, h))
    yb = int(np.clip(round(yb), 0, h))

    roi = image[ya:yb, xa:xb]
    area_px = roi.size
    noise = float(np.std(roi)) if area_px else float("nan")

    return {
        "noise": noise,
        "area_px": area_px,
        "rect_clipped": (xa, ya, xb, yb),
        "n_pixels": area_px,
    }


def compute_cnr(signal: float, background_mean: float, noise: float) -> float:
    if noise == 0 or np.isnan(noise):
        return float("nan")
    return abs((signal - background_mean) / noise)


def measure(image: np.ndarray, line: tuple[Point, Point], rect: Rect, exclusion_margin: int) -> dict:
    p0, p1 = line
    profile = sample_line_profile(image, p0, p1)
    sb = find_signal_and_background(profile, exclusion_margin)
    noise_info = compute_noise(image, rect)
    cnr = compute_cnr(sb["signal"], sb["background_mean"], noise_info["noise"])

    return {
        "signal": sb["signal"],
        "background_mean": sb["background_mean"],
        "noise": noise_info["noise"],
        "area_px": noise_info["area_px"],
        "cnr": cnr,
        "idx_min": sb["idx_min"],
        "profile": profile,
        "exclusion_lo": sb["exclusion_lo"],
        "exclusion_hi": sb["exclusion_hi"],
        "background_points": sb["background_points"],
    }
