"""QTabBar that emits a signal when a tab is dragged outside the bar's bounds.

See GUI.md section 0 for how MainWindow uses this to detach a tab into its own
floating window (browser-tab-style "drag out to pop out").
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtWidgets import QTabBar


class DetachableTabBar(QTabBar):
    tab_detach_requested = pyqtSignal(int, QPoint)  # index, global position at detach

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos = None
        self._dragging_index = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self._dragging_index = self.tabAt(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        if self._dragging_index is None or self._dragging_index < 0:
            return
        if not (event.buttons() & Qt.LeftButton):
            return
        # Once the cursor leaves the tab bar's own rectangle, treat it as a
        # detach gesture -- mirrors the standard browser "drag tab out" pattern.
        if self.rect().contains(event.pos()):
            return
        index = self._dragging_index
        global_pos = self.mapToGlobal(event.pos())
        self._dragging_index = None
        self._drag_start_pos = None
        self.tab_detach_requested.emit(index, global_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging_index = None
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)
