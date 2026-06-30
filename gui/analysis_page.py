"""Single-folder analysis page (one per tab). See GUI.md sections 1, 5, 6, 7 for
layout and wiring; section 0 for how MainWindow embeds many of these in tabs."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget,
    QSplitter,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QListWidget,
    QPushButton,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QLabel,
    QButtonGroup,
    QGroupBox,
    QMessageBox,
    QProgressDialog,
)

import batch
from image_io import load_image, to_display_uint8
from measurements import sample_line_profile, find_signal_and_background, compute_noise, compute_cnr
from gui.image_canvas import ImageCanvas
from gui.profile_panel import ProfilePanel
from gui.results_dialog import ResultsDialog


class AnalysisPage(QWidget):
    def __init__(self, folder: str, ext: str, width: int | None, height: int | None, parent=None):
        super().__init__(parent)

        self.folder = folder
        self.ext = ext
        self.current_loaded = None
        self.files: list[str] = []
        self._dims_reload_pending = False
        self.display_range: tuple[float, float] | None = None

        self._build_ui()
        self._wire_signals()

        self.ext_combo.setCurrentText(ext)
        if width is not None:
            self.width_spin.setValue(width)
        if height is not None:
            self.height_spin.setValue(height)

        self._rescan_folder()

    # ---------- UI construction ----------

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Horizontal)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(QLabel("Extension"))
        self.ext_combo = QComboBox()
        self.ext_combo.addItems([".raw", ".bmp"])
        left_layout.addWidget(self.ext_combo)

        dims_form = QFormLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 100000)
        self.width_spin.setValue(512)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 100000)
        self.height_spin.setValue(512)
        dims_form.addRow("Width", self.width_spin)
        dims_form.addRow("Height", self.height_spin)
        left_layout.addLayout(dims_form)

        display_box = QGroupBox("Display Range (contrast)")
        display_form = QFormLayout(display_box)
        self.display_min_spin = QDoubleSpinBox()
        self.display_max_spin = QDoubleSpinBox()
        for s in (self.display_min_spin, self.display_max_spin):
            s.setRange(0, 1_000_000)
            s.setDecimals(1)
        display_form.addRow("Min", self.display_min_spin)
        display_form.addRow("Max", self.display_max_spin)
        left_layout.addWidget(display_box)

        self.file_list = QListWidget()
        left_layout.addWidget(self.file_list, 1)

        nav_row = QHBoxLayout()
        self.prev_btn = QPushButton("Prev")
        self.next_btn = QPushButton("Next")
        nav_row.addWidget(self.prev_btn)
        nav_row.addWidget(self.next_btn)
        left_layout.addLayout(nav_row)

        splitter.addWidget(left)

        center = QWidget()
        center_layout = QVBoxLayout(center)

        mode_row = QHBoxLayout()
        self.mode_navigate_btn = QPushButton("Navigate")
        self.mode_line_btn = QPushButton("Draw Line")
        self.mode_rect_btn = QPushButton("Draw Rect")
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for b in (self.mode_navigate_btn, self.mode_line_btn, self.mode_rect_btn):
            b.setCheckable(True)
            self.mode_group.addButton(b)
            mode_row.addWidget(b)
        self.mode_navigate_btn.setChecked(True)
        center_layout.addLayout(mode_row)

        self.canvas = ImageCanvas()
        center_layout.addWidget(self.canvas, 1)

        splitter.addWidget(center)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.profile_panel = ProfilePanel()
        right_layout.addWidget(self.profile_panel, 1)

        params_box = QGroupBox("Parameters")
        params_form = QFormLayout(params_box)
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 10000)
        self.margin_spin.setValue(3)
        params_form.addRow("Exclusion margin (a)", self.margin_spin)
        right_layout.addWidget(params_box)

        coords_box = QGroupBox("Line / Rect coordinates")
        coords_form = QFormLayout(coords_box)
        self.line_spins = [QDoubleSpinBox() for _ in range(4)]
        self.rect_spins = [QDoubleSpinBox() for _ in range(4)]
        for s in self.line_spins + self.rect_spins:
            s.setRange(-100000, 100000)
            s.setDecimals(1)
        for label, spin in zip(
            ["Line x0", "Line y0", "Line x1", "Line y1"], self.line_spins
        ):
            coords_form.addRow(label, spin)
        for label, spin in zip(
            ["Rect x0", "Rect y0", "Rect x1", "Rect y1"], self.rect_spins
        ):
            coords_form.addRow(label, spin)
        right_layout.addWidget(coords_box)

        results_box = QGroupBox("Results")
        results_form = QFormLayout(results_box)
        self.signal_label = QLabel("-")
        self.background_label = QLabel("-")
        self.background_min_label = QLabel("-")
        self.background_max_label = QLabel("-")
        self.background_std_label = QLabel("-")
        self.profile_min_label = QLabel("-")
        self.profile_max_label = QLabel("-")
        self.profile_std_label = QLabel("-")
        self.noise_label = QLabel("-")
        self.noise_min_max_label = QLabel("-")
        self.rect_min_label = QLabel("-")
        self.rect_mean_label = QLabel("-")
        self.area_label = QLabel("-")
        self.cnr_label = QLabel("-")
        results_form.addRow("Signal", self.signal_label)
        results_form.addRow("Background mean", self.background_label)
        results_form.addRow("Background min", self.background_min_label)
        results_form.addRow("Background max", self.background_max_label)
        results_form.addRow("Background std", self.background_std_label)
        results_form.addRow("Profile min", self.profile_min_label)
        results_form.addRow("Profile max", self.profile_max_label)
        results_form.addRow("Profile std", self.profile_std_label)
        results_form.addRow("Noise (std)", self.noise_label)
        results_form.addRow("Noise (max-min)", self.noise_min_max_label)
        results_form.addRow("Rect min", self.rect_min_label)
        results_form.addRow("Rect mean", self.rect_mean_label)
        results_form.addRow("Area (px)", self.area_label)
        results_form.addRow("CNR", self.cnr_label)
        right_layout.addWidget(results_box)

        self.run_batch_btn = QPushButton("Run Batch")
        self.run_batch_btn.setEnabled(False)
        right_layout.addWidget(self.run_batch_btn)

        splitter.addWidget(right)
        splitter.setSizes([250, 700, 380])

    def _wire_signals(self) -> None:
        self.file_list.currentRowChanged.connect(self.on_file_selected)
        self.ext_combo.currentTextChanged.connect(self.on_extension_changed)
        self.width_spin.valueChanged.connect(self.on_raw_dims_changed)
        self.height_spin.valueChanged.connect(self.on_raw_dims_changed)
        self.margin_spin.valueChanged.connect(self.recompute_and_redraw)
        self.display_min_spin.valueChanged.connect(self.on_display_range_typed)
        self.display_max_spin.valueChanged.connect(self.on_display_range_typed)

        self.mode_navigate_btn.toggled.connect(
            lambda checked: checked and self.canvas.set_mode("navigate")
        )
        self.mode_line_btn.toggled.connect(
            lambda checked: checked and self.canvas.set_mode("line")
        )
        self.mode_rect_btn.toggled.connect(
            lambda checked: checked and self.canvas.set_mode("rect")
        )

        self.canvas.line_changed.connect(self.on_line_changed)
        self.canvas.rect_changed.connect(self.on_rect_changed)

        for s in self.line_spins:
            s.valueChanged.connect(self.on_line_coords_typed)
        for s in self.rect_spins:
            s.valueChanged.connect(self.on_rect_coords_typed)

        self.prev_btn.clicked.connect(self.on_prev)
        self.next_btn.clicked.connect(self.on_next)
        self.run_batch_btn.clicked.connect(self.on_run_batch)

    # ---------- folder / file handling ----------

    def _rescan_folder(self) -> None:
        self.files = batch.scan_folder(self.folder, self.ext)
        self.file_list.blockSignals(True)
        self.file_list.clear()
        self.file_list.addItems([Path(p).name for p in self.files])
        self.file_list.blockSignals(False)
        if self.files:
            self.file_list.setCurrentRow(0)
            self._load_current_file()
        else:
            self.current_loaded = None
            QMessageBox.warning(self, "No files", f"No '{self.ext}' files found in folder.")

    def on_extension_changed(self, ext: str) -> None:
        self.ext = ext
        is_raw = ext == ".raw"
        self.width_spin.setEnabled(is_raw)
        self.height_spin.setEnabled(is_raw)
        # Different extensions can have wildly different native value ranges
        # (e.g. 16-bit raw vs 8-bit bmp), so the frozen display range no longer
        # applies -- let the next loaded file pick a fresh default.
        self.display_range = None
        self._rescan_folder()

    def on_raw_dims_changed(self, _value) -> None:
        # width_spin and height_spin each fire valueChanged independently; coalesce
        # back-to-back changes (e.g. both set programmatically, or fast typing) into
        # a single reload on the next event-loop tick instead of reloading on every
        # partial (width, old_height) / (old_width, height) combination.
        if self.ext != ".raw" or self._dims_reload_pending:
            return
        self._dims_reload_pending = True
        QTimer.singleShot(0, self._apply_raw_dims_reload)

    def _apply_raw_dims_reload(self) -> None:
        self._dims_reload_pending = False
        if self.ext == ".raw":
            self._load_current_file()

    def on_prev(self) -> None:
        row = self.file_list.currentRow()
        if row > 0:
            self.file_list.setCurrentRow(row - 1)

    def on_next(self) -> None:
        row = self.file_list.currentRow()
        if row < self.file_list.count() - 1:
            self.file_list.setCurrentRow(row + 1)

    def on_file_selected(self, row: int) -> None:
        if row < 0 or row >= len(self.files):
            return
        self._load_current_file()

    def _load_current_file(self) -> None:
        row = self.file_list.currentRow()
        if row < 0 or row >= len(self.files):
            return
        path = self.files[row]
        try:
            loaded = load_image(
                path,
                self.ext,
                width=self.width_spin.value() if self.ext == ".raw" else None,
                height=self.height_spin.value() if self.ext == ".raw" else None,
                display_range=self.display_range,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Failed to load image", str(exc))
            return
        self.current_loaded = loaded
        if self.display_range is None:
            # First file of this folder/extension: freeze a default range so every
            # subsequent file (and this one, if reloaded) maps the same raw pixel
            # value to the same displayed gray level instead of each image getting
            # its own independent contrast stretch. Default is the fixed (0, 255)
            # range rather than a per-image percentile; users can override via the
            # Display Range spinboxes.
            self.display_range = (0.0, 255.0)
            self._set_display_range_spins(self.display_range)
        self.canvas.set_image(loaded.display)
        self.recompute_and_redraw()

    def _set_display_range_spins(self, range_: tuple[float, float]) -> None:
        for s, v in zip((self.display_min_spin, self.display_max_spin), range_):
            s.blockSignals(True)
            s.setValue(v)
            s.blockSignals(False)

    def on_display_range_typed(self, _value=None) -> None:
        lo, hi = self.display_min_spin.value(), self.display_max_spin.value()
        self.display_range = (lo, hi)
        if self.current_loaded is not None:
            self.current_loaded.display = to_display_uint8(self.current_loaded.raw, lo, hi)
            self.canvas.set_image(self.current_loaded.display)

    # ---------- line / rect interaction ----------

    def on_line_changed(self, p0: tuple, p1: tuple) -> None:
        self._set_line_spins(p0, p1)
        self.recompute_and_redraw()

    def on_rect_changed(self, rect: tuple) -> None:
        self._set_rect_spins(rect)
        self.recompute_and_redraw()

    def on_line_coords_typed(self, _value=None) -> None:
        p0 = (self.line_spins[0].value(), self.line_spins[1].value())
        p1 = (self.line_spins[2].value(), self.line_spins[3].value())
        self.canvas.set_line(p0, p1)  # emits line_changed -> on_line_changed -> recompute

    def on_rect_coords_typed(self, _value=None) -> None:
        rect = tuple(s.value() for s in self.rect_spins)
        self.canvas.set_rect(*rect)  # emits rect_changed -> on_rect_changed -> recompute

    def _set_line_spins(self, p0: tuple, p1: tuple) -> None:
        for s, v in zip(self.line_spins, [p0[0], p0[1], p1[0], p1[1]]):
            s.blockSignals(True)
            s.setValue(v)
            s.blockSignals(False)

    def _set_rect_spins(self, rect: tuple) -> None:
        for s, v in zip(self.rect_spins, rect):
            s.blockSignals(True)
            s.setValue(v)
            s.blockSignals(False)

    # ---------- measurement ----------

    def recompute_and_redraw(self, *_args) -> None:
        line = self.canvas.get_line()
        rect = self.canvas.get_rect()
        self.run_batch_btn.setEnabled(
            line is not None and rect is not None and self.current_loaded is not None
        )

        if self.current_loaded is None:
            return
        image = self.current_loaded.raw
        a = self.margin_spin.value()

        signal = background_mean = noise = noise_min_max = rect_min = rect_mean = cnr = float("nan")
        background_min = background_max = background_std = float("nan")
        profile_min = profile_max = profile_std = float("nan")
        area_px = None

        if line is not None:
            profile = sample_line_profile(image, *line)
            sb = find_signal_and_background(profile, a)
            signal = sb["signal"]
            background_mean = sb["background_mean"]
            background_min = sb["background_min"]
            background_max = sb["background_max"]
            background_std = sb["background_std"]
            profile_min = sb["profile_min"]
            profile_max = sb["profile_max"]
            profile_std = sb["profile_std"]
            self.profile_panel.update_profile(
                profile, sb["idx_min"], sb["exclusion_lo"], sb["exclusion_hi"]
            )

        if rect is not None:
            noise_info = compute_noise(image, rect)
            noise = noise_info["noise"]
            noise_min_max = noise_info["noise_min_max"]
            rect_min = noise_info["rect_min"]
            rect_mean = noise_info["rect_mean"]
            area_px = noise_info["area_px"]

        if line is not None and rect is not None:
            cnr = compute_cnr(signal, background_mean, noise)

        self.signal_label.setText("-" if line is None else f"{signal:.4f}")
        self.background_label.setText("-" if line is None else f"{background_mean:.4f}")
        self.background_min_label.setText("-" if line is None else f"{background_min:.4f}")
        self.background_max_label.setText("-" if line is None else f"{background_max:.4f}")
        self.background_std_label.setText("-" if line is None else f"{background_std:.4f}")
        self.profile_min_label.setText("-" if line is None else f"{profile_min:.4f}")
        self.profile_max_label.setText("-" if line is None else f"{profile_max:.4f}")
        self.profile_std_label.setText("-" if line is None else f"{profile_std:.4f}")
        self.noise_label.setText("-" if rect is None or np.isnan(noise) else f"{noise:.4f}")
        self.noise_min_max_label.setText(
            "-" if rect is None or np.isnan(noise_min_max) else f"{noise_min_max:.4f}"
        )
        self.rect_min_label.setText("-" if rect is None or np.isnan(rect_min) else f"{rect_min:.4f}")
        self.rect_mean_label.setText("-" if rect is None or np.isnan(rect_mean) else f"{rect_mean:.4f}")
        self.area_label.setText("-" if area_px is None else str(area_px))
        if line is None or rect is None:
            self.cnr_label.setText("-")
        elif np.isnan(cnr):
            self.cnr_label.setText("N/A (noise=0)")
        else:
            self.cnr_label.setText(f"{cnr:.4f}")

    # ---------- batch ----------

    def on_run_batch(self) -> None:
        line = self.canvas.get_line()
        rect = self.canvas.get_rect()
        if line is None or rect is None:
            return

        progress = QProgressDialog("Running batch...", "Cancel", 0, max(len(self.files), 1), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        def progress_cb(done, total):
            progress.setValue(done)

        rows = batch.run_batch(
            self.folder,
            self.ext,
            line,
            rect,
            self.margin_spin.value(),
            width=self.width_spin.value() if self.ext == ".raw" else None,
            height=self.height_spin.value() if self.ext == ".raw" else None,
            progress_cb=progress_cb,
        )
        progress.close()

        dialog = ResultsDialog(rows, parent=self)
        dialog.exec_()
