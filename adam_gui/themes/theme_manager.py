"""Theme management for the ADAM GUI application."""

from pathlib import Path


THEMES_DIR = Path(__file__).parent


class ThemeManager:
    """Load and apply QSS themes."""

    DARK = "dark"
    LIGHT = "light"

    def __init__(self, app):
        self._app = app
        self._current = self.DARK

    @property
    def current_theme(self) -> str:
        return self._current

    @property
    def is_dark(self) -> bool:
        return self._current == self.DARK

    def apply(self, theme: str) -> None:
        qss_path = THEMES_DIR / f"{theme}.qss"
        if qss_path.exists():
            self._app.setStyleSheet(qss_path.read_text())
            self._current = theme

    def toggle(self) -> str:
        new_theme = self.LIGHT if self._current == self.DARK else self.DARK
        self.apply(new_theme)
        return new_theme

    def chart_colors(self) -> dict:
        """Return color dict matching current theme for matplotlib charts."""
        if self.is_dark:
            return {
                "bg": "#1e1e2e",
                "fg": "#cdd6f4",
                "grid": "#313244",
                "accent": "#89b4fa",
                "axes": "#a6adc8",
            }
        return {
            "bg": "#eff1f5",
            "fg": "#4c4f69",
            "grid": "#ccd0da",
            "accent": "#1e66f5",
            "axes": "#6c6f85",
        }
