"""Folder scanning and batch measurement across all images of a chosen extension.

See PREPROCESSING.md section 7. Both the GUI file list and the batch loop call
scan_folder() so iteration order always matches what the user sees on screen.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from image_io import load_image
from measurements import measure


def scan_folder(folder: str, ext: str) -> list[str]:
    ext = ext.lower()
    paths = [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() == ext]
    paths.sort(key=lambda p: p.name)
    return [str(p) for p in paths]


def run_batch(
    folder: str,
    ext: str,
    line: tuple,
    rect: tuple,
    exclusion_margin: int,
    width: int | None = None,
    height: int | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
) -> list[dict]:
    files = scan_folder(folder, ext)
    rows = []
    total = len(files)
    for i, path in enumerate(files):
        row = {
            "filename": Path(path).name,
            "signal": None,
            "background_mean": None,
            "noise": None,
            "noise_min_max": None,
            "rect_min": None,
            "rect_mean": None,
            "area_px": None,
            "cnr": None,
            "error": None,
        }
        try:
            loaded = load_image(path, ext, width=width, height=height)
            result = measure(loaded.raw, line, rect, exclusion_margin)
            row.update(
                signal=result["signal"],
                background_mean=result["background_mean"],
                noise=result["noise"],
                noise_min_max=result["noise_min_max"],
                rect_min=result["rect_min"],
                rect_mean=result["rect_mean"],
                area_px=result["area_px"],
                cnr=result["cnr"],
            )
            if result["noise"] == 0:
                row["error"] = "noise=0"
        except Exception as exc:  # noqa: BLE001 - one bad file must not abort the batch
            row["error"] = str(exc)
        rows.append(row)
        if progress_cb is not None:
            progress_cb(i + 1, total)
    return rows
