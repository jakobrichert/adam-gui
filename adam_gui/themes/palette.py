"""Design tokens for the dark and light themes.

Every colour used by the application (widgets, charts, 3D scenes) comes from a
``Palette`` so the two themes stay in sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Categorical series colours, fixed order (validated for colour-vision
# deficiency on the adjacent-pair list in both modes; only the first three are
# safe when every pair can touch, e.g. scatter plots).
LIGHT_SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                "#e87ba4", "#008300", "#4a3aa7", "#e34948")
DARK_SERIES = ("#3987e5", "#d95926", "#199e70", "#c98500",
               "#d55181", "#008300", "#9085e9", "#e66767")

# Single-hue sequential ramp (blue), steps 100..700
BLUE_RAMP = ("#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
             "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b")

# Diverging poles and neutral midpoints
DIVERGING_LOW = {"light": "#2a78d6", "dark": "#3987e5"}
DIVERGING_HIGH = {"light": "#e34948", "dark": "#e66767"}
DIVERGING_MID = {"light": "#f0efec", "dark": "#383835"}


@dataclass(frozen=True)
class Palette:
    name: str
    is_dark: bool

    # Surfaces, from the window background up to hovered controls
    bg: str
    surface: str
    surface_2: str
    surface_3: str
    border: str
    border_strong: str

    # Text
    text: str
    text_muted: str
    text_faint: str

    # Accent (brand) and semantic colours
    accent: str
    accent_hover: str
    accent_pressed: str
    on_accent: str
    accent_soft: str
    danger: str
    danger_soft: str
    warning: str
    warning_soft: str
    info: str
    info_soft: str

    # Data colours
    series: tuple[str, ...] = field(default_factory=tuple)
    grid: str = ""
    scene_bg: str = ""
    scene_bg_2: str = ""
    scene_edge: str = ""

    def qcolor_tuple(self, hex_color: str) -> tuple[float, float, float]:
        """Hex colour -> (r, g, b) floats in 0..1, for VTK."""
        h = hex_color.lstrip("#")
        return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


DARK = Palette(
    name="dark",
    is_dark=True,
    bg="#0e1116",
    surface="#151920",
    surface_2="#1b2029",
    surface_3="#242a35",
    border="#262c37",
    border_strong="#363e4b",
    text="#e7eaf0",
    text_muted="#a0a8b6",
    text_faint="#6c7584",
    accent="#34d399",
    accent_hover="#6ee7b7",
    accent_pressed="#10b981",
    on_accent="#04241a",
    accent_soft="rgba(52, 211, 153, 0.14)",
    danger="#f87171",
    danger_soft="rgba(248, 113, 113, 0.14)",
    warning="#fbbf24",
    warning_soft="rgba(251, 191, 36, 0.14)",
    info="#60a5fa",
    info_soft="rgba(96, 165, 250, 0.14)",
    series=DARK_SERIES,
    grid="#262c37",
    scene_bg="#11151b",
    scene_bg_2="#1a2029",
    scene_edge="#5b6577",
)

LIGHT = Palette(
    name="light",
    is_dark=False,
    bg="#f5f6f8",
    surface="#ffffff",
    surface_2="#f1f3f6",
    surface_3="#e7eaef",
    border="#e1e5eb",
    border_strong="#cbd2dc",
    text="#141922",
    text_muted="#566070",
    text_faint="#8a93a2",
    accent="#059669",
    accent_hover="#047857",
    accent_pressed="#065f46",
    on_accent="#ffffff",
    accent_soft="rgba(5, 150, 105, 0.10)",
    danger="#dc2626",
    danger_soft="rgba(220, 38, 38, 0.08)",
    warning="#b45309",
    warning_soft="rgba(217, 119, 6, 0.10)",
    info="#2563eb",
    info_soft="rgba(37, 99, 235, 0.08)",
    series=LIGHT_SERIES,
    grid="#e6e9ee",
    scene_bg="#fbfcfd",
    scene_bg_2="#e9edf2",
    scene_edge="#94a0b2",
)

PALETTES = {"dark": DARK, "light": LIGHT}
