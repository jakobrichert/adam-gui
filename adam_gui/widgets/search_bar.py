"""Filterable search input with debounce."""

from adam_gui.qt_compat import QWidget, QHBoxLayout, QLineEdit, QPushButton, Signal, QTimer


class SearchBar(QWidget):
    """Search input with debounced text changed signal."""

    search_changed = Signal(str)

    def __init__(self, placeholder: str = "Search...", debounce_ms: int = 300, parent=None):
        super().__init__(parent)
        self._debounce_ms = debounce_ms
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._emit_search)
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.textChanged.connect(self._on_text_changed)
        self.input.setClearButtonEnabled(True)
        layout.addWidget(self.input, 1)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedWidth(60)
        self.clear_btn.clicked.connect(self.clear)
        layout.addWidget(self.clear_btn)

    def _on_text_changed(self, text: str):
        self._timer.start(self._debounce_ms)

    def _emit_search(self):
        self.search_changed.emit(self.input.text())

    def clear(self):
        self.input.clear()
        self.search_changed.emit("")

    def text(self) -> str:
        return self.input.text()
