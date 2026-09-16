"""File/directory path picker: line edit, browse button and validity marker."""

from __future__ import annotations

import os
from pathlib import Path

from adam_gui.icons import bind_icon, pixmap
from adam_gui.qt_compat import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QToolButton, QWidget, Qt, Signal,
)
from adam_gui.themes import palette, theme


class FilePicker(QWidget):
    """Path selector.

    file_mode: "file" (any existing file), "executable" (existing, executable
    file), "directory" (existing or creatable directory) or "save" (new file).
    """

    path_changed = Signal(str)

    def __init__(self, parent=None, placeholder: str = "Select file…", file_mode: str = "file",
                 file_filter: str = "", dialog_title: str = "Select file", show_status: bool = True):
        super().__init__(parent)
        self._file_mode = file_mode
        self._file_filter = file_filter
        self._dialog_title = dialog_title
        self._show_status = show_status

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self._line_edit = QLineEdit()
        self._line_edit.setPlaceholderText(placeholder)
        self._line_edit.setClearButtonEnabled(True)
        self._line_edit.textChanged.connect(self._on_text)
        lay.addWidget(self._line_edit, 1)

        self._status = QLabel()
        self._status.setFixedWidth(18)
        self._status.setVisible(show_status)
        lay.addWidget(self._status)

        self._browse = QToolButton()
        self._browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self._browse.setToolTip("Browse…")
        bind_icon(self._browse, "folder", role="text_muted", active_role=None, size=16)
        self._browse.clicked.connect(self._browse_dialog)
        lay.addWidget(self._browse)

        theme().changed.connect(self._refresh_status)
        self._refresh_status()

    # ------------------------------------------------------------ api
    @property
    def path(self) -> str:
        return self._line_edit.text().strip()

    @path.setter
    def path(self, value: str):
        self._line_edit.setText(value or "")

    def setPlaceholderText(self, text: str):  # noqa: N802
        self._line_edit.setPlaceholderText(text)

    def is_valid(self) -> bool:
        text = self.path
        if not text:
            return False
        p = Path(text).expanduser()
        if self._file_mode == "directory":
            return p.is_dir()
        if self._file_mode == "executable":
            return p.is_file() and os.access(p, os.X_OK)
        if self._file_mode == "save":
            return p.parent.is_dir()
        return p.is_file()

    # ------------------------------------------------------------ internals
    def _on_text(self, text: str):
        self._refresh_status()
        self.path_changed.emit(text.strip())

    def _refresh_status(self, *_):
        if not self._show_status:
            return
        p = palette()
        if not self.path:
            self._status.clear()
            self._status.setToolTip("")
        elif self.is_valid():
            self._status.setPixmap(pixmap("check-circle", p.accent, 16))
            self._status.setToolTip("Path looks good")
        elif self._file_mode == "directory":
            self._status.setPixmap(pixmap("info", p.text_faint, 16))
            self._status.setToolTip("This folder does not exist yet; it will be created when needed")
            return
        else:
            self._status.setPixmap(pixmap("alert-circle", p.danger, 16))
            self._status.setToolTip("Not an executable file" if self._file_mode == "executable"
                                    else "File not found")

    def _browse_dialog(self):
        start = self.path or str(Path.home())
        if self._file_mode == "directory":
            path = QFileDialog.getExistingDirectory(self, self._dialog_title, start)
        elif self._file_mode == "save":
            path, _ = QFileDialog.getSaveFileName(self, self._dialog_title, start, self._file_filter)
        else:
            path, _ = QFileDialog.getOpenFileName(self, self._dialog_title, start, self._file_filter)
        if path:
            self._line_edit.setText(path)
