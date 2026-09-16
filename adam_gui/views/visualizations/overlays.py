"""Qt widgets floating over the 3D canvas: legend, info panel, toolbar, hint."""

from __future__ import annotations

from adam_gui.qt_compat import (
    QColor, QEvent, QFont, QFrame, QGridLayout, QHBoxLayout, QLinearGradient,
    QObject, QPainter, QPen, QRectF, QSizePolicy, Qt, QToolButton, QVBoxLayout,
    QWidget, Signal,
)
from adam_gui.themes import palette, theme
from adam_gui.vtk_pipelines.common import LegendSpec
from adam_gui.widgets.ui import icon_button, label

MARGIN = 12


class Overlay(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class _GradientBar(QWidget):
    """Horizontal colour ramp with min / mid / max tick labels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._spec: LegendSpec | None = None
        self.setFixedHeight(34)
        self.setMinimumWidth(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_spec(self, spec: LegendSpec):
        self._spec = spec
        self.update()

    def paintEvent(self, _event):
        spec = self._spec
        if spec is None or not spec.stops:
            return
        p = palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bar = QRectF(1, 2, self.width() - 2, 10)
        grad = QLinearGradient(bar.left(), 0, bar.right(), 0)
        n = len(spec.stops)
        for i, c in enumerate(spec.stops):
            grad.setColorAt(i / max(1, n - 1), QColor(c))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(bar, 4, 4)
        font = QFont(self.font())
        font.setPixelSize(11)  # the stylesheet sets pixel sizes, so pointSizeF() is -1
        painter.setFont(font)
        painter.setPen(QPen(QColor(p.text_muted)))
        mid = (spec.vmin + spec.vmax) / 2
        labels = [(0.0, spec.vmin, Qt.AlignmentFlag.AlignLeft),
                  (0.5, mid, Qt.AlignmentFlag.AlignHCenter),
                  (1.0, spec.vmax, Qt.AlignmentFlag.AlignRight)]
        for t, value, align in labels:
            x = bar.left() + t * bar.width()
            tick = QColor(p.text_faint)
            painter.setPen(QPen(tick, 1))
            painter.drawLine(int(x), int(bar.bottom()) + 1, int(x), int(bar.bottom()) + 4)
            painter.setPen(QPen(QColor(p.text_muted)))
            text = _format(spec.fmt, value)
            w = 80
            if align == Qt.AlignmentFlag.AlignLeft:
                rect = QRectF(x, bar.bottom() + 5, w, 16)
            elif align == Qt.AlignmentFlag.AlignRight:
                rect = QRectF(x - w, bar.bottom() + 5, w, 16)
            else:
                rect = QRectF(x - w / 2, bar.bottom() + 5, w, 16)
            painter.drawText(rect, int(align | Qt.AlignmentFlag.AlignTop), text)
        painter.end()


def _format(fmt: str, value: float) -> str:
    try:
        return fmt.format(value)
    except (ValueError, TypeError):
        return str(value)


class _Swatch(QWidget):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(12, 12)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(QRectF(0.5, 0.5, 11, 11))
        painter.end()


class LegendOverlay(Overlay):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(12, 10, 12, 10)
        self._lay.setSpacing(6)
        self.title = label("", "overline", wrap=True)
        self._lay.addWidget(self.title)
        self.bar = _GradientBar()
        self._lay.addWidget(self.bar)
        self._items = QWidget()
        self._items_lay = QVBoxLayout(self._items)
        self._items_lay.setContentsMargins(0, 0, 0, 0)
        self._items_lay.setSpacing(4)
        self._lay.addWidget(self._items)
        self.note = label("", "faint", wrap=True)
        self._lay.addWidget(self.note)
        self.setFixedWidth(230)
        self._spec: LegendSpec | None = None
        theme().changed.connect(self._on_theme)

    def _on_theme(self, *_):
        self.set_spec(self._spec)

    def set_spec(self, spec: LegendSpec | None):
        self._spec = spec
        if spec is None:
            self.hide()
            return
        self.title.setText(spec.title.upper())
        categorical = spec.kind == "categorical"
        self.bar.setVisible(not categorical)
        if not categorical:
            self.bar.set_spec(spec)
        while self._items_lay.count():
            item = self._items_lay.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._items.setVisible(categorical)
        if categorical:
            for text, color in spec.items:
                row = QWidget()
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 0, 0, 0)
                rl.setSpacing(8)
                rl.addWidget(_Swatch(color))
                rl.addWidget(label(text), 1)
                self._items_lay.addWidget(row)
        self.note.setText(spec.note)
        self.note.setVisible(bool(spec.note))
        self.show()
        self.adjustSize()


class InfoOverlay(Overlay):
    """Title plus key/value rows. Shows scene stats or the picked object."""

    close_requested = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 10, 12)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(6)
        self.title = label("", "section")
        head.addWidget(self.title, 1)
        self.close_btn = icon_button("x", "Clear selection (Esc)", size=14)
        self.close_btn.clicked.connect(self.close_requested.emit)
        head.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(head)
        self.subtitle = label("", "faint", wrap=True)
        lay.addWidget(self.subtitle)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(14)
        self._grid.setVerticalSpacing(5)
        lay.addWidget(self._grid_host)
        self.setFixedWidth(258)

    def set_content(self, title: str, rows: list[tuple[str, str]], subtitle: str = "",
                    closable: bool = False, dots: dict[str, str] | None = None):
        self.title.setText(title)
        self.subtitle.setText(subtitle)
        self.subtitle.setVisible(bool(subtitle))
        self.close_btn.setVisible(closable)
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        for r, (key, value) in enumerate(rows):
            k = QWidget()
            kl = QHBoxLayout(k)
            kl.setContentsMargins(0, 0, 0, 0)
            kl.setSpacing(6)
            if dots and key in dots:
                kl.addWidget(_Swatch(dots[key]))
            kl.addWidget(label(key, "muted"))
            kl.addStretch(1)
            v = label(value)
            v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._grid.addWidget(k, r, 0)
            self._grid.addWidget(v, r, 1)
        self.setVisible(bool(title or rows))
        self.adjustSize()


class CameraToolbar(Overlay):
    reset = Signal()
    view = Signal(str)
    save = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        home = icon_button("rotate-ccw", "Reset view (R)", size=16)
        home.clicked.connect(self.reset.emit)
        lay.addWidget(home)
        lay.addWidget(_vline())
        for key, text, tip in (("front", "Front", "Look along the depth axis (F)"),
                               ("side", "Side", "Look from the side"),
                               ("top", "Top", "Look from above (T)"),
                               ("iso", "3D", "Angled view")):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            b.clicked.connect(lambda _=False, k=key: self.view.emit(k))
            lay.addWidget(b)
        lay.addWidget(_vline())
        shot = icon_button("camera", "Save image…", size=16)
        shot.clicked.connect(self.save.emit)
        lay.addWidget(shot)
        self.adjustSize()


class _VLine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(9, 18)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(4, 0, 1, self.height(), QColor(palette().border_strong))
        painter.end()


def _vline() -> QWidget:
    return _VLine()


class HintOverlay(Overlay):
    DEFAULT = "Drag to rotate · Shift-drag to pan · Scroll to zoom · Click for details"

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 5, 10, 5)
        self.text = label(self.DEFAULT, "faint")
        lay.addWidget(self.text)
        self._default = self.DEFAULT

    def set_default(self, text: str):
        self._default = text
        self.text.setText(text)
        self.adjustSize()

    def show_hover(self, text: str | None):
        if text:
            self.text.setProperty("role", "")
            self.text.setText(text)
        else:
            self.text.setProperty("role", "faint")
            self.text.setText(self._default)
        self.text.style().unpolish(self.text)
        self.text.style().polish(self.text)
        self.adjustSize()


class OverlayHost(QObject):
    """Keeps overlays pinned to the canvas corners."""

    def __init__(self, canvas: QWidget, top_left: QWidget, top_right: QWidget,
                 bottom_left: QWidget, bottom_right: QWidget):
        super().__init__(canvas)
        self._canvas = canvas
        self._tl, self._tr, self._bl, self._br = top_left, top_right, bottom_left, bottom_right
        canvas.installEventFilter(self)
        for w in (top_left, top_right, bottom_left, bottom_right):
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest):
            self.place()
        return False

    def place(self):
        c = self._canvas
        w, h = c.width(), c.height()
        for widget in (self._tl, self._tr, self._bl, self._br):
            widget.adjustSize()
        self._tl.move(MARGIN, MARGIN)
        self._tr.move(max(MARGIN, w - self._tr.width() - MARGIN), MARGIN)
        self._bl.move(MARGIN, max(MARGIN, h - self._bl.height() - MARGIN))
        self._br.move(max(MARGIN, w - self._br.width() - MARGIN), max(MARGIN, h - self._br.height() - MARGIN))
        for widget in (self._tl, self._tr, self._bl, self._br):
            widget.raise_()
