"""Image loading for .raw (headerless 16-bit unsigned little-endian) and .bmp files.

See PREPROCESSING.md section 1 for the exact format rules. The key invariant:
`LoadedImage.raw` is the untouched numeric array used for ALL measurements;
`LoadedImage.display` is a uint8 stretch used ONLY for on-screen display.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

GRAYSCALE_MODES = {"L", "I", "I;16", "I;16B", "I;16L"}


@dataclass
class LoadedImage:
    raw: np.ndarray
    display: np.ndarray
    path: str
    width: int
    height: int
    source_dtype: np.dtype


def load_raw(path: str, width: int, height: int) -> np.ndarray:
    if width <= 0 or height <= 0:
        raise ValueError(f"width/height must be > 0 (got {width}x{height})")
    data = Path(path).read_bytes()
    expected = width * height * 2
    if len(data) != expected:
        raise ValueError(
            f"'{Path(path).name}': file size {len(data)} bytes does not match "
            f"width*height*2 = {expected} bytes (width={width}, height={height})"
        )
    arr = np.frombuffer(data, dtype="<u2").reshape(height, width)
    return arr.copy()


def load_bmp(path: str, allow_color_conversion: bool = False) -> np.ndarray:
    img = Image.open(path)
    mode = img.mode
    if mode in GRAYSCALE_MODES:
        return np.array(img)
    if not allow_color_conversion:
        raise ValueError(
            f"'{Path(path).name}': BMP mode '{mode}' is not grayscale. "
            "Enable color conversion explicitly if you want lossy luminance conversion."
        )
    return np.array(img.convert("L"))


EXT_LOADERS = {
    ".raw": lambda path, width, height, **kw: load_raw(path, width, height),
    ".bmp": lambda path, width, height, **kw: load_bmp(path, **kw),
}


def default_display_range(raw: np.ndarray) -> tuple[float, float]:
    """1st/99th percentile of this array, used only to pick a one-time default
    display range (see to_display_uint8). Falls back to min/max if the percentile
    range is degenerate (e.g. a flat image)."""
    arr = raw.astype(np.float64)
    lo, hi = np.percentile(arr, [1, 99])
    if hi <= lo:
        lo, hi = float(arr.min()), float(arr.max())
    return lo, hi


def to_display_uint8(raw: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Stretch raw -> uint8 for imshow using an explicit (lo, hi) range. The SAME
    (lo, hi) must be passed for every image in a folder so that a given raw pixel
    value always maps to the same displayed gray level across images (otherwise
    each image would get its own auto-stretch and look inconsistently contrasted).
    Callers get a sensible one-time default from default_display_range()."""
    arr = raw.astype(np.float64)
    if hi <= lo:
        return np.zeros(arr.shape, dtype=np.uint8)
    stretched = np.clip((arr - lo) / (hi - lo), 0, 1) * 255
    return stretched.astype(np.uint8)


def load_image(
    path: str,
    ext: str,
    width: int | None = None,
    height: int | None = None,
    allow_color_conversion: bool = False,
    display_range: tuple[float, float] | None = None,
) -> LoadedImage:
    loader = EXT_LOADERS.get(ext.lower())
    if loader is None:
        raise ValueError(f"Unsupported extension '{ext}'")
    raw = loader(path, width, height, allow_color_conversion=allow_color_conversion)
    lo, hi = display_range if display_range is not None else default_display_range(raw)
    display = to_display_uint8(raw, lo, hi)
    h, w = raw.shape[:2]
    return LoadedImage(
        raw=raw,
        display=display,
        path=path,
        width=w,
        height=h,
        source_dtype=raw.dtype,
    )
