"""Batch results popup with Excel export. See GUI.md section 8."""
from __future__ import annotations

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

from export import export_to_xlsx

COLUMNS = [
    "filename",
    "signal",
    "background_mean",
    "background_min",
    "background_max",
    "background_std",
    "profile_min",
    "profile_max",
    "profile_std",
    "noise",
    "noise_min_max",
    "rect_min",
    "rect_mean",
    "area_px",
    "cnr",
    "error",
]


class ResultsDialog(QDialog):
    def __init__(self, rows: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Results")
        self.rows = rows
        self.resize(750, 450)

        layout = QVBoxLayout(self)
        self.table = QTableWidget(len(rows), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self._populate()
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        export_btn = QPushButton("Export to Excel")
        export_btn.clicked.connect(self._export)
        btn_row.addStretch()
        btn_row.addWidget(export_btn)
        layout.addLayout(btn_row)

    def _populate(self) -> None:
        for r, row in enumerate(self.rows):
            has_error = bool(row.get("error"))
            for c, key in enumerate(COLUMNS):
                value = row.get(key)
                if value is None:
                    text = ""
                elif isinstance(value, float):
                    text = "" if value != value else f"{value:.4f}"  # NaN check without numpy import
                else:
                    text = str(value)
                item = QTableWidgetItem(text)
                if has_error:
                    item.setBackground(QColor(255, 200, 200))
                self.table.setItem(r, c, item)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export to Excel", "", "Excel Files (*.xlsx)")
        if not path:
            return
        try:
            export_to_xlsx(self.rows, path)
            QMessageBox.information(self, "Export complete", f"Saved to {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))
