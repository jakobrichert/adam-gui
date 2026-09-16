"""Small, theme-aware building blocks shared by every page."""

from __future__ import annotations

from typing import Iterable, Sequence

from adam_gui.icons import bind_icon, pixmap
from adam_gui.qt_compat import (
    QButtonGroup, QColor, QEasingCurve, QFrame, QGraphicsOpacityEffect, QGridLayout,
    QHBoxLayout, QLabel, QLinearGradient, QPainter, QPainterPath, QPen, QPointF,
    QPropertyAnimation, QPushButton, QScrollArea, QSizePolicy, Qt, QTimer,
    QToolButton, QVBoxLayout, QWidget, Signal,
)
from adam_gui.themes import palette, theme


# ---------------------------------------------------------------- helpers

def repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_role(widget: QWidget, role: str | None) -> None:
    widget.setProperty("role", role or "")
    repolish(widget)


def label(text: str = "", role: str | None = None, wrap: bool = False,
          selectable: bool = False) -> QLabel:
    lbl = QLabel(text)
    if role:
        lbl.setProperty("role", role)
    if wrap:
        lbl.setWordWrap(True)
    if selectable:
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lbl


def button(text: str = "", variant: str | None = None, icon: str | None = None,
           tooltip: str | None = None, checkable: bool = False) -> QPushButton:
    btn = QPushButton(f" {text}" if icon and text else text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if variant:
        btn.setProperty("variant", variant)
    if icon:
        role = "on_accent" if variant == "primary" else (
            "danger" if variant == "danger" else "text")
        bind_icon(btn, icon, role=role, active_role="accent" if variant == "ghost" else None, size=16)
    if tooltip:
        btn.setToolTip(tooltip)
    btn.setCheckable(checkable)
    return btn


def icon_button(icon: str, tooltip: str, checkable: bool = False, size: int = 18) -> QToolButton:
    btn = QToolButton()
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip(tooltip)
    btn.setAutoRaise(True)
    btn.setCheckable(checkable)
    bind_icon(btn, icon, role="text_muted", active_role="accent", size=size)
    return btn


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.Shape.NoFrame)
    return line


def hbox(*items, spacing: int = 8, margins: Sequence[int] = (0, 0, 0, 0),
         stretch_at: int | None = None) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    _fill(lay, items)
    return lay


def vbox(*items, spacing: int = 8, margins: Sequence[int] = (0, 0, 0, 0)) -> QVBoxLayout:
    lay = QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    _fill(lay, items)
    return lay


def _fill(lay, items: Iterable) -> None:
    for item in items:
        if item is None:
            lay.addStretch(1)
        elif isinstance(item, int):
            lay.addSpacing(item)
        elif isinstance(item, QWidget):
            lay.addWidget(item)
        else:
            lay.addLayout(item)


# ---------------------------------------------------------------- containers

class Card(QFrame):
    """Rounded surface with an optional header (title, subtitle, actions)."""

    def __init__(self, title: str | None = None, subtitle: str | None = None,
                 parent: QWidget | None = None, padding: int = 16, spacing: int = 12):
        super().__init__(parent)
        self.setObjectName("Card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(padding, padding, padding, padding)
        self._outer.setSpacing(spacing)
        self.header_actions = QHBoxLayout()
        self.header_actions.setSpacing(6)
        if title:
            head = QHBoxLayout()
            head.setSpacing(8)
            titles = QVBoxLayout()
            titles.setSpacing(2)
            self.title_label = label(title, "section")
            titles.addWidget(self.title_label)
            if subtitle:
                self.subtitle_label = label(subtitle, "muted", wrap=True)
                titles.addWidget(self.subtitle_label)
            head.addLayout(titles, 1)
            head.addLayout(self.header_actions)
            self._outer.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(spacing)
        self.body.setContentsMargins(0, 0, 0, 0)
        self._outer.addLayout(self.body, 1)

    def add(self, item, stretch: int = 0):
        if isinstance(item, QWidget):
            self.body.addWidget(item, stretch)
        else:
            self.body.addLayout(item, stretch)
        return item

    def set_interactive(self, on: bool = True):
        self.setProperty("interactive", "true" if on else "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor if on else Qt.CursorShape.ArrowCursor)
        repolish(self)


class ClickableCard(Card):
    clicked = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_interactive(True)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class PageHeader(QWidget):
    """Title + subtitle on the left, action widgets on the right."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = label(title, "title")
        self.subtitle = label(subtitle, "subtitle", wrap=True)
        self.subtitle.setVisible(bool(subtitle))
        text.addWidget(self.title)
        text.addWidget(self.subtitle)
        lay.addLayout(text, 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        lay.addLayout(self.actions)

    def add_action(self, widget: QWidget) -> QWidget:
        self.actions.addWidget(widget)
        return widget

    def set_subtitle(self, text: str):
        self.subtitle.setText(text)
        self.subtitle.setVisible(bool(text))


class Page(QWidget):
    """Standard page: padded column with a header and a body layout."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None,
                 margins: Sequence[int] = (28, 22, 28, 22)):
        super().__init__(parent)
        self.setObjectName("Page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(*margins)
        self.root.setSpacing(18)
        self.header = PageHeader(title, subtitle)
        self.root.addWidget(self.header)


class ScrollBody(QScrollArea):
    """Transparent scroll area wrapping a vertical body layout."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 16,
                 margins: Sequence[int] = (0, 0, 0, 0)):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("ScrollBody")
        body.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)
        self.layout_ = QVBoxLayout(body)
        self.layout_.setContentsMargins(*margins)
        self.layout_.setSpacing(spacing)
        self.setWidget(body)
        body.setAutoFillBackground(False)  # setWidget() turns it back on

    def add(self, item, stretch: int = 0):
        if isinstance(item, QWidget):
            self.layout_.addWidget(item, stretch)
        else:
            self.layout_.addLayout(item, stretch)
        return item


class IconBadge(QLabel):
    """Rounded square with a tinted icon (used in cards and empty states)."""

    def __init__(self, icon: str, size: int = 40, tone: str = "accent", parent=None):
        super().__init__(parent)
        self._icon = icon
        self._size = size
        self._tone = tone
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme().changed.connect(self._refresh)
        self._refresh()

    def set_icon(self, icon: str):
        self._icon = icon
        self._refresh()

    def _refresh(self, *_):
        p = palette()
        color = {"accent": p.accent, "info": p.info, "warning": p.warning,
                 "danger": p.danger, "muted": p.text_muted}.get(self._tone, p.accent)
        soft = {"accent": p.accent_soft, "info": p.info_soft, "warning": p.warning_soft,
                "danger": p.danger_soft, "muted": p.surface_3}.get(self._tone, p.accent_soft)
        self.setStyleSheet(f"background-color: {soft}; border-radius: {self._size // 4}px;")
        self.setPixmap(pixmap(self._icon, color, int(self._size * 0.5)))


class EmptyState(QWidget):
    """Centered illustration + message + call-to-action buttons."""

    def __init__(self, icon: str, title: str, message: str,
                 actions: Sequence[QWidget] = (), parent: QWidget | None = None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.addStretch(1)
        col = QVBoxLayout()
        col.setSpacing(10)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        badge = IconBadge(icon, 56)
        col.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
        col.addSpacing(6)
        self.title = label(title, "empty-title")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.title, 0, Qt.AlignmentFlag.AlignHCenter)
        self.message = label(message, "muted", wrap=True)
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fit_message()
        col.addWidget(self.message, 0, Qt.AlignmentFlag.AlignHCenter)
        if actions:
            col.addSpacing(8)
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addStretch(1)
            for a in actions:
                row.addWidget(a)
            row.addStretch(1)
            col.addLayout(row)
        outer.addLayout(col)
        outer.addStretch(2)

    MESSAGE_WIDTH = 440

    def _fit_message(self):
        # A word-wrapped label in an aligned layout cell ignores height-for-width,
        # so give it an explicit width and the height that width needs.
        self.message.ensurePolished()
        self.message.setFixedWidth(self.MESSAGE_WIDTH)
        self.message.setMinimumHeight(self.message.heightForWidth(self.MESSAGE_WIDTH) + 4)

    def set_message(self, text: str):
        self.message.setText(text)
        self._fit_message()

    def showEvent(self, event):
        self._fit_message()
        super().showEvent(event)


class Banner(QFrame):
    """Inline notice with an icon, text and optional action."""

    ICONS = {"info": "info", "warning": "alert-triangle", "danger": "alert-circle", "accent": "check-circle"}

    def __init__(self, text: str, tone: str = "info", action: QWidget | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Banner")
        self.setProperty("tone", tone)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)
        self._icon = QLabel()
        self._tone = tone
        lay.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        self.text = label(text, wrap=True)
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.text.setOpenExternalLinks(True)
        lay.addWidget(self.text, 1)
        if action is not None:
            lay.addWidget(action, 0, Qt.AlignmentFlag.AlignVCenter)
        theme().changed.connect(self._refresh)
        self._refresh()

    def set_tone(self, tone: str):
        self._tone = tone
        self.setProperty("tone", tone)
        repolish(self)
        self._refresh()

    def set_text(self, text: str):
        self.text.setText(text)

    def _refresh(self, *_):
        p = palette()
        color = {"info": p.info, "warning": p.warning, "danger": p.danger, "accent": p.accent}[self._tone]
        self._icon.setPixmap(pixmap(self.ICONS[self._tone], color, 18))


# ---------------------------------------------------------------- data display

class Sparkline(QWidget):
    """Tiny trend line with a soft area fill."""

    def __init__(self, parent=None, color_role: str = "accent"):
        super().__init__(parent)
        self._values: list[float] = []
        self._role = color_role
        self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(40)
        theme().changed.connect(self.update)

    def set_values(self, values: Sequence[float], color_role: str | None = None):
        self._values = [float(v) for v in values if v == v]  # drop NaN
        if color_role:
            self._role = color_role
        self.update()

    def paintEvent(self, _event):
        if len(self._values) < 2:
            return
        p = palette()
        color = QColor(getattr(p, self._role))
        w, h = self.width(), self.height()
        lo, hi = min(self._values), max(self._values)
        span = (hi - lo) or 1.0
        n = len(self._values)
        pts = [QPointF(2 + i * (w - 4) / (n - 1), 3 + (h - 6) * (1 - (v - lo) / span))
               for i, v in enumerate(self._values)]
        path = QPainterPath(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        area = QPainterPath(path)
        area.lineTo(QPointF(pts[-1].x(), h))
        area.lineTo(QPointF(pts[0].x(), h))
        area.closeSubpath()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 0, h)
        top = QColor(color)
        top.setAlpha(70)
        bottom = QColor(color)
        bottom.setAlpha(0)
        grad.setColorAt(0, top)
        grad.setColorAt(1, bottom)
        painter.fillPath(area, grad)
        pen = QPen(color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(pts[-1], 3, 3)
        painter.end()


class KpiCard(Card):
    """Headline number with a caption, delta and optional sparkline."""

    def __init__(self, title: str, icon: str | None = None, help_text: str = "", parent=None):
        super().__init__(parent=parent, padding=16, spacing=6)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.title_label = label(title.upper(), "overline")
        head.addWidget(self.title_label)
        head.addStretch(1)
        if icon:
            self._badge = IconBadge(icon, 26, "muted")
            head.addWidget(self._badge)
        self.add(head)
        self.value_label = label("—", "kpi")
        self.add(self.value_label)
        self.detail_label = label("", "kpi-delta-flat")
        self.add(self.detail_label)
        self.spark = Sparkline()
        self.spark.setVisible(False)
        self.add(self.spark)
        if help_text:
            self.setToolTip(help_text)

    def set_value(self, value: str, detail: str = "", trend: str = "flat",
                  series: Sequence[float] | None = None, series_role: str = "accent"):
        self.value_label.setText(value)
        self.detail_label.setText(detail)
        set_role(self.detail_label, {"up": "kpi-delta-up", "down": "kpi-delta-down"}.get(trend, "kpi-delta-flat"))
        if series is not None and len(series) > 1:
            self.spark.set_values(series, series_role)
            self.spark.setVisible(True)
        else:
            self.spark.setVisible(False)

    def clear(self):
        self.set_value("—", "")


class SegmentedControl(QFrame):
    """Exclusive pill buttons; emits the key of the selected option."""

    changed = Signal(str)

    def __init__(self, options: Sequence[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._keys: list[str] = []
        for i, (key, text) in enumerate(options):
            b = QPushButton(text)
            b.setProperty("segment", "true")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(b, i)
            lay.addWidget(b)
            self._keys.append(key)
        if self._keys:
            self._group.button(0).setChecked(True)
        self._group.idClicked.connect(lambda i: self.changed.emit(self._keys[i]))

    def current(self) -> str:
        i = self._group.checkedId()
        return self._keys[i] if i >= 0 else ""

    def set_current(self, key: str, emit: bool = False):
        if key in self._keys:
            self._group.button(self._keys.index(key)).setChecked(True)
            if emit:
                self.changed.emit(key)


class FormGrid(QGridLayout):
    """Two-column label/field grid with optional help text under fields."""

    def __init__(self, columns: int = 2, parent=None):
        super().__init__(parent)
        self._columns = columns
        self._count = 0
        self.setHorizontalSpacing(20)
        self.setVerticalSpacing(12)
        for c in range(columns):
            self.setColumnStretch(c, 1)

    def add_field(self, text: str, widget: QWidget, help_text: str = "",
                  span: int = 1) -> QWidget:
        if self._count % self._columns + span > self._columns:
            self._count += self._columns - self._count % self._columns
        row, col = divmod(self._count, self._columns)
        cell = QWidget()
        lay = QVBoxLayout(cell)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        cap = label(text, "muted")
        cap.setBuddy(widget)
        lay.addWidget(cap)
        lay.addWidget(widget)
        if help_text:
            lay.addWidget(label(help_text, "help", wrap=True))
            widget.setToolTip(help_text)
        cell.caption = cap
        self.addWidget(cell, row, col, 1, span, Qt.AlignmentFlag.AlignTop)
        self._count += span
        return cell

    def add_full(self, widget: QWidget) -> QWidget:
        if self._count % self._columns:
            self._count += self._columns - self._count % self._columns
        row = self._count // self._columns
        self.addWidget(widget, row, 0, 1, self._columns)
        self._count += self._columns
        return widget


# ---------------------------------------------------------------- toast

class Toast(QFrame):
    """Transient notification anchored to the bottom of a window."""

    def __init__(self, parent: QWidget, text: str, tone: str = "accent", timeout_ms: int = 2600):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 16, 10)
        lay.setSpacing(10)
        p = palette()
        color = {"accent": p.accent, "info": p.info, "warning": p.warning, "danger": p.danger}.get(tone, p.accent)
        ic = QLabel()
        ic.setPixmap(pixmap(Banner.ICONS.get(tone, "info"), color, 18))
        lay.addWidget(ic)
        lay.addWidget(label(text))
        self.adjustSize()
        self._place()
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(180)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.show()
        self.raise_()
        self._anim.start()
        QTimer.singleShot(timeout_ms, self._fade_out)

    def _place(self):
        parent = self.parentWidget()
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 46
        self.move(max(8, x), max(8, y))

    def _fade_out(self):
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.deleteLater)
        self._anim.start()


def toast(widget: QWidget, text: str, tone: str = "accent") -> None:
    """Show a toast on the top-level window containing ``widget``."""
    window = widget.window() if widget is not None else None
    if window is None:
        return
    Toast(window, text, tone)
