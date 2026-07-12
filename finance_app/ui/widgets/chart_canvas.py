from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class ChartCanvas(FigureCanvasQTAgg):
    """A matplotlib figure embedded as a Qt widget, with one axes to draw into."""

    def __init__(self, title: str = "", parent=None):
        self.figure = Figure(figsize=(4, 3), tight_layout=True)
        super().__init__(self.figure)
        self.setParent(parent)
        self.axes = self.figure.add_subplot(111)
        self._title = title
        self.show_empty("No data yet.")

    def show_empty(self, message: str) -> None:
        self.axes.clear()
        self.axes.set_title(self._title)
        self.axes.text(0.5, 0.5, message, ha="center", va="center", transform=self.axes.transAxes)
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.draw()

    def clear(self):
        self.axes.clear()
        self.axes.set_title(self._title)
        return self.axes
