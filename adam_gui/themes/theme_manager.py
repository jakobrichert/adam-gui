"""Theme management: applies palette, stylesheet and notifies listeners."""

from __future__ import annotations

from adam_gui.qt_compat import QApplication, QColor, QObject, QPalette, Signal
from adam_gui.themes.palette import DARK, PALETTES, Palette
from adam_gui.themes.stylesheet import build_stylesheet


class ThemeManager(QObject):
    """Process-wide theme state. Use ``theme()`` to get the instance."""

    DARK = "dark"
    LIGHT = "light"

    changed = Signal(object)  # Palette

    _instance: "ThemeManager | None" = None

    def __init__(self):
        super().__init__()
        self._palette: Palette = DARK

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def palette(self) -> Palette:
        return self._palette

    @property
    def current_theme(self) -> str:
        return self._palette.name

    @property
    def is_dark(self) -> bool:
        return self._palette.is_dark

    def apply(self, name: str) -> None:
        from adam_gui import icons

        p = PALETTES.get(name, DARK)
        self._palette = p
        app = QApplication.instance()
        if app is not None:
            if app.style().objectName().lower() != "fusion":
                app.setStyle("Fusion")
            app.setPalette(_qpalette(p))
            icon_paths = icons.write_svg_files(p.name, {
                "chevron_up": ("chevron-up", p.text_muted),
                "chevron_down": ("chevron-down", p.text_muted),
                "check": ("check", p.on_accent),
                "dot": ("dot", p.on_accent),
            })
            app.setStyleSheet(build_stylesheet(p, icon_paths))
        self.changed.emit(p)

    def toggle(self) -> str:
        self.apply(self.LIGHT if self.is_dark else self.DARK)
        return self.current_theme

    def chart_colors(self) -> dict:
        p = self._palette
        return {"bg": p.surface, "fg": p.text, "muted": p.text_muted,
                "grid": p.grid, "accent": p.accent, "axes": p.border_strong}


def _qpalette(p: Palette) -> QPalette:
    pal = QPalette()
    role = QPalette.ColorRole
    group = QPalette.ColorGroup

    def c(value: str) -> QColor:
        return QColor(value)

    pal.setColor(role.Window, c(p.bg))
    pal.setColor(role.WindowText, c(p.text))
    pal.setColor(role.Base, c(p.surface_2))
    pal.setColor(role.AlternateBase, c(p.surface))
    pal.setColor(role.Text, c(p.text))
    pal.setColor(role.PlaceholderText, c(p.text_faint))
    pal.setColor(role.Button, c(p.surface_2))
    pal.setColor(role.ButtonText, c(p.text))
    pal.setColor(role.BrightText, c(p.danger))
    pal.setColor(role.Highlight, c(p.accent))
    pal.setColor(role.HighlightedText, c(p.on_accent))
    pal.setColor(role.ToolTipBase, c(p.surface_3))
    pal.setColor(role.ToolTipText, c(p.text))
    pal.setColor(role.Link, c(p.accent))
    pal.setColor(role.Light, c(p.surface_3))
    pal.setColor(role.Midlight, c(p.surface_2))
    pal.setColor(role.Mid, c(p.border_strong))
    pal.setColor(role.Dark, c(p.border))
    pal.setColor(role.Shadow, QColor(0, 0, 0, 120))
    for r in (role.WindowText, role.Text, role.ButtonText):
        pal.setColor(group.Disabled, r, c(p.text_faint))
    return pal


def theme() -> ThemeManager:
    return ThemeManager.instance()


def palette() -> Palette:
    return ThemeManager.instance().palette
