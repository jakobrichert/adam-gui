"""Matplotlib chart embedded in Qt that follows the active theme.

Usage::

    chart = ChartWidget()
    chart.set_renderer(lambda c: c.line(x, y, "Trait 1", 0))

The renderer is re-run on every theme change, so it must draw everything from
scratch using ``chart.ax`` / ``chart.palette`` and the helpers below.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import matplotlib

matplotlib.use("QtAgg")

import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from adam_gui.qt_compat import (  # noqa: E402
    QApplication, QFileDialog, QMenu, QSizePolicy, Qt, QVBoxLayout, QWidget,
)
from adam_gui.themes import colormaps, palette, theme  # noqa: E402

FONT_SIZE = 9.5
_FONT_CANDIDATES = ("Inter", "Helvetica Neue", "Segoe UI", "Ubuntu", "Noto Sans",
                    "Arial", "DejaVu Sans")
_font_family: str | None = None


def ui_font_family() -> str:
    global _font_family
    if _font_family is None:
        available = {f.name for f in font_manager.fontManager.ttflist}
        _font_family = next((f for f in _FONT_CANDIDATES if f in available), "DejaVu Sans")
    return _font_family


@dataclass
class _Series:
    x: np.ndarray
    y: np.ndarray
    label: str
    color: str
    fmt: str
    end_label: bool


class _Canvas(FigureCanvasQTAgg):
    def __init__(self, figure):
        super().__init__(figure)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(160)


class ChartWidget(QWidget):
    """Themed matplotlib canvas with hover read-outs and save/copy actions."""

    def __init__(self, parent: QWidget | None = None, hover: bool = True, min_height: int = 220):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.figure = Figure(dpi=100)
        self.canvas = _Canvas(self.figure)
        self.canvas.setMinimumHeight(min_height)
        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._context_menu)
        lay.addWidget(self.canvas)

        self.ax = self.figure.add_subplot(111)
        self._renderer: Callable[["ChartWidget"], None] | None = None
        self._series: list[_Series] = []
        self._legend = True
        self._hover_enabled = hover
        self._hover_formatter: Callable[[float, float], str | None] | None = None
        self._hover_artists: list = []
        self._hover_key = None
        self._message: str | None = None
        self.save_name = "chart"

        self.canvas.mpl_connect("motion_notify_event", self._on_move)
        self.canvas.mpl_connect("figure_leave_event", lambda _e: self._clear_hover(redraw=True))
        self.canvas.mpl_connect("resize_event", lambda _e: self._layout())
        theme().changed.connect(self.redraw)

    # ------------------------------------------------------------ public API
    @property
    def palette(self):
        return palette()

    def set_renderer(self, fn: Callable[["ChartWidget"], None] | None, legend: bool = True):
        self._renderer = fn
        self._legend = legend
        self._message = None
        self.redraw()

    def show_message(self, text: str):
        self._renderer = None
        self._message = text
        self.redraw()

    def set_hover_formatter(self, fn: Callable[[float, float], str | None] | None):
        """Custom hover text for non-line charts: fn(xdata, ydata) -> text | None."""
        self._hover_formatter = fn

    def redraw(self, *_):
        p = palette()
        self._series = []
        self._hover_artists = []
        self._hover_key = None
        self.figure.clf()
        self.figure.set_facecolor(p.surface)
        self.ax = self.figure.add_subplot(111)
        self._style_axes(self.ax)
        if self._renderer is not None:
            self._renderer(self)
            self._finish()
        elif self._message:
            self.ax.set_axis_off()
            self.ax.text(0.5, 0.5, self._message, ha="center", va="center",
                         color=p.text_muted, fontsize=FONT_SIZE + 1,
                         transform=self.ax.transAxes, family=ui_font_family())
        else:
            self.ax.set_axis_off()
        self._layout()
        self.canvas.draw_idle()

    def style_axes(self, ax):
        """Apply theme styling to an extra axes (e.g. a colorbar)."""
        self._style_axes(ax)

    def line(self, x: Sequence[float], y: Sequence[float], label: str, slot: int | None = None,
             color: str | None = None, style: str = "-", width: float = 1.7,
             fmt: str = "{:.3f}", end_label: bool = True, alpha: float = 1.0, zorder: int = 3):
        """Draw a series; it takes part in hover read-outs and end labels."""
        color = color or colormaps.categorical(palette(), slot or 0)
        xs = np.asarray(x, dtype=float)
        ys = np.asarray(y, dtype=float)
        self.ax.plot(xs, ys, style, color=color, linewidth=width, label=label,
                     solid_capstyle="round", alpha=alpha, zorder=zorder)
        self._series.append(_Series(xs, ys, label, color, fmt, end_label and style == "-"))
        return color

    def save(self, path: str):
        self.figure.savefig(path, facecolor=self.figure.get_facecolor(), dpi=200,
                            bbox_inches="tight")

    def copy_to_clipboard(self):
        QApplication.clipboard().setImage(self.canvas.grab().toImage())

    def save_dialog(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save chart", f"{self.save_name}.png",
            "PNG image (*.png);;SVG vector (*.svg);;PDF document (*.pdf)")
        if path:
            self.save(path)
        return path

    # ------------------------------------------------------------ styling
    def _style_axes(self, ax):
        p = palette()
        family = ui_font_family()
        ax.set_facecolor(p.surface)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(p.border_strong)
            ax.spines[side].set_linewidth(0.8)
        ax.tick_params(colors=p.border_strong, labelcolor=p.text_muted,
                       labelsize=FONT_SIZE - 0.5, length=3, width=0.8)
        for lbl in ax.get_xticklabels() + ax.get_yticklabels():
            lbl.set_family(family)
        ax.xaxis.label.set_color(p.text_muted)
        ax.yaxis.label.set_color(p.text_muted)
        ax.xaxis.label.set_size(FONT_SIZE)
        ax.yaxis.label.set_size(FONT_SIZE)
        ax.xaxis.label.set_family(family)
        ax.yaxis.label.set_family(family)
        ax.grid(True, axis="y", color=p.grid, linewidth=0.8)
        ax.set_axisbelow(True)

    def _finish(self):
        p = palette()
        ax = self.ax
        family = ui_font_family()
        for lbl in ax.get_xticklabels() + ax.get_yticklabels():
            lbl.set_family(family)
        labelled = [s for s in self._series if s.label and not s.label.startswith("_")]
        handles, labels = ax.get_legend_handles_labels()
        if self._legend and len(labels) >= 2:
            leg = ax.legend(frameon=False, fontsize=FONT_SIZE - 0.5, loc="upper left",
                            bbox_to_anchor=(0, 1.02, 1, 0.1), ncols=min(4, len(labels)),
                            mode=None, borderaxespad=0, handlelength=1.6,
                            columnspacing=1.4, prop={"family": family, "size": FONT_SIZE - 0.5})
            for text in leg.get_texts():
                text.set_color(p.text_muted)
        end = [s for s in labelled if s.end_label and len(s.x)]
        if 1 <= len(end) <= 4 and len(labelled) >= 1:
            self._end_labels(end)

    def _end_labels(self, series: list[_Series]):
        p = palette()
        ax = self.ax
        ax.margins(x=0.02)
        items = []
        for s in series:
            finite = np.isfinite(s.y)
            if not finite.any():
                continue
            i = np.flatnonzero(finite)[-1]
            items.append((s, s.x[i], s.y[i]))
            ax.plot([s.x[i]], [s.y[i]], "o", color=s.color, markersize=4.5,
                    markeredgecolor=p.surface, markeredgewidth=1.2, zorder=5)
        if not items:
            return
        # Spread labels vertically so they never collide (in axes fraction).
        y0, y1 = ax.get_ylim()
        span = (y1 - y0) or 1.0
        fracs = sorted(((y - y0) / span, k) for k, (_s, _x, y) in enumerate(items))
        min_gap = 0.075
        placed = []
        for frac, k in fracs:
            if placed and frac - placed[-1][0] < min_gap:
                frac = placed[-1][0] + min_gap
            placed.append((frac, k))
        overflow = placed[-1][0] - 0.98 if placed else 0
        if overflow > 0:
            placed = [(f - overflow, k) for f, k in placed]
        # Labels that had to move far from their line would read as axis ticks;
        # fall back to the legend and hover read-out instead.
        original = dict((k, f) for f, k in fracs)
        if any(abs(f - original[k]) > 0.09 for f, k in placed):
            return
        for frac, k in placed:
            s, x, y = items[k]
            ax.annotate(
                s.fmt.format(y), xy=(x, y), xycoords="data",
                xytext=(1.012, frac), textcoords=("axes fraction"),
                va="center", ha="left", fontsize=FONT_SIZE - 0.5, color=p.text_muted,
                family=ui_font_family(), annotation_clip=False,
            )

    def _layout(self):
        try:
            has_end = any(t for t in self.ax.texts if getattr(t, "xyann", None) is not None)
            self.figure.tight_layout(pad=0.6)
            if has_end:
                right = self.figure.subplotpars.right
                self.figure.subplots_adjust(right=min(right, 0.9))
            if self.ax.get_legend() is not None:
                top = self.figure.subplotpars.top
                self.figure.subplots_adjust(top=min(top, 0.88))
        except Exception:  # tight_layout can fail on tiny canvases
            pass

    # ------------------------------------------------------------ hover
    def _clear_hover(self, redraw: bool = False):
        for art in self._hover_artists:
            try:
                art.remove()
            except (ValueError, AttributeError):
                pass
        had = bool(self._hover_artists)
        self._hover_artists = []
        self._hover_key = None
        if redraw and had:
            self.canvas.draw_idle()

    def _on_move(self, event):
        if not self._hover_enabled or event.inaxes is not self.ax:
            self._clear_hover(redraw=True)
            return
        p = palette()
        if self._series:
            xs = self._series[0].x
            if not len(xs):
                return
            idx = int(np.nanargmin(np.abs(xs - event.xdata)))
            key = ("line", idx)
            if key == self._hover_key:
                return
            self._clear_hover()
            self._hover_key = key
            x = xs[idx]
            vline = self.ax.axvline(x, color=p.text_faint, linewidth=0.8, zorder=1)
            self._hover_artists.append(vline)
            lines = [f"Generation {x:g}"]
            for s in self._series:
                j = int(np.argmin(np.abs(s.x - x))) if len(s.x) else -1
                if j < 0 or not np.isfinite(s.y[j]):
                    continue
                dot = self.ax.plot([s.x[j]], [s.y[j]], "o", color=s.color, markersize=6,
                                   markeredgecolor=p.surface, markeredgewidth=1.5, zorder=6)[0]
                self._hover_artists.append(dot)
                if s.label and not s.label.startswith("_"):
                    lines.append(f"{s.label}:  {s.fmt.format(s.y[j])}")
            self._tooltip("\n".join(lines[:12]), x, event.ydata)
        elif self._hover_formatter is not None:
            text = self._hover_formatter(event.xdata, event.ydata)
            key = ("custom", text)
            if key == self._hover_key:
                return
            self._clear_hover()
            self._hover_key = key
            if text:
                self._tooltip(text, event.xdata, event.ydata)
        self.canvas.draw_idle()

    def _tooltip(self, text: str, x: float, y: float):
        p = palette()
        x0, x1 = self.ax.get_xlim()
        right_half = (x - x0) / ((x1 - x0) or 1) > 0.6
        ann = self.ax.annotate(
            text, xy=(x, y), xycoords="data",
            xytext=(-14 if right_half else 14, 0), textcoords="offset points",
            ha="right" if right_half else "left", va="center",
            fontsize=FONT_SIZE - 0.5, color=p.text, family=ui_font_family(),
            bbox=dict(boxstyle="round,pad=0.5,rounding_size=0.4", fc=p.surface_3,
                      ec=p.border_strong, lw=0.8),
            zorder=10, annotation_clip=False,
        )
        self._hover_artists.append(ann)

    # ------------------------------------------------------------ context menu
    def _context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Save image…", self.save_dialog)
        menu.addAction("Copy image", self.copy_to_clipboard)
        menu.exec(self.canvas.mapToGlobal(pos))
