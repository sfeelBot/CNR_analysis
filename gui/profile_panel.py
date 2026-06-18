"""Live gray-value line-profile plot.

See GUI.md section 4. Unlike ImageCanvas, this panel does a lightweight full
redraw on every update rather than blitting: axis limits autoscale to the new
profile's min/max on every call, which would defeat blitting anyway. The
profile array is small (at most a few thousand points, bounded by the image
diagonal), so a full draw stays responsive.
"""
from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class ProfilePanel(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        self.fig = Figure()
        super().__init__(self.fig)
        if parent is not None:
            self.setParent(parent)

        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Position along line (px)")
        self.ax.set_ylabel("Gray value")

        (self.profile_line,) = self.ax.plot([], [], color="blue", linewidth=1)
        (self.min_marker,) = self.ax.plot([], [], "ro", markersize=6)
        self.exclusion_span = self.ax.axvspan(0, 0, color="orange", alpha=0.25)
        self.exclusion_span.set_visible(False)

        self.fig.tight_layout()
        self.draw()

    def update_profile(self, profile: np.ndarray, idx_min: int, exclusion_lo: int, exclusion_hi: int) -> None:
        n = len(profile)
        if n == 0:
            return
        xs = np.arange(n)
        self.profile_line.set_data(xs, profile)
        self.min_marker.set_data([idx_min], [profile[idx_min]])

        self.exclusion_span.remove()
        self.exclusion_span = self.ax.axvspan(
            exclusion_lo - 0.5, exclusion_hi - 0.5, color="orange", alpha=0.25
        )

        self.ax.set_xlim(0, max(n - 1, 1))
        lo, hi = float(np.min(profile)), float(np.max(profile))
        pad = (hi - lo) * 0.1 or 1.0
        self.ax.set_ylim(lo - pad, hi + pad)

        self.fig.tight_layout()
        self.draw()
