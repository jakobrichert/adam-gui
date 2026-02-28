"""Dual-handle range slider widget."""

from adam_gui.qt_compat import (
    QWidget, QHBoxLayout, QSlider, QLabel, Qt, Signal,
)


class RangeSlider(QWidget):
    """A dual-value range selector using two synced sliders."""

    range_changed = Signal(int, int)

    def __init__(self, minimum: int = 0, maximum: int = 100, parent=None):
        super().__init__(parent)
        self._min = minimum
        self._max = maximum
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.low_label = QLabel(str(self._min))
        self.low_label.setMinimumWidth(30)
        layout.addWidget(self.low_label)

        self.low_slider = QSlider(Qt.Orientation.Horizontal)
        self.low_slider.setRange(self._min, self._max)
        self.low_slider.setValue(self._min)
        self.low_slider.valueChanged.connect(self._on_low_changed)
        layout.addWidget(self.low_slider, 1)

        self.dash = QLabel("-")
        layout.addWidget(self.dash)

        self.high_slider = QSlider(Qt.Orientation.Horizontal)
        self.high_slider.setRange(self._min, self._max)
        self.high_slider.setValue(self._max)
        self.high_slider.valueChanged.connect(self._on_high_changed)
        layout.addWidget(self.high_slider, 1)

        self.high_label = QLabel(str(self._max))
        self.high_label.setMinimumWidth(30)
        layout.addWidget(self.high_label)

    def _on_low_changed(self, value: int):
        if value > self.high_slider.value():
            self.low_slider.setValue(self.high_slider.value())
            return
        self.low_label.setText(str(value))
        self.range_changed.emit(self.low_slider.value(), self.high_slider.value())

    def _on_high_changed(self, value: int):
        if value < self.low_slider.value():
            self.high_slider.setValue(self.low_slider.value())
            return
        self.high_label.setText(str(value))
        self.range_changed.emit(self.low_slider.value(), self.high_slider.value())

    def set_range(self, minimum: int, maximum: int):
        self._min = minimum
        self._max = maximum
        self.low_slider.setRange(minimum, maximum)
        self.high_slider.setRange(minimum, maximum)
        self.low_slider.setValue(minimum)
        self.high_slider.setValue(maximum)
        self.low_label.setText(str(minimum))
        self.high_label.setText(str(maximum))

    def values(self) -> tuple[int, int]:
        return self.low_slider.value(), self.high_slider.value()
