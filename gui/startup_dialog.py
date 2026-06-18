"""Startup dialog: pick folder, extension, and (for .raw) image dimensions.

See GUI.md section 2.
"""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QPushButton,
    QFileDialog,
    QDialogButtonBox,
    QLineEdit,
    QMessageBox,
)


class StartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Image Folder")
        self.folder = ""

        layout = QVBoxLayout(self)

        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        folder_row.addWidget(QLabel("Folder:"))
        folder_row.addWidget(self.folder_edit)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        ext_row = QHBoxLayout()
        self.ext_combo = QComboBox()
        self.ext_combo.addItems([".raw", ".bmp"])
        self.ext_combo.currentTextChanged.connect(self._on_ext_changed)
        ext_row.addWidget(QLabel("Extension:"))
        ext_row.addWidget(self.ext_combo)
        layout.addLayout(ext_row)

        dims_form = QFormLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 100000)
        self.width_spin.setValue(512)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 100000)
        self.height_spin.setValue(512)
        dims_form.addRow("Width", self.width_spin)
        dims_form.addRow("Height", self.height_spin)
        layout.addLayout(dims_form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_ext_changed(self.ext_combo.currentText())

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder = folder
            self.folder_edit.setText(folder)

    def _on_ext_changed(self, ext: str) -> None:
        is_raw = ext == ".raw"
        self.width_spin.setEnabled(is_raw)
        self.height_spin.setEnabled(is_raw)

    def _on_accept(self) -> None:
        if not self.folder:
            QMessageBox.warning(self, "Missing folder", "Please select a folder.")
            return
        if self.ext_combo.currentText() == ".raw" and (
            self.width_spin.value() <= 0 or self.height_spin.value() <= 0
        ):
            QMessageBox.warning(self, "Invalid size", "Width/height must be > 0.")
            return
        self.accept()

    def get_values(self) -> dict:
        ext = self.ext_combo.currentText()
        return {
            "folder": self.folder,
            "ext": ext,
            "width": self.width_spin.value() if ext == ".raw" else None,
            "height": self.height_spin.value() if ext == ".raw" else None,
        }
