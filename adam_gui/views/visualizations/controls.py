"""Per-scene control panels shown in the left column of the 3D Explorer."""

from __future__ import annotations

from adam_gui.qt_compat import (
    QCheckBox, QComboBox, QHBoxLayout, QIntValidator, QLineEdit, QSlider, Qt,
    QTimer, QVBoxLayout, QWidget, Signal,
)
from adam_gui.vtk_pipelines.pedigree_pipeline import COLOR_OPTIONS
from adam_gui.vtk_pipelines.surface_pipeline import METRICS
from adam_gui.widgets.ui import SegmentedControl, button, icon_button, label
from adam_gui.icons import bind_icon


def _field(title: str, widget: QWidget, trailing: QWidget | None = None) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)
    head = QHBoxLayout()
    head.setSpacing(6)
    cap = label(title, "muted")
    head.addWidget(cap, 1)
    if trailing is not None:
        head.addWidget(trailing)
    lay.addLayout(head)
    lay.addWidget(widget)
    box.caption = cap
    return box


def _combo(items: list[tuple[str, str]]) -> QComboBox:
    combo = QComboBox()
    for key, text in items:
        combo.addItem(text, key)
    return combo


class _Panel(QWidget):
    changed = Signal()

    def __init__(self, help_text: str, parent=None):
        super().__init__(parent)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(14)
        self._help = label(help_text, "help", wrap=True)

    def finish(self):
        self.lay.addWidget(self._help)
        self.lay.addStretch(1)

    def set_traits(self, combo: QComboBox, field: QWidget, names: list[str]):
        current = combo.currentIndex()
        combo.blockSignals(True)
        combo.clear()
        for i, n in enumerate(names):
            combo.addItem(n, i)
        combo.setCurrentIndex(current if 0 <= current < len(names) else 0)
        combo.blockSignals(False)
        field.setVisible(len(names) > 1)


class PlayButton(QWidget):
    """Play/pause toggle that ticks a timer."""

    tick = Signal()

    def __init__(self, interval_ms: int, tooltip: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.btn = icon_button("play", tooltip, checkable=True, size=16)
        lay.addWidget(self.btn)
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.tick.emit)
        self.btn.toggled.connect(self._toggled)

    def _toggled(self, on: bool):
        bind_icon(self.btn, "pause" if on else "play", size=16)
        if on:
            self.timer.start()
        else:
            self.timer.stop()

    def stop(self):
        if self.btn.isChecked():
            self.btn.setChecked(False)

    @property
    def playing(self) -> bool:
        return self.btn.isChecked()


class PedigreeControls(_Panel):
    find_requested = Signal(int)
    clear_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(
            "Each row is one generation; spheres are individuals and lines link parents to "
            "offspring. Larger spheres were selected as parents. Click an individual to trace "
            "its ancestors (blue) and descendants (orange).", parent)
        self.gens = QSlider(Qt.Orientation.Horizontal)
        self.gens.setRange(2, 15)
        self.gens.setValue(6)
        self.gens_value = label("6", "badge")
        self.gens_field = _field("Generations shown", self.gens, self.gens_value)
        self.gens.valueChanged.connect(lambda v: self.gens_value.setText(str(v)))
        self.gens.sliderReleased.connect(self.changed.emit)
        self.gens.valueChanged.connect(lambda _: None if self.gens.isSliderDown() else self.changed.emit())
        self.lay.addWidget(self.gens_field)

        self.color = _combo(list(COLOR_OPTIONS.items()))
        self.color.currentIndexChanged.connect(self.changed.emit)
        self.lay.addWidget(_field("Colour by", self.color))

        self.trait = QComboBox()
        self.trait.currentIndexChanged.connect(self.changed.emit)
        self.trait_field = _field("Trait", self.trait)
        self.lay.addWidget(self.trait_field)

        self.arrange = SegmentedControl([("ebv", "By EBV"), ("family", "By family")])
        self.arrange.changed.connect(lambda _: self.changed.emit())
        self.lay.addWidget(_field("Order within generation", self.arrange))

        self.links = _combo([("all", "All parent links"), ("selected", "Links to selected offspring"),
                             ("none", "Hide links")])
        self.links.currentIndexChanged.connect(self.changed.emit)
        self.lay.addWidget(_field("Links", self.links))

        find_row = QWidget()
        fl = QHBoxLayout(find_row)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(6)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Individual ID")
        self.find_edit.setValidator(QIntValidator(1, 2_000_000_000, self))
        self.find_edit.returnPressed.connect(self._find)
        fl.addWidget(self.find_edit, 1)
        find_btn = button("Find", icon="search")
        find_btn.clicked.connect(self._find)
        fl.addWidget(find_btn)
        self.lay.addWidget(_field("Go to individual", find_row))
        self.find_status = label("", "help", wrap=True)
        self.find_status.hide()
        self.lay.addWidget(self.find_status)
        self.finish()

    def _find(self):
        text = self.find_edit.text().strip()
        if text.isdigit():
            self.find_requested.emit(int(text))

    def set_find_status(self, text: str):
        self.find_status.setText(text)
        self.find_status.setVisible(bool(text))

    def configure(self, trait_names: list[str], is_animal: bool, max_gens: int):
        self.set_traits(self.trait, self.trait_field, trait_names)
        model = self.color.model()
        idx = self.color.findData("sex")
        item = model.item(idx) if hasattr(model, "item") else None
        if item is not None:
            item.setEnabled(is_animal)
        if not is_animal and self.color.currentData() == "sex":
            self.color.setCurrentIndex(0)
        self.gens.blockSignals(True)
        self.gens.setRange(min(2, max(1, max_gens)), max(2, min(15, max_gens)))
        self.gens.setValue(min(self.gens.value(), self.gens.maximum()))
        self.gens_value.setText(str(self.gens.value()))
        self.gens.blockSignals(False)
        self.set_find_status("")

    def options(self) -> dict:
        return dict(n_gens=self.gens.value(), color_by=self.color.currentData(),
                    trait=max(0, self.trait.currentIndex()), arrange=self.arrange.current(),
                    links=self.links.currentData())


class ChromosomeControls(_Panel):
    generation_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(
            "Capsules are chromosomes (length in cM); light bands are markers, fading as "
            "heterozygosity is lost. Spheres are QTL: size shows the allele effect and colour "
            "the frequency of the favourable allele. Press play to watch selection move them.",
            parent)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.value = label("0", "badge")
        self.play = PlayButton(170, "Animate generations")
        self.play.tick.connect(self._advance)
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)
        rl.addWidget(self.play)
        rl.addWidget(self.slider, 1)
        self.lay.addWidget(_field("Generation", row, self.value))
        self.slider.valueChanged.connect(self._on_value)
        self.note = label("", "help", wrap=True)
        self.note.hide()
        self.lay.addWidget(self.note)
        self.finish()

    def _on_value(self, v: int):
        self.value.setText(str(v))
        self.generation_changed.emit(v)

    def _advance(self):
        v = self.slider.value() + 1
        if v > self.slider.maximum():
            v = self.slider.minimum()
        self.slider.setValue(v)

    def configure(self, n_generations: int, has_qtl: bool):
        self.play.stop()
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, n_generations - 1))
        self.slider.setValue(0)
        self.value.setText("0")
        self.slider.blockSignals(False)
        self.play.setEnabled(n_generations > 1 and has_qtl)
        self.note.setText("" if has_qtl else "This run has no QTL data, so only the chromosome "
                                              "layout is shown.")
        self.note.setVisible(not has_qtl)

    def options(self) -> dict:
        return dict(generation=self.slider.value())


class PCAControls(_Panel):
    range_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(
            "Genotypes of every stored generation are projected into one shared principal-"
            "component space, so movement between generations is real genetic change. The "
            "line joins the generation centroids; press play to reveal generations in order.",
            parent)
        self.color = _combo([("generation", "Generation"), ("tbv", "True breeding value"),
                             ("selected", "Selected as parent")])
        self.color.currentIndexChanged.connect(self.changed.emit)
        self.lay.addWidget(_field("Colour by", self.color))
        self.trait = QComboBox()
        self.trait.currentIndexChanged.connect(self.changed.emit)
        self.trait_field = _field("Trait", self.trait)
        self.lay.addWidget(self.trait_field)

        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        self.gen_from = QComboBox()
        self.gen_to = QComboBox()
        rl.addWidget(self.gen_from, 1)
        rl.addWidget(label("to", "muted"))
        rl.addWidget(self.gen_to, 1)
        self.play = PlayButton(650, "Reveal generations one by one")
        self.play.tick.connect(self._advance)
        rl.addWidget(self.play)
        self.lay.addWidget(_field("Generations (from – to)", row))
        self.gen_from.currentIndexChanged.connect(self._on_range)
        self.gen_to.currentIndexChanged.connect(self._on_range)
        self.note = label("", "help", wrap=True)
        self.note.hide()
        self.lay.addWidget(self.note)
        self.finish()

    def _on_range(self, *_):
        if self.gen_from.currentIndex() > self.gen_to.currentIndex():
            sender = self.sender()
            other = self.gen_to if sender is self.gen_from else self.gen_from
            other.blockSignals(True)
            other.setCurrentIndex(sender.currentIndex())
            other.blockSignals(False)
        self.range_changed.emit()

    def _advance(self):
        n = self.gen_to.count()
        if n == 0:
            return
        i = self.gen_to.currentIndex() + 1
        if i >= n:
            i = self.gen_from.currentIndex()
        self.gen_to.setCurrentIndex(i)

    def start_play(self):
        """Begin the reveal from the first selected generation."""
        self.gen_to.setCurrentIndex(self.gen_from.currentIndex())

    def configure(self, stored_gens: list[int], trait_names: list[str]):
        self.play.stop()
        self.set_traits(self.trait, self.trait_field, trait_names)
        for combo in (self.gen_from, self.gen_to):
            combo.blockSignals(True)
            combo.clear()
            for g in stored_gens:
                combo.addItem(str(g), g)
            combo.blockSignals(False)
        self.gen_from.setCurrentIndex(0)
        self.gen_to.setCurrentIndex(max(0, len(stored_gens) - 1))
        ok = len(stored_gens) > 0
        self.play.setEnabled(len(stored_gens) > 1)
        self.note.setText("" if ok else "This run has no genotype data to project.")
        self.note.setVisible(not ok)

    def options(self) -> dict:
        return dict(color_by=self.color.currentData(), trait=max(0, self.trait.currentIndex()),
                    gen_from=self.gen_from.currentData(), gen_to=self.gen_to.currentData())


class LandscapeControls(_Panel):
    def __init__(self, parent=None):
        super().__init__(
            "The surface shows how the distribution of the chosen value shifts and narrows "
            "across generations: height is density, the green line follows the generation mean.",
            parent)
        self.metric = _combo(list(METRICS.items()))
        self.metric.currentIndexChanged.connect(self.changed.emit)
        self.lay.addWidget(_field("Value", self.metric))
        self.trait = QComboBox()
        self.trait.currentIndexChanged.connect(self.changed.emit)
        self.trait_field = _field("Trait", self.trait)
        self.lay.addWidget(self.trait_field)
        self.normalise = QCheckBox("Normalise each generation")
        self.normalise.setChecked(True)
        self.normalise.setToolTip("Scale each generation to its own peak. Off: heights are comparable across generations")
        self.normalise.toggled.connect(self.changed.emit)
        self.lay.addWidget(self.normalise)
        self.contours = QCheckBox("Contour lines")
        self.contours.setChecked(True)
        self.contours.toggled.connect(self.changed.emit)
        self.lay.addWidget(self.contours)
        self.finish()

    def configure(self, trait_names: list[str]):
        self.set_traits(self.trait, self.trait_field, trait_names)

    def options(self) -> dict:
        return dict(metric=self.metric.currentData(), trait=max(0, self.trait.currentIndex()),
                    contours=self.contours.isChecked(), normalise=self.normalise.isChecked())
