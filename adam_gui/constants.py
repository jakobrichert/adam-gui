"""Application-wide constants and defaults."""

APP_NAME = "ADAM GUI"
APP_VERSION = "0.2.0"
ORG_NAME = "AdamGui"
ORG_DOMAIN = "adam-gui.github.io"
ADAM_URL = "https://qgg.au.dk/en/research/qgg-big-data-software/adam"
REPO_URL = "https://github.com/jakobrichert/adam-gui"

# Window defaults
DEFAULT_WINDOW_WIDTH = 1440
DEFAULT_WINDOW_HEIGHT = 900
MIN_WINDOW_WIDTH = 1080
MIN_WINDOW_HEIGHT = 680

# Sidebar
SIDEBAR_WIDTH = 88

# Navigation page keys, in sidebar order
PAGE_KEYS = ("parameters", "run", "results", "viz", "settings")
PAGE_PARAMETERS, PAGE_RUNNER, PAGE_RESULTS, PAGE_VISUALIZATIONS, PAGE_SETTINGS = PAGE_KEYS

# File extensions
PROJECT_EXTENSION = ".adam-project"
PARAM_FILE_EXTENSION = ".adam-params"
PROJECT_FILTER = f"ADAM GUI project (*{PROJECT_EXTENSION})"
PARAM_FILTER = f"ADAM GUI parameters (*{PARAM_FILE_EXTENSION} *.json)"
