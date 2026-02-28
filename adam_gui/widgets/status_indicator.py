"""LED-style status indicator widget."""

from adam_gui.qt_compat import (
    QWidget, QHBoxLayout, QLabel, QPainter, QColor, QBrush, Qt,
)


class StatusIndicator(QWidget):
    """Colored circle with a label showing status."""

    COLORS = {
        "ok": "#a6e3a1",
        "warning": "#f9e2af",
        "error": "#f38ba8",
        "unknown": "#6c7086",
    }

    def __init__(self, label: str = "", status: str = "unknown", parent=None):
        super().__init__(parent)
        self._status = status
        self.setFixedHeight(24)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._dot = _Dot(self.COLORS.get(status, self.COLORS["unknown"]))
        layout.addWidget(self._dot)

        self._label = QLabel(label)
        self._label.setObjectName("muted")
        layout.addWidget(self._label)
        layout.addStretch()

    def set_status(self, status: str, label: str = None):
        self._status = status
        self._dot.color = QColor(self.COLORS.get(status, self.COLORS["unknown"]))
        self._dot.update()
        if label is not None:
            self._label.setText(label)

    @property
    def status(self) -> str:
        return self._status


class _Dot(QWidget):
    def __init__(self, color: str):
        super().__init__()
        self.color = QColor(color)
        self.setFixedSize(12, 12)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(self.color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(1, 1, 10, 10)
        painter.end()
