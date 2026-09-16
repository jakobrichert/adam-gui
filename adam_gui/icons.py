"""Inline SVG icon set, recoloured on the fly to match the active theme.

Glyphs follow the Feather / Lucide style (24x24 grid, 2px round strokes);
Feather is MIT licensed and Lucide is ISC licensed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from adam_gui.qt_compat import (
    QByteArray, QIcon, QObject, QPainter, QPixmap, QSize, QSvgRenderer, Qt, QWidget,
)

_ICONS: dict[str, str] = {
    "sprout": '<path d="M7 20h10"/><path d="M10 20c5.5-2.5.8-6.4 3-10"/>'
              '<path d="M9.5 9.4c1.1.8 1.8 2.2 2.3 3.7-2 .4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2 2.8-.5 4.4 0 5.5.8z"/>'
              '<path d="M14.1 6a7 7 0 0 0-1.1 4c1.9-.1 3.3-.6 4.3-1.4 1-1 1.6-2.3 1.7-4.6-2.7.1-4 1-4.9 2z"/>',
    "sliders": '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>'
               '<line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>'
               '<line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>'
               '<line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>'
               '<line x1="17" y1="16" x2="23" y2="16"/>',
    "play": '<polygon points="6 4 20 12 6 20 6 4"/>',
    "play-filled": '<polygon points="6 4 20 12 6 20 6 4" fill="COLOR"/>',
    "pause": '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "bar-chart": '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/>'
                 '<line x1="6" y1="20" x2="6" y2="14"/>',
    "box": '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>'
           '<polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
    "settings": '<circle cx="12" cy="12" r="3"/>'
                '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
            '<polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
    "folder": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "file-plus": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
                 '<polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/>'
                 '<line x1="9" y1="15" x2="15" y2="15"/>',
    "file-text": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
                 '<polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>'
                 '<line x1="16" y1="17" x2="8" y2="17"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
                '<polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
              '<polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
    "rotate-ccw": '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>',
    "camera": '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>'
              '<circle cx="12" cy="13" r="4"/>',
    "arrow-left": '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
    "arrow-right": '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
    "chevron-up": '<polyline points="18 15 12 9 6 15"/>',
    "chevron-down": '<polyline points="6 9 12 15 18 9"/>',
    "chevron-right": '<polyline points="9 18 15 12 9 6"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "dot": '<circle cx="12" cy="12" r="4.5" fill="COLOR" stroke="none"/>',
    "x": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "minus": '<line x1="5" y1="12" x2="19" y2="12"/>',
    "alert-triangle": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
                      '<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "alert-circle": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>'
                    '<line x1="12" y1="16" x2="12.01" y2="16"/>',
    "info": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/>'
            '<line x1="12" y1="8" x2="12.01" y2="8"/>',
    "check-circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "trash": '<polyline points="3 6 5 6 21 6"/>'
             '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "search": '<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="4"/>'
           '<line x1="12" y1="20" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="6.34" y2="6.34"/>'
           '<line x1="17.66" y1="17.66" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="4" y2="12"/>'
           '<line x1="20" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="6.34" y2="17.66"/>'
           '<line x1="17.66" y1="6.34" x2="19.07" y2="4.93"/>',
    "moon": '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
    "pedigree": '<circle cx="6" cy="5" r="2.5"/><circle cx="18" cy="5" r="2.5"/><circle cx="12" cy="19" r="2.5"/>'
                '<path d="M6 7.5V9a3 3 0 0 0 3 3h6a3 3 0 0 0 3-3V7.5"/><line x1="12" y1="12" x2="12" y2="16.5"/>',
    "dna": '<path d="M7 2c0 5 10 5 10 10S7 17 7 22"/><path d="M17 2c0 5-10 5-10 10s10 5 10 10"/>'
           '<line x1="8" y1="4.5" x2="16" y2="4.5"/><line x1="10" y1="8" x2="14" y2="8"/>'
           '<line x1="10" y1="16" x2="14" y2="16"/><line x1="8" y1="19.5" x2="16" y2="19.5"/>',
    "scatter": '<path d="M3 3v18h18"/><circle cx="8" cy="15" r="1.4"/><circle cx="11.5" cy="10" r="1.4"/>'
               '<circle cx="16" cy="13" r="1.4"/><circle cx="18" cy="6.5" r="1.4"/><circle cx="12.5" cy="17" r="1.4"/>',
    "landscape": '<path d="M2 20h20"/><path d="M3 20l5.5-9.5 3.5 5 3-4.5L21 20"/><circle cx="17" cy="5.5" r="1.8"/>',
    "trending-up": '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
    "activity": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>'
            '<rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
             '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "compare": '<rect x="3" y="4" width="7" height="16" rx="1.5"/><rect x="14" y="9" width="7" height="11" rx="1.5"/>',
    "dashboard": '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/>'
                 '<rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    "terminal": '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "maximize": '<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "copy": '<rect x="9" y="9" width="13" height="13" rx="2"/>'
            '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>'
           '<line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/>'
           '<line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/>'
           '<line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/>'
           '<line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>',
    "eye": '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/>'
              '<polyline points="2 12 12 17 22 12"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>'
            '<line x1="12" y1="17" x2="12.01" y2="17"/>',
    "external": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
                '<polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
}


def names() -> list[str]:
    return sorted(_ICONS)


def svg_markup(name: str, color: str, stroke_width: float = 2.0) -> str:
    body = _ICONS[name].replace("COLOR", color)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )


def pixmap(name: str, color: str, size: int = 20, scale: float = 2.0,
           stroke_width: float = 2.0) -> QPixmap:
    """Render an icon to a HiDPI-aware pixmap of ``size`` logical pixels."""
    px = max(1, int(round(size * scale)))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg_markup(name, color, stroke_width).encode()))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    pm.setDevicePixelRatio(scale)
    return pm


def icon(name: str, color: str, active_color: str | None = None,
         disabled_color: str | None = None, size: int = 20) -> QIcon:
    """Build a QIcon with separate colours for normal, checked and disabled states."""
    ic = QIcon()
    for scale in (1.0, 2.0):
        ic.addPixmap(pixmap(name, color, size, scale), QIcon.Mode.Normal, QIcon.State.Off)
        ic.addPixmap(pixmap(name, active_color or color, size, scale), QIcon.Mode.Normal, QIcon.State.On)
        ic.addPixmap(pixmap(name, active_color or color, size, scale), QIcon.Mode.Active, QIcon.State.On)
        if disabled_color:
            ic.addPixmap(pixmap(name, disabled_color, size, scale), QIcon.Mode.Disabled, QIcon.State.Off)
    return ic


def write_svg_files(theme_name: str, colors: dict[str, tuple[str, str]]) -> dict[str, str]:
    """Write recoloured SVGs to a cache dir for use in stylesheets (url(...)).

    ``colors`` maps a key to (icon name, colour). Returns key -> file path.
    """
    out_dir = Path(tempfile.gettempdir()) / "adam-gui-icons" / theme_name
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, (name, color) in colors.items():
        width = 3.0 if name in ("check",) else 2.2
        path = out_dir / f"{key}.svg"
        path.write_text(svg_markup(name, color, width), encoding="utf-8")
        paths[key] = path.as_posix()
    return paths


class _IconBinder(QObject):
    """Keeps a widget's icon in sync with the active theme.

    Parented to the widget so the theme connection dies with it.
    """

    def __init__(self, widget: QWidget, name: str, role: str, active_role: str | None, size: int):
        super().__init__(widget)
        self._widget = widget
        self._name = name
        self._role = role
        self._active_role = active_role
        self._size = size
        from adam_gui.themes import theme
        theme().changed.connect(self.refresh)
        self.refresh()

    def set_name(self, name: str):
        self._name = name
        self.refresh()

    def refresh(self, *_):
        from adam_gui.themes import theme
        p = theme().palette
        color = getattr(p, self._role)
        active = getattr(p, self._active_role) if self._active_role else None
        ic = icon(self._name, color, active, p.text_faint, self._size)
        self._widget.setIcon(ic)
        if hasattr(self._widget, "setIconSize"):
            self._widget.setIconSize(QSize(self._size, self._size))


def bind_icon(widget: QWidget, name: str, role: str = "text_muted",
              active_role: str | None = "accent", size: int = 18) -> _IconBinder:
    """Give ``widget`` (anything with setIcon) a theme-following icon."""
    existing = getattr(widget, "_adam_icon_binder", None)
    if existing is not None:
        existing._role = role
        existing._active_role = active_role
        existing._size = size
        existing.set_name(name)
        return existing
    binder = _IconBinder(widget, name, role, active_role, size)
    widget._adam_icon_binder = binder
    return binder
