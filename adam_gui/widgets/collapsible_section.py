"""Collapsible section widget with animated expand/collapse."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolButton,
    QLabel, QFrame, QSizePolicy, QParallelAnimationGroup,
    QPropertyAnimation, Qt, Signal,
)


class CollapsibleSection(QWidget):
    """A section with a clickable header that toggles content visibility."""

    toggled = Signal(bool)

    def __init__(self, title: str, parent=None, expanded: bool = True):
        super().__init__(parent)
        self._expanded = expanded

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.03);
                border-radius: 6px;
                padding: 2px;
            }
            QFrame:hover {
                background-color: rgba(255, 255, 255, 0.06);
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 6)

        self._arrow = QToolButton()
        self._arrow.setStyleSheet("QToolButton { border: none; background: transparent; }")
        self._arrow.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self._arrow.setFixedSize(20, 20)
        self._arrow.clicked.connect(self.toggle)

        self._title_label = QLabel(f"<b>{title}</b>")
        self._title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        header_layout.addWidget(self._arrow)
        header_layout.addWidget(self._title_label)

        header.mousePressEvent = lambda e: self.toggle()
        header.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(header)

        # Content area
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(12, 8, 4, 8)
        self._content_layout.setSpacing(8)
        layout.addWidget(self._content)

        if not expanded:
            self._content.setMaximumHeight(0)
            self._content.setVisible(False)

    def add_widget(self, widget: QWidget):
        self._content_layout.addWidget(widget)

    def add_layout(self, layout):
        self._content_layout.addLayout(layout)

    @property
    def content_layout(self):
        return self._content_layout

    def toggle(self):
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._arrow.setArrowType(
            Qt.ArrowType.DownArrow if self._expanded else Qt.ArrowType.RightArrow
        )
        if self._expanded:
            self._content.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        else:
            self._content.setMaximumHeight(0)
        self.toggled.emit(self._expanded)

    def set_expanded(self, expanded: bool):
        if self._expanded != expanded:
            self.toggle()

    @property
    def is_expanded(self) -> bool:
        return self._expanded
