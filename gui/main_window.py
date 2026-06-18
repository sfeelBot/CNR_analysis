"""Top-level window: a tab per opened folder. See GUI.md section 0.

Each tab hosts an independent AnalysisPage (its own file list, canvas, profile
panel, results, batch button -- nothing is shared between tabs). The last tab
is a permanent "+" placeholder; selecting it opens StartupDialog to pick a new
folder/extension/dimensions and inserts a real AnalysisPage tab before it.
"""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtWidgets import QMainWindow, QWidget, QTabWidget, QTabBar, QDialog

from gui.analysis_page import AnalysisPage
from gui.startup_dialog import StartupDialog

PLUS_TAB_LABEL = "+"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CNR Measurement Tool")
        self.resize(1300, 850)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.on_tab_close_requested)
        self.setCentralWidget(self.tabs)

        self._previous_index = -1
        self._plus_widget = QWidget()
        self._add_plus_tab()

        # Connected after the plus tab exists so the initial addTab doesn't fire
        # the handler before self._plus_widget is set.
        self.tabs.currentChanged.connect(self.on_current_tab_changed)

    # ---------- public API ----------

    def add_analysis_tab(self, folder: str, ext: str, width: int | None, height: int | None) -> int:
        page = AnalysisPage(folder, ext, width, height)
        title = Path(folder).name or folder
        index = self.tabs.insertTab(self._plus_tab_index(), page, title)
        self.tabs.setCurrentIndex(index)
        return index

    # ---------- "+" tab handling ----------

    def _add_plus_tab(self) -> None:
        index = self.tabs.addTab(self._plus_widget, PLUS_TAB_LABEL)
        tab_bar = self.tabs.tabBar()
        tab_bar.setTabButton(index, QTabBar.RightSide, None)
        tab_bar.setTabButton(index, QTabBar.LeftSide, None)

    def _plus_tab_index(self) -> int:
        return self.tabs.indexOf(self._plus_widget)

    def _is_plus_tab(self, index: int) -> bool:
        return self.tabs.widget(index) is self._plus_widget

    def on_current_tab_changed(self, index: int) -> None:
        if index == -1:
            return
        if self._is_plus_tab(index):
            self._handle_plus_clicked()
            return
        self._previous_index = index

    def _handle_plus_clicked(self) -> None:
        dialog = StartupDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            values = dialog.get_values()
            self.add_analysis_tab(values["folder"], values["ext"], values["width"], values["height"])
        elif self._previous_index >= 0:
            self.tabs.setCurrentIndex(self._previous_index)

    def on_tab_close_requested(self, index: int) -> None:
        if self._is_plus_tab(index):
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
