"""Matplotlib canvas embedded in Qt for 2D charts."""

import matplotlib
matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from adam_gui.qt_compat import QWidget, QVBoxLayout


class ChartWidget(QWidget):
    """Matplotlib chart embedded in a Qt widget."""

    def __init__(self, parent=None, figsize=(8, 4), dpi=100):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(figsize=figsize, dpi=dpi)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.ax = self.figure.add_subplot(111)

    def apply_theme(self, colors: dict):
        """Apply theme colors to the chart."""
        self.figure.set_facecolor(colors["bg"])
        self.ax.set_facecolor(colors["bg"])
        self.ax.tick_params(colors=colors["fg"])
        self.ax.xaxis.label.set_color(colors["fg"])
        self.ax.yaxis.label.set_color(colors["fg"])
        self.ax.title.set_color(colors["fg"])
        for spine in self.ax.spines.values():
            spine.set_color(colors["grid"])
        self.ax.grid(True, alpha=0.3, color=colors["grid"])

    def clear(self):
        self.ax.clear()

    def refresh(self):
        self.canvas.draw()
