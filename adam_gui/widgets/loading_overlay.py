"""Translucent loading overlay with spinner animation."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QLabel, Qt, QTimer,
)


class LoadingOverlay(QWidget):
    """A translucent overlay with a spinning indicator and message."""

    _FRAMES = ["|", "/", "-", "\\"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._frame = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._advance_frame)
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        self.setStyleSheet("background-color: rgba(0, 0, 0, 160); border-radius: 8px;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.spinner_label = QLabel(self._FRAMES[0])
        self.spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner_label.setStyleSheet("color: white; font-size: 28px; font-weight: bold; background: transparent;")
        layout.addWidget(self.spinner_label)

        self.message_label = QLabel("Loading...")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setStyleSheet("color: white; font-size: 14px; background: transparent;")
        layout.addWidget(self.message_label)

    def show_message(self, message: str = "Loading..."):
        """Show the overlay with a message."""
        self.message_label.setText(message)
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self._timer.start(150)

    def hide_overlay(self):
        """Hide the overlay."""
        self._timer.stop()
        self.hide()

    def _advance_frame(self):
        self._frame = (self._frame + 1) % len(self._FRAMES)
        self.spinner_label.setText(self._FRAMES[self._frame])

    def resizeEvent(self, event):
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)
