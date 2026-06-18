"""Interactive image canvas: line profile + rectangle ROI drawing with live updates.

See GUI.md section 3 for the full state-machine description (modes, drag targets,
blitting strategy, and why RectangleSelector isn't used).
"""
from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from PyQt5.QtCore import pyqtSignal

HIT_TOLERANCE_PX = 8
ZOOM_SCALE_PER_STEP = 1.2


class ImageCanvas(FigureCanvasQTAgg):
    line_changed = pyqtSignal(tuple, tuple)
    rect_changed = pyqtSignal(tuple)

    def __init__(self, parent=None):
        self.fig = Figure()
        super().__init__(self.fig)
        if parent is not None:
            self.setParent(parent)

        self.ax = self.fig.add_subplot(111)
        self.ax.set_axis_off()
        self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        self.im = None
        self._line = None
        self._rect = None
        self.mode = "navigate"
        self.drag_target = None
        self._move_anchor = None
        self._pan_anchor_px = None
        self._bg = None

        self.line_artist = Line2D([], [], color="red", marker="o", markersize=4, linewidth=1.5)
        self.ax.add_line(self.line_artist)
        self.rect_artist = Rectangle((0, 0), 0, 0, fill=False, edgecolor="yellow", linewidth=1.5)
        self.ax.add_patch(self.rect_artist)
        self.line_artist.set_visible(False)
        self.rect_artist.set_visible(False)

        self.mpl_connect("button_press_event", self.on_press)
        self.mpl_connect("motion_notify_event", self.on_motion)
        self.mpl_connect("button_release_event", self.on_release)
        self.mpl_connect("scroll_event", self.on_scroll)

    # ---------- public API ----------

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.drag_target = None

    def set_image(self, display_array: np.ndarray) -> None:
        if self.im is None:
            self.im = self.ax.imshow(display_array, cmap="gray", interpolation="nearest")
            h, w = display_array.shape[:2]
            self.ax.set_xlim(-0.5, w - 0.5)
            self.ax.set_ylim(h - 0.5, -0.5)
        else:
            self.im.set_data(display_array)
        self._refresh_background_and_render()

    def set_line(self, p0: tuple, p1: tuple) -> None:
        self._line = (tuple(p0), tuple(p1))
        self._update_line_artist()
        self._blit_dynamic()
        self.line_changed.emit(*self._line)

    def set_rect(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self._rect = (x0, y0, x1, y1)
        self._update_rect_artist()
        self._blit_dynamic()
        self.rect_changed.emit(self._rect)

    def get_line(self):
        return self._line

    def get_rect(self):
        return self._rect

    # ---------- artist / rendering helpers ----------

    def _update_line_artist(self) -> None:
        if self._line is None:
            self.line_artist.set_visible(False)
            return
        (x0, y0), (x1, y1) = self._line
        self.line_artist.set_data([x0, x1], [y0, y1])
        self.line_artist.set_visible(True)

    def _update_rect_artist(self) -> None:
        if self._rect is None:
            self.rect_artist.set_visible(False)
            return
        x0, y0, x1, y1 = self._rect
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        self.rect_artist.set_bounds(xa, ya, xb - xa, yb - ya)
        self.rect_artist.set_visible(True)

    def _refresh_background_and_render(self) -> None:
        """Full redraw with dynamic artists hidden, capture clean background for blitting,
        then blit the dynamic artists back on top. Must be used whenever the static image
        content changes (file switch) or before a new drag starts."""
        was_line = self.line_artist.get_visible()
        was_rect = self.rect_artist.get_visible()
        self.line_artist.set_visible(False)
        self.rect_artist.set_visible(False)
        self.draw()
        self._bg = self.copy_from_bbox(self.ax.bbox)
        self.line_artist.set_visible(was_line)
        self.rect_artist.set_visible(was_rect)
        self._blit_dynamic()

    def _blit_dynamic(self) -> None:
        if self._bg is None:
            self.draw()
            return
        self.restore_region(self._bg)
        if self.line_artist.get_visible():
            self.ax.draw_artist(self.line_artist)
        if self.rect_artist.get_visible():
            self.ax.draw_artist(self.rect_artist)
        self.blit(self.ax.bbox)

    # ---------- hit testing ----------

    def _hit_endpoint(self, event):
        if self._line is None:
            return None
        (x0, y0), (x1, y1) = self._line
        for name, (px, py) in (("p0", (x0, y0)), ("p1", (x1, y1))):
            dx, dy = self.ax.transData.transform((px, py))
            if np.hypot(dx - event.x, dy - event.y) <= HIT_TOLERANCE_PX:
                return name
        return None

    def _hit_rect_corner(self, event):
        if self._rect is None:
            return None
        x0, y0, x1, y1 = self._rect
        corners = {"c00": (x0, y0), "c01": (x0, y1), "c10": (x1, y0), "c11": (x1, y1)}
        for name, (px, py) in corners.items():
            dx, dy = self.ax.transData.transform((px, py))
            if np.hypot(dx - event.x, dy - event.y) <= HIT_TOLERANCE_PX:
                return name
        return None

    def _point_in_rect(self, x, y) -> bool:
        if self._rect is None:
            return False
        x0, y0, x1, y1 = self._rect
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        return xa <= x <= xb and ya <= y <= yb

    def _clip_to_image(self, x, y):
        if self.im is None:
            return x, y
        h, w = self.im.get_array().shape[:2]
        return float(np.clip(x, 0, w - 1)), float(np.clip(y, 0, h - 1))

    # ---------- mouse events ----------

    def on_press(self, event) -> None:
        if event.inaxes is not self.ax or event.xdata is None:
            return

        if event.button == 3:
            # Right-click drag pans the view, independent of the current mode
            # (line/rect drawing always uses left-click, so this never conflicts).
            self.drag_target = "pan"
            self._pan_anchor_px = (event.x, event.y)
            return

        x, y = event.xdata, event.ydata

        if self.mode == "line":
            hit = self._hit_endpoint(event)
            if hit is not None:
                self.drag_target = hit
            else:
                self._line = ((x, y), (x, y))
                self.drag_target = "p1"
                self._update_line_artist()
            self._refresh_background_and_render()

        elif self.mode == "rect":
            hit = self._hit_rect_corner(event)
            if hit is not None:
                self.drag_target = hit
            elif self._point_in_rect(x, y):
                self.drag_target = "move"
                self._move_anchor = (x, y)
            else:
                self._rect = (x, y, x, y)
                self.drag_target = "c11"
                self._update_rect_artist()
            self._refresh_background_and_render()

    def on_motion(self, event) -> None:
        if self.drag_target is None or event.inaxes is not self.ax or event.xdata is None:
            return

        if self.drag_target == "pan":
            self._pan_by_pixels(event.x, event.y)
            return

        x, y = self._clip_to_image(event.xdata, event.ydata)

        if self.mode == "line" and self._line is not None:
            p0, p1 = self._line
            if self.drag_target == "p0":
                p0 = (x, y)
            elif self.drag_target == "p1":
                p1 = (x, y)
            self._line = (p0, p1)
            self._update_line_artist()
            self._blit_dynamic()
            self.line_changed.emit(p0, p1)

        elif self.mode == "rect" and self._rect is not None:
            x0, y0, x1, y1 = self._rect
            if self.drag_target == "move":
                ax, ay = self._move_anchor
                dx, dy = x - ax, y - ay
                x0, x1, y0, y1 = x0 + dx, x1 + dx, y0 + dy, y1 + dy
                self._move_anchor = (x, y)
            elif self.drag_target == "c00":
                x0, y0 = x, y
            elif self.drag_target == "c01":
                x0, y1 = x, y
            elif self.drag_target == "c10":
                x1, y0 = x, y
            elif self.drag_target == "c11":
                x1, y1 = x, y
            self._rect = (x0, y0, x1, y1)
            self._update_rect_artist()
            self._blit_dynamic()
            self.rect_changed.emit(self._rect)

    def on_release(self, event) -> None:
        self.drag_target = None
        self._move_anchor = None
        self._pan_anchor_px = None
        self._refresh_background_and_render()

    def on_scroll(self, event) -> None:
        if event.inaxes is not self.ax or event.xdata is None or self.im is None:
            return
        scale = 1 / ZOOM_SCALE_PER_STEP if event.button == "up" else ZOOM_SCALE_PER_STEP
        x, y = event.xdata, event.ydata
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        new_xlim = (x - (x - xlim[0]) * scale, x + (xlim[1] - x) * scale)
        new_ylim = (y - (y - ylim[0]) * scale, y + (ylim[1] - y) * scale)
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        self._refresh_background_and_render()

    def _pan_by_pixels(self, event_x: float, event_y: float) -> None:
        """Translate the view by the pixel delta since the last pan step, converted to
        data units via the (currently unchanged-by-this-step) transData. See GUI.md
        section 3 for why the anchor is reset to pixel coords every step rather than
        kept in data coords (data coords would drift as xlim/ylim change mid-drag)."""
        inv = self.ax.transData.inverted()
        x0_data, y0_data = inv.transform(self._pan_anchor_px)
        x1_data, y1_data = inv.transform((event_x, event_y))
        dx, dy = x1_data - x0_data, y1_data - y0_data

        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
        self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
        self._pan_anchor_px = (event_x, event_y)
        self._refresh_background_and_render()
