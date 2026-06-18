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


def to_display_uint8(raw: np.ndarray) -> np.ndarray:
    arr = raw.astype(np.float64)
    lo, hi = np.percentile(arr, [1, 99])
    if hi <= lo:
        lo, hi = float(arr.min()), float(arr.max())
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
) -> LoadedImage:
    loader = EXT_LOADERS.get(ext.lower())
    if loader is None:
        raise ValueError(f"Unsupported extension '{ext}'")
    raw = loader(path, width, height, allow_color_conversion=allow_color_conversion)
    display = to_display_uint8(raw)
    h, w = raw.shape[:2]
    return LoadedImage(
        raw=raw,
        display=display,
        path=path,
        width=w,
        height=h,
        source_dtype=raw.dtype,
    )
