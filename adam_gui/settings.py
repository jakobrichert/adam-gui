"""Typed access to persistent application settings (QSettings)."""

from __future__ import annotations

import os
from pathlib import Path

from adam_gui.qt_compat import QByteArray, QObject, QSettings, Signal
from adam_gui.services.adam_runner import AdamRunner


class AppSettings(QObject):
    changed = Signal(str)  # key

    MAX_RECENT = 8

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        # ADAM_GUI_SETTINGS=/path/file.ini isolates tests and screenshot scripts
        override = os.environ.get("ADAM_GUI_SETTINGS")
        self._s = QSettings(override, QSettings.Format.IniFormat) if override else QSettings()

    # ------------------------------------------------------------ generic
    def _get(self, key: str, default=None, type_=str):
        value = self._s.value(key, default)
        if value is None:
            return default
        if type_ is bool:
            return value in (True, "true", "1", 1)
        if type_ is list:
            if isinstance(value, str):
                return [value] if value else []
            return list(value)
        try:
            return type_(value)
        except (TypeError, ValueError):
            return default

    def _set(self, key: str, value):
        self._s.setValue(key, value)
        self._s.sync()
        self.changed.emit(key)

    # ------------------------------------------------------------ values
    @property
    def theme(self) -> str:
        return self._get("theme", "dark")

    @theme.setter
    def theme(self, value: str):
        self._set("theme", value)

    @property
    def adam_executable(self) -> str:
        env = os.environ.get("ADAM_EXECUTABLE", "")
        return self._get("adam/executable", "") or env

    @adam_executable.setter
    def adam_executable(self, value: str):
        self._set("adam/executable", value.strip())

    @property
    def adam_available(self) -> bool:
        path = self.adam_executable
        return bool(path) and AdamRunner.is_available(path)

    @property
    def adam_arguments(self) -> str:
        from adam_gui.services.adam_runner import DEFAULT_ARGS
        return self._get("adam/arguments", DEFAULT_ARGS) or DEFAULT_ARGS

    @adam_arguments.setter
    def adam_arguments(self, value: str):
        self._set("adam/arguments", value.strip())

    @property
    def output_directory(self) -> str:
        default = str(Path.home() / "ADAM GUI Runs")
        return self._get("adam/output_directory", default) or default

    @output_directory.setter
    def output_directory(self, value: str):
        self._set("adam/output_directory", value.strip())

    @property
    def keep_run_directories(self) -> bool:
        return self._get("adam/keep_run_directories", True, bool)

    @keep_run_directories.setter
    def keep_run_directories(self, value: bool):
        self._set("adam/keep_run_directories", bool(value))

    @property
    def recent_projects(self) -> list[str]:
        items = self._get("recent_projects", [], list)
        return [p for p in items if p and Path(p).is_file()]

    def add_recent_project(self, path: str):
        path = str(Path(path).resolve())
        items = [p for p in self.recent_projects if p != path]
        items.insert(0, path)
        self._set("recent_projects", items[: self.MAX_RECENT])

    def clear_recent_projects(self):
        self._set("recent_projects", [])

    @property
    def last_directory(self) -> str:
        return self._get("last_directory", str(Path.home()))

    @last_directory.setter
    def last_directory(self, value: str):
        p = Path(value)
        self._set("last_directory", str(p if p.is_dir() else p.parent))

    def window_geometry(self) -> QByteArray | None:
        value = self._s.value("window/geometry")
        return value if isinstance(value, QByteArray) else None

    def set_window_geometry(self, geometry: QByteArray):
        self._s.setValue("window/geometry", geometry)

    @property
    def last_page(self) -> int:
        return self._get("window/last_page", 0, int)

    @last_page.setter
    def last_page(self, value: int):
        self._s.setValue("window/last_page", int(value))
