"""Main application window: sidebar navigation, page stack, menus, status bar."""

from __future__ import annotations

from adam_gui.constants import (
    APP_NAME, DEFAULT_WINDOW_HEIGHT, DEFAULT_WINDOW_WIDTH, MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH, PAGE_KEYS, SIDEBAR_WIDTH,
)
from adam_gui.icons import bind_icon, pixmap
from adam_gui.qt_compat import (
    QAction, QButtonGroup, QHBoxLayout, QKeySequence, QLabel, QMainWindow, QMenu, QSizePolicy,
    QStackedWidget, QStatusBar, Qt, QToolButton, QVBoxLayout, QWidget, Signal,
)
from adam_gui.themes import palette, theme
from adam_gui.widgets.ui import set_role

NAV_ITEMS = [
    # key, label, icon, tooltip
    ("parameters", "Setup", "sliders", "Simulation setup (Ctrl+1)"),
    ("run", "Run", "play", "Run simulations (Ctrl+2)"),
    ("results", "Results", "bar-chart", "Results and charts (Ctrl+3)"),
    ("viz", "3D", "box", "3D explorer (Ctrl+4)"),
]


class NavButton(QToolButton):
    def __init__(self, text: str, icon: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.setObjectName("NavButton")
        self.setText(text)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(58)
        bind_icon(self, icon, role="text_muted", active_role="accent", size=22)


class MainWindow(QMainWindow):
    """Top-level window. Pages are installed by the application."""

    theme_toggle_requested = Signal()
    close_requested = Signal(object)  # QCloseEvent; app decides accept/ignore

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME}[*]")
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self._pages: dict[str, QWidget] = {}
        self._build_actions()
        self._build_menus()
        self._build_central()
        self._build_status_bar()
        theme().changed.connect(self._on_theme_changed)
        self._on_theme_changed()

    # ------------------------------------------------------------ actions
    def _action(self, text: str, shortcut=None, tip: str = "", fallback: str = "") -> QAction:
        act = QAction(text, self)
        if shortcut is not None:
            seq = QKeySequence(shortcut)
            if seq.isEmpty() and fallback:  # some platforms define no standard key
                seq = QKeySequence(fallback)
            act.setShortcut(seq)
        if tip:
            act.setStatusTip(tip)
            act.setToolTip(tip)
        self.addAction(act)
        return act

    def _build_actions(self):
        std = QKeySequence.StandardKey
        self.action_new = self._action("&New Project", std.New)
        self.action_open = self._action("&Open Project…", std.Open)
        self.action_save = self._action("&Save Project", std.Save)
        self.action_save_as = self._action("Save Project &As…", std.SaveAs)
        self.action_import_params = self._action("Import Parameters…", None,
                                                 "Load a .adam-params file into the editor")
        self.action_export_params = self._action("Export Parameters…", None,
                                                 "Save the current setup as a .adam-params file")
        self.action_export_adam = self._action("Export ADAM Parameter File…", None,
                                               "Write the setup in ADAM's text format")
        self.action_import_results = self._action("Import ADAM Results Folder…", "Ctrl+I",
                                                  "Load output files from an ADAM run")
        self.action_quit = self._action("&Quit", std.Quit, fallback="Ctrl+Q")
        self.action_quit.setMenuRole(QAction.MenuRole.QuitRole)

        self.action_run = self._action("Run with &ADAM", "Ctrl+R")
        self.action_demo = self._action("Run &Demo Simulation", "Ctrl+Shift+R")
        self.action_stop = self._action("&Stop", "Ctrl+.")
        self.action_stop.setEnabled(False)

        self.action_toggle_theme = self._action("Toggle Light/Dark Theme", "Ctrl+Shift+L")
        self.action_toggle_theme.triggered.connect(self.theme_toggle_requested.emit)
        self.nav_actions: dict[str, QAction] = {}
        for i, (key, _text, _icon, _tip) in enumerate(NAV_ITEMS):
            act = self._action({"parameters": "Setup", "run": "Run", "results": "Results",
                                "viz": "3D Explorer"}[key], f"Ctrl+{i + 1}")
            act.triggered.connect(lambda _=False, k=key: self.navigate_to(k))
            self.nav_actions[key] = act
        self.action_settings = self._action("Settings…", std.Preferences, fallback="Ctrl+,")
        self.action_settings.setMenuRole(QAction.MenuRole.PreferencesRole)
        self.action_settings.triggered.connect(lambda: self.navigate_to("settings"))

        self.action_about = self._action("About ADAM GUI")
        self.action_about.setMenuRole(QAction.MenuRole.AboutRole)
        self.action_quick_start = self._action("Quick Start")
        self.action_adam_site = self._action("ADAM Website")

    def _build_menus(self):
        mb = self.menuBar()
        m = mb.addMenu("&File")
        m.addAction(self.action_new)
        m.addAction(self.action_open)
        self.recent_menu = QMenu("Open &Recent", self)
        m.addMenu(self.recent_menu)
        m.addSeparator()
        m.addAction(self.action_save)
        m.addAction(self.action_save_as)
        m.addSeparator()
        m.addAction(self.action_import_params)
        m.addAction(self.action_export_params)
        m.addAction(self.action_export_adam)
        m.addSeparator()
        m.addAction(self.action_import_results)
        m.addSeparator()
        m.addAction(self.action_settings)
        m.addAction(self.action_quit)

        m = mb.addMenu("&Simulation")
        m.addAction(self.action_demo)
        m.addAction(self.action_run)
        m.addAction(self.action_stop)

        m = mb.addMenu("&View")
        for act in self.nav_actions.values():
            m.addAction(act)
        m.addSeparator()
        m.addAction(self.action_toggle_theme)

        m = mb.addMenu("&Help")
        m.addAction(self.action_quick_start)
        m.addAction(self.action_adam_site)
        m.addSeparator()
        m.addAction(self.action_about)

    # ------------------------------------------------------------ layout
    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.sidebar.setFixedWidth(SIDEBAR_WIDTH)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(10, 14, 10, 12)
        side.setSpacing(4)

        self.brand = QLabel()
        self.brand.setObjectName("BrandMark")
        self.brand.setFixedSize(40, 40)
        self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand.setToolTip(f"{APP_NAME} — graphical front end for the ADAM breeding simulator")
        side.addWidget(self.brand, 0, Qt.AlignmentFlag.AlignHCenter)
        side.addSpacing(14)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, NavButton] = {}
        for key, text, icon, tip in NAV_ITEMS:
            btn = NavButton(text, icon, tip)
            btn.clicked.connect(lambda _=False, k=key: self.navigate_to(k))
            self.nav_group.addButton(btn)
            self.nav_buttons[key] = btn
            side.addWidget(btn)
        side.addStretch(1)

        self.theme_button = QToolButton()
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.setFixedSize(40, 36)
        self.theme_button.clicked.connect(self.theme_toggle_requested.emit)
        side.addWidget(self.theme_button, 0, Qt.AlignmentFlag.AlignHCenter)

        settings_btn = NavButton("Settings", "settings", "Settings (Ctrl+,)")
        settings_btn.clicked.connect(lambda: self.navigate_to("settings"))
        self.nav_group.addButton(settings_btn)
        self.nav_buttons["settings"] = settings_btn
        side.addWidget(settings_btn)

        root.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("PageStack")
        root.addWidget(self.stack, 1)

    def _build_status_bar(self):
        status = QStatusBar()
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)
        self.project_label = QLabel("Untitled project")
        self.run_label = QLabel("")
        status.addWidget(self.project_label)
        status.addWidget(self.run_label)

        self.adam_badge = QLabel("ADAM not configured")
        self.adam_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.adam_badge.setToolTip("Click to configure the ADAM executable")
        self.adam_badge.mousePressEvent = lambda _e: self.navigate_to("settings")
        set_role(self.adam_badge, "badge")
        status.addPermanentWidget(self.adam_badge)

    # ------------------------------------------------------------ pages
    def add_page(self, key: str, widget: QWidget):
        self._pages[key] = widget
        self.stack.addWidget(widget)

    def page(self, key: str) -> QWidget | None:
        return self._pages.get(key)

    def current_page_key(self) -> str:
        current = self.stack.currentWidget()
        for key, widget in self._pages.items():
            if widget is current:
                return key
        return "parameters"

    def navigate_to(self, key: str | int):
        if isinstance(key, int):
            key = PAGE_KEYS[key] if 0 <= key < len(PAGE_KEYS) else "parameters"
        widget = self._pages.get(key)
        if widget is None:
            return
        self.stack.setCurrentWidget(widget)
        btn = self.nav_buttons.get(key)
        if btn is not None:
            btn.setChecked(True)

    # ------------------------------------------------------------ status
    def set_project_status(self, name: str, dirty: bool, path: str = ""):
        self.setWindowTitle(f"{name} — {APP_NAME}[*]")
        self.setWindowModified(dirty)
        self.setWindowFilePath(path)
        self.project_label.setText(f"{name}{'  •  unsaved changes' if dirty else ''}")
        self.project_label.setToolTip(path or "Not saved yet")

    def set_run_status(self, text: str):
        self.run_label.setText(text)

    def set_adam_status(self, available: bool, configured: bool, path: str = ""):
        if available:
            self.adam_badge.setText("ADAM ready")
            set_role(self.adam_badge, "badge-accent")
            self.adam_badge.setToolTip(path)
        elif configured:
            self.adam_badge.setText("ADAM not found")
            set_role(self.adam_badge, "badge-danger")
            self.adam_badge.setToolTip(f"Not an executable file: {path}\nClick to fix in Settings")
        else:
            self.adam_badge.setText("Demo mode · ADAM not configured")
            set_role(self.adam_badge, "badge")
            self.adam_badge.setToolTip("Click to configure the ADAM executable")

    def _on_theme_changed(self, *_):
        p = palette()
        self.brand.setPixmap(pixmap("sprout", p.on_accent, 24))
        bind_icon(self.theme_button, "sun" if p.is_dark else "moon", role="text_muted",
                  active_role=None, size=18)
        self.theme_button.setToolTip("Switch to light theme" if p.is_dark else "Switch to dark theme")

    def closeEvent(self, event):
        self.close_requested.emit(event)
