"""Main application window with sidebar navigation and stacked views."""

from pathlib import Path

from adam_gui.qt_compat import (
    QMainWindow, QWidget, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QToolButton, QButtonGroup, QStatusBar, QLabel,
    QAction, QFileDialog, QMessageBox, QSizePolicy,
    Qt, QSize, QIcon, Signal,
)
from adam_gui.constants import (
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT,
    SIDEBAR_WIDTH, SIDEBAR_ICON_SIZE,
    PAGE_PARAMETERS, PAGE_RUNNER, PAGE_RESULTS, PAGE_VISUALIZATIONS, PAGE_SETTINGS,
    APP_NAME,
)

ICONS_DIR = Path(__file__).parent / "assets" / "icons"


class PlaceholderPage(QWidget):
    """Temporary placeholder for pages not yet implemented."""

    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("heading")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc_label = QLabel(description)
        desc_label.setObjectName("subheading")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title_label)
        layout.addWidget(desc_label)


class MainWindow(QMainWindow):
    """Main application window."""

    theme_toggle_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        self._setup_menu_bar()
        self._setup_central()
        self._setup_status_bar()

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")
        self.action_new = QAction("&New Project", self)
        self.action_new.setShortcut("Ctrl+N")
        file_menu.addAction(self.action_new)

        self.action_open = QAction("&Open Project...", self)
        self.action_open.setShortcut("Ctrl+O")
        file_menu.addAction(self.action_open)

        file_menu.addSeparator()

        self.action_save = QAction("&Save Project", self)
        self.action_save.setShortcut("Ctrl+S")
        file_menu.addAction(self.action_save)

        self.action_save_as = QAction("Save &As...", self)
        self.action_save_as.setShortcut("Ctrl+Shift+S")
        file_menu.addAction(self.action_save_as)

        file_menu.addSeparator()

        self.action_import_results = QAction("&Import Results Directory...", self)
        file_menu.addAction(self.action_import_results)

        file_menu.addSeparator()

        self.action_quit = QAction("&Quit", self)
        self.action_quit.setShortcut("Ctrl+Q")
        self.action_quit.triggered.connect(self.close)
        file_menu.addAction(self.action_quit)

        # Simulation menu
        sim_menu = menu_bar.addMenu("&Simulation")
        self.action_run = QAction("&Run Simulation", self)
        self.action_run.setShortcut("Ctrl+R")
        sim_menu.addAction(self.action_run)

        self.action_stop = QAction("&Stop Simulation", self)
        sim_menu.addAction(self.action_stop)

        sim_menu.addSeparator()

        self.action_demo_data = QAction("&Generate Demo Data", self)
        sim_menu.addAction(self.action_demo_data)

        # View menu
        view_menu = menu_bar.addMenu("&View")
        self.action_toggle_theme = QAction("Toggle &Dark/Light Theme", self)
        self.action_toggle_theme.setShortcut("Ctrl+T")
        self.action_toggle_theme.triggered.connect(self.theme_toggle_requested.emit)
        view_menu.addAction(self.action_toggle_theme)

        view_menu.addSeparator()

        self.action_goto_params = QAction("&Parameters", self)
        self.action_goto_params.setShortcut("Ctrl+1")
        self.action_goto_params.triggered.connect(lambda: self.navigate_to(PAGE_PARAMETERS))
        view_menu.addAction(self.action_goto_params)

        self.action_goto_runner = QAction("&Runner", self)
        self.action_goto_runner.setShortcut("Ctrl+2")
        self.action_goto_runner.triggered.connect(lambda: self.navigate_to(PAGE_RUNNER))
        view_menu.addAction(self.action_goto_runner)

        self.action_goto_results = QAction("R&esults", self)
        self.action_goto_results.setShortcut("Ctrl+3")
        self.action_goto_results.triggered.connect(lambda: self.navigate_to(PAGE_RESULTS))
        view_menu.addAction(self.action_goto_results)

        self.action_goto_viz = QAction("3D &Visualizations", self)
        self.action_goto_viz.setShortcut("Ctrl+4")
        self.action_goto_viz.triggered.connect(lambda: self.navigate_to(PAGE_VISUALIZATIONS))
        view_menu.addAction(self.action_goto_viz)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        self.action_about = QAction("&About", self)
        self.action_about.triggered.connect(self._show_about)
        help_menu.addAction(self.action_about)

    def _setup_central(self):
        central = QWidget()
        self.setCentralWidget(central)

        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QToolBar()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setOrientation(Qt.Orientation.Vertical)
        self.sidebar.setMovable(False)
        self.sidebar.setFixedWidth(SIDEBAR_WIDTH)
        self.sidebar.setIconSize(QSize(SIDEBAR_ICON_SIZE, SIDEBAR_ICON_SIZE))

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_items = [
            ("Parameters", "parameters.svg", PAGE_PARAMETERS),
            ("Runner", "runner.svg", PAGE_RUNNER),
            ("Results", "chart.svg", PAGE_RESULTS),
            ("3D Viz", "3d.svg", PAGE_VISUALIZATIONS),
        ]

        self.nav_buttons: list[QToolButton] = []
        for label, icon_file, page_index in nav_items:
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setToolTip(label)
            icon_path = ICONS_DIR / icon_file
            if icon_path.exists():
                btn.setIcon(QIcon(str(icon_path)))
            else:
                btn.setText(label[:2])
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(48)
            self.nav_group.addButton(btn, page_index)
            self.sidebar.addWidget(btn)
            self.nav_buttons.append(btn)

        # Add separator and settings at bottom
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.sidebar.addWidget(spacer)

        settings_btn = QToolButton()
        settings_btn.setCheckable(True)
        settings_btn.setToolTip("Settings")
        icon_path = ICONS_DIR / "settings.svg"
        if icon_path.exists():
            settings_btn.setIcon(QIcon(str(icon_path)))
        else:
            settings_btn.setText("S")
        settings_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        settings_btn.setFixedHeight(48)
        self.nav_group.addButton(settings_btn, PAGE_SETTINGS)
        self.sidebar.addWidget(settings_btn)
        self.nav_buttons.append(settings_btn)

        h_layout.addWidget(self.sidebar)

        # Stacked widget for pages
        self.stack = QStackedWidget()
        self.stack.addWidget(PlaceholderPage(
            "Parameter Editor",
            "Configure ADAM simulation parameters"
        ))
        self.stack.addWidget(PlaceholderPage(
            "Simulation Runner",
            "Execute ADAM simulations and monitor progress"
        ))
        self.stack.addWidget(PlaceholderPage(
            "Result Viewer",
            "Browse simulation results and charts"
        ))
        self.stack.addWidget(PlaceholderPage(
            "3D Visualizations",
            "Interactive 3D views of breeding data"
        ))
        self.stack.addWidget(PlaceholderPage(
            "Settings",
            "Application settings and ADAM configuration"
        ))
        h_layout.addWidget(self.stack)

        # Wire navigation
        self.nav_group.idClicked.connect(self.navigate_to)
        self.nav_buttons[0].setChecked(True)

    def _setup_status_bar(self):
        status = QStatusBar()
        self.setStatusBar(status)

        self.adam_status_label = QLabel("ADAM: Not Found")
        self.adam_status_label.setObjectName("muted")
        status.addPermanentWidget(self.adam_status_label)

        self.project_label = QLabel("Project: Untitled")
        self.project_label.setObjectName("muted")
        status.addWidget(self.project_label)

    def navigate_to(self, page_index: int):
        """Switch to a specific page."""
        if 0 <= page_index < self.stack.count():
            self.stack.setCurrentIndex(page_index)
            btn = self.nav_group.button(page_index)
            if btn:
                btn.setChecked(True)

    def set_page(self, index: int, widget: QWidget):
        """Replace a placeholder page with a real widget."""
        old = self.stack.widget(index)
        self.stack.removeWidget(old)
        old.deleteLater()
        self.stack.insertWidget(index, widget)

    def set_adam_status(self, found: bool, path: str = ""):
        if found:
            self.adam_status_label.setText(f"ADAM: {path}")
        else:
            self.adam_status_label.setText("ADAM: Not Found")

    def set_project_name(self, name: str):
        self.project_label.setText(f"Project: {name}")

    def _show_about(self):
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h3>{APP_NAME}</h3>"
            "<p>Desktop GUI with 3D visualizations for the "
            "ADAM breeding simulator from Aarhus University.</p>"
            "<p>Built with PyQt6 + VTK</p>"
        )
