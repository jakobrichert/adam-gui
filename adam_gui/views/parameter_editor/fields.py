"""Form field factories for the parameter editor.

Spin boxes and combo boxes ignore the mouse wheel unless focused, so
scrolling the long form never changes a value by accident.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Iterable

from adam_gui.qt_compat import (
    QAbstractSpinBox, QComboBox, QDoubleSpinBox, QSpinBox, QStandardItemModel,
    QValidator, Qt,
)


class _WheelGuard:
    def wheelEvent(self, event):  # noqa: N802
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class SpinBox(_WheelGuard, QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGroupSeparatorShown(True)
        self.setAccelerated(True)


class DoubleSpinBox(_WheelGuard, QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccelerated(True)


class ComboBox(_WheelGuard, QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


class SciSpinBox(DoubleSpinBox):
    """Double spin box that shows and accepts scientific notation (2.5e-05)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDecimals(12)
        self.setStepType(QAbstractSpinBox.StepType.DefaultStepType)

    def textFromValue(self, value: float) -> str:  # noqa: N802
        if value == 0:
            return "0"
        return f"{value:.3g}" if 1e-3 <= abs(value) < 1e3 else f"{value:.3e}".replace("e-0", "e-")

    def valueFromText(self, text: str) -> float:  # noqa: N802
        try:
            return float(text.strip())
        except ValueError:
            return self.value()

    def validate(self, text: str, pos: int):
        stripped = text.strip()
        if stripped in ("", "-", ".", "e", "E") or stripped.lower().endswith(("e", "e-", "e+")):
            return QValidator.State.Intermediate, text, pos
        try:
            v = float(stripped)
        except ValueError:
            return QValidator.State.Invalid, text, pos
        if self.minimum() <= v <= self.maximum():
            return QValidator.State.Acceptable, text, pos
        return QValidator.State.Intermediate, text, pos

    def stepBy(self, steps: int):  # noqa: N802
        v = self.value()
        if v <= 0:
            v = 1e-6
        exponent = math.floor(math.log10(v))
        self.setValue(max(self.minimum(), min(self.maximum(), v + steps * 10 ** exponent)))


def int_spin(lo: int, hi: int, value: int, step: int = 1, suffix: str = "",
             special: str | None = None) -> SpinBox:
    w = SpinBox()
    w.setRange(lo, hi)
    w.setSingleStep(step)
    w.setValue(value)
    if suffix:
        w.setSuffix(suffix)
    if special:
        w.setSpecialValueText(special)
    return w


def float_spin(lo: float, hi: float, value: float, decimals: int = 2,
               step: float = 0.1, suffix: str = "") -> DoubleSpinBox:
    w = DoubleSpinBox()
    w.setDecimals(decimals)
    w.setRange(lo, hi)
    w.setSingleStep(step)
    w.setValue(value)
    if suffix:
        w.setSuffix(suffix)
    return w


def percent_spin(fraction: float, lo: float = 0.5, hi: float = 100.0) -> DoubleSpinBox:
    """Edits a 0..1 fraction as a percentage; read with ``value() / 100``."""
    w = float_spin(lo, hi, fraction * 100.0, decimals=1, step=5.0, suffix=" %")
    return w


def pretty_enum(member: Enum) -> str:
    return member.name.replace("_", " ").capitalize()


def enum_combo(members: Iterable[Enum], labels: dict | None = None) -> ComboBox:
    w = ComboBox()
    for m in members:
        w.addItem((labels or {}).get(m, pretty_enum(m)), m)
    return w


def combo_value(combo: QComboBox):
    return combo.currentData()


def set_combo_value(combo: QComboBox, value) -> None:
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return


def set_item_enabled(combo: QComboBox, value, enabled: bool) -> None:
    model = combo.model()
    if not isinstance(model, QStandardItemModel):
        return
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            item = model.item(i)
            if item is not None:
                item.setEnabled(enabled)
