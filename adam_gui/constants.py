"""Application-wide constants and defaults."""

APP_NAME = "ADAM GUI"
APP_VERSION = "0.1.0"
ORG_NAME = "AdamGui"
ORG_DOMAIN = "adam-gui.github.io"

# Window defaults
DEFAULT_WINDOW_WIDTH = 1400
DEFAULT_WINDOW_HEIGHT = 900
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 600

# Sidebar
SIDEBAR_WIDTH = 60
SIDEBAR_ICON_SIZE = 28

# Navigation page indices
PAGE_PARAMETERS = 0
PAGE_RUNNER = 1
PAGE_RESULTS = 2
PAGE_VISUALIZATIONS = 3
PAGE_SETTINGS = 4

# Color palettes for charts
CHART_COLORS = [
    "#89b4fa",  # Blue
    "#a6e3a1",  # Green
    "#fab387",  # Peach
    "#f38ba8",  # Red
    "#cba6f7",  # Mauve
    "#f9e2af",  # Yellow
    "#94e2d5",  # Teal
    "#f2cdcd",  # Flamingo
    "#74c7ec",  # Sapphire
    "#b4befe",  # Lavender
]

# VTK colors
VTK_BG_DARK = (0.12, 0.12, 0.15)
VTK_BG_DARK_GRADIENT = (0.05, 0.05, 0.08)
VTK_BG_LIGHT = (0.95, 0.95, 0.97)
VTK_BG_LIGHT_GRADIENT = (0.85, 0.85, 0.90)

# File extensions
PROJECT_EXTENSION = ".adam-project"
PARAM_FILE_EXTENSION = ".adam-params"

# Status codes
STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_ERROR = "error"
STATUS_UNKNOWN = "unknown"
