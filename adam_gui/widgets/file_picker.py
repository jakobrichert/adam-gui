"""File/directory path picker widget."""

from pathlib import Path

from adam_gui.qt_compat import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QFileDialog, Signal,
)


class FilePicker(QWidget):
    """Path selector with a browse button."""

    path_changed = Signal(str)

    def __init__(
        self,
        parent=None,
        placeholder: str = "Select file...",
        file_mode: str = "file",
        file_filter: str = "",
    ):
        super().__init__(parent)
        self._file_mode = file_mode
        self._file_filter = file_filter

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._line_edit = QLineEdit()
        self._line_edit.setPlaceholderText(placeholder)
        self._line_edit.textChanged.connect(self.path_changed.emit)
        layout.addWidget(self._line_edit)

        self._browse_btn = QPushButton("Browse")
        self._browse_btn.setFixedWidth(70)
        self._browse_btn.clicked.connect(self._browse)
        layout.addWidget(self._browse_btn)

    def _browse(self):
        if self._file_mode == "directory":
            path = QFileDialog.getExistingDirectory(self, "Select Directory")
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select File", "", self._file_filter
            )
        if path:
            self._line_edit.setText(path)

    @property
    def path(self) -> str:
        return self._line_edit.text()

    @path.setter
    def path(self, value: str):
        self._line_edit.setText(value)

    def is_valid(self) -> bool:
        p = Path(self._line_edit.text())
        if self._file_mode == "directory":
            return p.is_dir()
        return p.is_file()
