"""ADAM GUI application entry point."""

from adam_gui.qt_compat import QApplication, QSettings, Qt
from adam_gui.constants import APP_NAME, APP_VERSION, ORG_NAME, ORG_DOMAIN
from adam_gui.main_window import MainWindow
from adam_gui.themes.theme_manager import ThemeManager


class AdamApplication(QApplication):
    """Main application class."""

    def __init__(self, argv):
        super().__init__(argv)

        self.setApplicationName(APP_NAME)
        self.setApplicationVersion(APP_VERSION)
        self.setOrganizationName(ORG_NAME)
        self.setOrganizationDomain(ORG_DOMAIN)

        # Settings
        self.settings = QSettings()

        # Theme
        self.theme_manager = ThemeManager(self)
        saved_theme = self.settings.value("theme", ThemeManager.DARK)
        self.theme_manager.apply(saved_theme)

        # Main window
        self.main_window = MainWindow()
        self.main_window.theme_toggle_requested.connect(self._toggle_theme)
        self.main_window.show()

    def _toggle_theme(self):
        new_theme = self.theme_manager.toggle()
        self.settings.setValue("theme", new_theme)


def main():
    import sys
    app = AdamApplication(sys.argv)
    sys.exit(app.exec())
