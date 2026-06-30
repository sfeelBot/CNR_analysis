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
            "background_min": None,
            "background_max": None,
            "background_std": None,
            "profile_min": None,
            "profile_max": None,
            "profile_std": None,
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
                background_min=result["background_min"],
                background_max=result["background_max"],
                background_std=result["background_std"],
                profile_min=result["profile_min"],
                profile_max=result["profile_max"],
                profile_std=result["profile_std"],
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
