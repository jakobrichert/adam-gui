"""Qt stylesheet generated from a Palette.

Widgets opt into styles through object names (``Card``, ``Sidebar``) and
dynamic properties (``variant="primary"``, ``role="title"``) instead of inline
stylesheets, so nothing cascades into child widgets by accident.
"""

from __future__ import annotations

from string import Template

from adam_gui.themes.palette import Palette

_QSS = Template(r"""
QMainWindow, QDialog, QWidget#Page, QStackedWidget#PageStack {
    background-color: $bg;
}
QWidget {
    color: $text;
    font-size: 13px;
}
QWidget:disabled { color: $text_faint; }

/* ---------- Sidebar ---------- */
QWidget#Sidebar {
    background-color: $surface;
    border-right: 1px solid $border;
}
QLabel#BrandMark {
    color: $on_accent;
    background-color: $accent;
    border-radius: 10px;
    font-weight: 700;
    font-size: 15px;
}
QToolButton#NavButton {
    background: transparent;
    border: none;
    border-radius: 10px;
    color: $text_muted;
    padding: 8px 2px 6px 2px;
    font-size: 11px;
    font-weight: 500;
}
QToolButton#NavButton:hover {
    background-color: $surface_2;
    color: $text;
}
QToolButton#NavButton:checked {
    background-color: $accent_soft;
    color: $accent;
    font-weight: 600;
}

/* ---------- Typography ---------- */
QLabel { background: transparent; }
QLabel[role="title"] { font-size: 22px; font-weight: 700; color: $text; }
QLabel[role="subtitle"] { font-size: 13px; color: $text_muted; }
QLabel[role="section"] { font-size: 15px; font-weight: 650; color: $text; }
QLabel[role="overline"] {
    font-size: 11px; font-weight: 600; color: $text_faint;
    letter-spacing: 0.6px;
}
QLabel[role="muted"] { color: $text_muted; }
QLabel[role="faint"] { color: $text_faint; font-size: 12px; }
QLabel[role="kpi"] { font-size: 26px; font-weight: 700; color: $text; }
QLabel[role="kpi-delta-up"] { color: $accent; font-weight: 600; font-size: 12px; }
QLabel[role="kpi-delta-down"] { color: $danger; font-weight: 600; font-size: 12px; }
QLabel[role="kpi-delta-flat"] { color: $text_muted; font-size: 12px; }
QLabel[role="empty-title"] { font-size: 17px; font-weight: 650; color: $text; }
QLabel[role="badge"] {
    background-color: $surface_3; color: $text_muted;
    border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600;
}
QLabel[role="badge-accent"] {
    background-color: $accent_soft; color: $accent;
    border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600;
}
QLabel[role="badge-warning"] {
    background-color: $warning_soft; color: $warning;
    border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600;
}
QLabel[role="badge-danger"] {
    background-color: $danger_soft; color: $danger;
    border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600;
}
QLabel[role="badge-info"] {
    background-color: $info_soft; color: $info;
    border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600;
}
QLabel[role="help"] { color: $text_faint; font-size: 12px; }
QLabel[role="field-error"] { color: $danger; font-size: 12px; }

/* ---------- Cards and panels ---------- */
QFrame#Card {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 12px;
}
QFrame#Card[interactive="true"]:hover {
    border-color: $border_strong;
    background-color: $surface_2;
}
QFrame#Inset {
    background-color: $surface_2;
    border: 1px solid $border;
    border-radius: 10px;
}
QFrame#Banner {
    background-color: $info_soft;
    border: 1px solid $border;
    border-radius: 10px;
}
QFrame#Banner[tone="warning"] { background-color: $warning_soft; }
QFrame#Banner[tone="danger"] { background-color: $danger_soft; }
QFrame#Banner[tone="accent"] { background-color: $accent_soft; }
QFrame#Divider { background-color: $border; max-height: 1px; min-height: 1px; border: none; }
QFrame#Overlay {
    background-color: $overlay_bg;
    border: 1px solid $border;
    border-radius: 10px;
}
QFrame#Toast {
    background-color: $surface_3;
    border: 1px solid $border_strong;
    border-radius: 10px;
}

/* ---------- Buttons ---------- */
QPushButton {
    background-color: $surface_2;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 8px;
    padding: 6px 14px;
    min-height: 20px;
    font-weight: 500;
}
QPushButton:hover { background-color: $surface_3; }
QPushButton:pressed { background-color: $border_strong; }
QPushButton:disabled { color: $text_faint; background-color: $surface; border-color: $border; }
QPushButton:focus { border-color: $accent; }
QPushButton[variant="primary"] {
    background-color: $accent; color: $on_accent; border: 1px solid $accent; font-weight: 600;
}
QPushButton[variant="primary"]:hover { background-color: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:pressed { background-color: $accent_pressed; }
QPushButton[variant="primary"]:disabled {
    background-color: $surface_3; color: $text_faint; border-color: $surface_3;
}
QPushButton[variant="danger"] {
    background-color: transparent; color: $danger; border: 1px solid $danger;
}
QPushButton[variant="danger"]:hover { background-color: $danger_soft; }
QPushButton[variant="danger"]:disabled { color: $text_faint; border-color: $border; }
QPushButton[variant="ghost"] {
    background-color: transparent; border: 1px solid transparent; color: $text_muted;
}
QPushButton[variant="ghost"]:hover { background-color: $surface_2; color: $text; }
QPushButton[variant="ghost"]:checked { background-color: $accent_soft; color: $accent; }
QPushButton[variant="link"] {
    background: transparent; border: none; color: $accent; padding: 0; font-weight: 600;
}
QPushButton[variant="link"]:hover { color: $accent_hover; text-decoration: underline; }
QPushButton[variant="large"] { padding: 10px 20px; font-size: 14px; }

QPushButton[segment="true"] {
    background-color: transparent; border: none; border-radius: 6px;
    padding: 5px 12px; color: $text_muted;
}
QPushButton[segment="true"]:hover { color: $text; background-color: $surface_3; }
QPushButton[segment="true"]:checked {
    background-color: $surface; color: $text; font-weight: 600;
}
QFrame#Segmented {
    background-color: $surface_2; border: 1px solid $border; border-radius: 8px;
}

QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px;
    color: $text_muted;
}
QToolButton:hover { background-color: $surface_3; color: $text; }
QToolButton:checked { background-color: $accent_soft; color: $accent; }
QToolButton:disabled { color: $text_faint; }
QToolButton::menu-indicator { image: none; }

/* ---------- Inputs ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
    background-color: $surface_2;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 8px;
    padding: 5px 8px;
    selection-background-color: $accent;
    selection-color: $on_accent;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { min-height: 20px; }
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { border-color: $text_faint; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus { border-color: $accent; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    background-color: $surface; color: $text_faint; border-color: $border;
}
QLineEdit[invalid="true"], QSpinBox[invalid="true"], QDoubleSpinBox[invalid="true"] { border-color: $danger; }
QPlainTextEdit#Log {
    font-size: 12px;
    background-color: $surface;
    border-radius: 10px;
    padding: 10px;
}

QSpinBox, QDoubleSpinBox { padding-right: 22px; }
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border; subcontrol-position: top right;
    width: 20px; border: none; border-left: 1px solid $border;
    border-top-right-radius: 8px; background: transparent;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 20px; border: none; border-left: 1px solid $border;
    border-bottom-right-radius: 8px; background: transparent;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover { background-color: $surface_3; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url("$icon_chevron_up"); width: 10px; height: 10px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url("$icon_chevron_down"); width: 10px; height: 10px; }

QComboBox { padding-right: 26px; }
QComboBox::drop-down {
    subcontrol-origin: padding; subcontrol-position: center right;
    width: 24px; border: none; background: transparent;
}
QComboBox::down-arrow { image: url("$icon_chevron_down"); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background-color: $surface;
    border: 1px solid $border_strong;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: $accent_soft;
    selection-color: $text;
}
QComboBox QAbstractItemView::item { min-height: 26px; padding: 2px 8px; border-radius: 6px; }

QCheckBox, QRadioButton { spacing: 8px; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px; height: 16px;
    border: 1px solid $border_strong;
    background-color: $surface_2;
}
QCheckBox::indicator { border-radius: 5px; }
QRadioButton::indicator { border-radius: 9px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked {
    background-color: $accent; border-color: $accent; image: url("$icon_check");
}
QRadioButton::indicator:checked {
    background-color: $accent; border-color: $accent; image: url("$icon_dot");
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { background-color: $surface; border-color: $border; }

/* ---------- Sliders & progress ---------- */
QSlider::groove:horizontal { height: 4px; background: $surface_3; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 16px; height: 16px; margin: -6px 0;
    background: $surface; border: 2px solid $accent; border-radius: 8px;
}
QSlider::handle:horizontal:hover { background: $accent_soft; }
QSlider::groove:horizontal:disabled { background: $surface_2; }
QSlider::sub-page:horizontal:disabled { background: $border_strong; }
QSlider::handle:horizontal:disabled { border-color: $border_strong; }

QProgressBar {
    background-color: $surface_3; border: none; border-radius: 4px;
    max-height: 8px; min-height: 8px; text-align: center; color: transparent;
}
QProgressBar::chunk { background-color: $accent; border-radius: 4px; }

/* ---------- Tabs ---------- */
QTabWidget::pane { border: none; border-top: 1px solid $border; top: -1px; }
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab {
    background: transparent; color: $text_muted;
    padding: 8px 14px; margin-right: 4px;
    border: none; border-bottom: 2px solid transparent;
    font-weight: 500;
}
QTabBar::tab:hover { color: $text; }
QTabBar::tab:selected { color: $text; border-bottom: 2px solid $accent; font-weight: 600; }

/* ---------- Lists / tables / trees ---------- */
QListWidget, QTreeWidget, QTreeView, QListView {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 4px;
    outline: none;
}
QListWidget::item, QListView::item { padding: 6px 8px; border-radius: 6px; }
QListWidget::item:hover, QListView::item:hover { background-color: $surface_2; }
QListWidget::item:selected, QListView::item:selected { background-color: $accent_soft; color: $text; }
QTreeView::item { padding: 3px 4px; }
QTreeView::item:selected { background-color: $accent_soft; color: $text; }
QListView::indicator, QTreeView::indicator, QTableView::indicator {
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid $border_strong; background-color: $surface_2;
}
QListView::indicator:hover, QTreeView::indicator:hover, QTableView::indicator:hover { border-color: $accent; }
QListView::indicator:checked, QTreeView::indicator:checked, QTableView::indicator:checked {
    background-color: $accent; border-color: $accent; image: url("$icon_check");
}
QListWidget#SubNav {
    background: transparent; border: none; padding: 0;
}
QListWidget#SubNav::item { padding: 8px 10px; margin: 1px 0; border-radius: 8px; color: $text_muted; }
QListWidget#SubNav::item:hover { background-color: $surface_2; color: $text; }
QListWidget#SubNav::item:selected { background-color: $accent_soft; color: $accent; font-weight: 600; }

QTableView, QTableWidget {
    background-color: $surface;
    alternate-background-color: $table_alt;
    border: 1px solid $border;
    border-radius: 10px;
    gridline-color: transparent;
    selection-background-color: $accent_soft;
    selection-color: $text;
    outline: none;
}
QTableView::item { padding: 0 8px; border: none; }
QHeaderView { background-color: transparent; border: none; }
QHeaderView::section {
    background-color: $surface;
    color: $text_muted;
    border: none;
    border-bottom: 1px solid $border;
    padding: 7px 8px;
    font-weight: 600;
    font-size: 12px;
}
QHeaderView::section:hover { color: $text; }
QTableCornerButton::section { background-color: $surface; border: none; }
QHeaderView::down-arrow { image: url("$icon_chevron_down"); width: 10px; height: 10px; }
QHeaderView::up-arrow { image: url("$icon_chevron_up"); width: 10px; height: 10px; }

/* ---------- Scrollbars ---------- */
QScrollArea, QScrollArea > QWidget > QWidget#ScrollBody { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border_strong; border-radius: 3px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: $text_faint; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border_strong; border-radius: 3px; min-width: 32px; }
QScrollBar::handle:horizontal:hover { background: $text_faint; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---------- Menus, tooltips, status bar ---------- */
QMenuBar { background-color: $surface; border-bottom: 1px solid $border; }
QMenuBar::item { padding: 5px 10px; border-radius: 6px; background: transparent; }
QMenuBar::item:selected { background-color: $surface_3; }
QMenu {
    background-color: $surface; border: 1px solid $border_strong;
    border-radius: 10px; padding: 5px;
}
QMenu::item { padding: 6px 26px 6px 12px; border-radius: 6px; }
QMenu::item:selected { background-color: $accent_soft; color: $text; }
QMenu::item:disabled { color: $text_faint; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }
QToolTip {
    background-color: $surface_3; color: $text;
    border: 1px solid $border_strong; border-radius: 6px; padding: 5px 8px;
}
QStatusBar {
    background-color: $surface; color: $text_muted;
    border-top: 1px solid $border; min-height: 26px;
}
QStatusBar::item { border: none; }
QStatusBar QLabel { color: $text_muted; padding: 0 6px; font-size: 12px; }

QSplitter::handle { background-color: transparent; }
QSplitter::handle:horizontal { width: 6px; }
QSplitter::handle:vertical { height: 6px; }
QSplitter::handle:hover { background-color: $accent_soft; }

QMessageBox QLabel { color: $text; }
""")


def build_stylesheet(p: Palette, icon_paths: dict[str, str]) -> str:
    overlay_bg = "rgba(21, 25, 32, 0.88)" if p.is_dark else "rgba(255, 255, 255, 0.92)"
    table_alt = "#181c24" if p.is_dark else "#fafbfc"
    values = {k: v for k, v in vars(p).items() if isinstance(v, str)}
    values.update(overlay_bg=overlay_bg, table_alt=table_alt)
    values.update({f"icon_{k}": v for k, v in icon_paths.items()})
    return _QSS.substitute(values)
