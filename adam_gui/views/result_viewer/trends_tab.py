"""Trends tab: one chart at a time, picked from a side list."""

from __future__ import annotations

from adam_gui.icons import icon
from adam_gui.models.results import SimulationResults
from adam_gui.qt_compat import (
    QCheckBox, QComboBox, QHBoxLayout, QListWidget, QListWidgetItem, QSize, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
)
from adam_gui.themes import palette, theme
from adam_gui.views.charts import (
    draw_accuracy, draw_gain, draw_inbreeding, draw_qtl_frequencies, draw_variance,
)
from adam_gui.views.result_viewer.data import RunData, run_data
from adam_gui.widgets import ui
from adam_gui.widgets.chart_widget import ChartWidget


class _ChartPage(QWidget):
    """Card with a title, an option row and a chart."""

    def __init__(self, title: str, subtitle: str, save_name: str):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.card = ui.Card(title, subtitle)
        self.options = QHBoxLayout()
        self.options.setSpacing(14)
        self.card.header_actions.addLayout(self.options)
        self.chart = ChartWidget(min_height=320)
        self.chart.save_name = save_name
        self.card.add(self.chart, 1)
        lay.addWidget(self.card)


class TrendsTab(QWidget):
    ITEMS = [
        ("gain", "Genetic gain", "trending-up"),
        ("variance", "Genetic variance", "bar-chart"),
        ("inbreeding", "Inbreeding", "pedigree"),
        ("accuracy", "Selection accuracy", "target"),
        ("qtl", "QTL allele frequencies", "dna"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: RunData | None = None
        self._stale: set[str] = set()
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 16, 0, 0)
        root.setSpacing(16)

        side = QVBoxLayout()
        side.setSpacing(10)
        side.addWidget(ui.label("CHARTS", "overline"))
        self.nav = QListWidget()
        self.nav.setObjectName("SubNav")
        self.nav.setIconSize(QSize(16, 16))
        self.nav.setFixedWidth(210)
        for key, text, _icon in self.ITEMS:
            item = QListWidgetItem(text)
            item.setData(256, key)
            self.nav.addItem(item)
        self.nav.setSpacing(1)
        side.addWidget(self.nav, 1)

        self.trait_box = QWidget()
        tb = QVBoxLayout(self.trait_box)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(6)
        tb.addWidget(ui.label("TRAIT", "overline"))
        self.trait_combo = QComboBox()
        self.trait_combo.currentIndexChanged.connect(self._redraw_current)
        tb.addWidget(self.trait_combo)
        side.addWidget(self.trait_box)
        self.trait_box.setVisible(False)
        root.addLayout(side)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # Genetic gain
        self.p_gain = _ChartPage("Genetic gain", "Population mean breeding value per generation", "genetic-gain")
        self.cb_band = QCheckBox("±1 SD band")
        self.cb_band.setChecked(True)
        self.cb_ebv = QCheckBox("Estimated (EBV)")
        self.cb_pheno = QCheckBox("Phenotype")
        for cb in (self.cb_band, self.cb_ebv, self.cb_pheno):
            cb.toggled.connect(self._redraw_current)
            self.p_gain.options.addWidget(cb)

        # Variance
        self.p_var = _ChartPage("Genetic variance", "Variance of true breeding values", "genetic-variance")
        self.cb_components = QCheckBox("Between / within families")
        self.cb_components.toggled.connect(self._redraw_current)
        self.p_var.options.addWidget(self.cb_components)

        # Inbreeding
        self.p_f = _ChartPage("Inbreeding", "Mean inbreeding coefficient per generation", "inbreeding")
        self.cb_genomic = QCheckBox("Genomic F")
        self.cb_genomic.setChecked(True)
        self.cb_genomic.toggled.connect(self._redraw_current)
        self.p_f.options.addWidget(self.cb_genomic)

        # Accuracy
        self.p_acc = _ChartPage("Selection accuracy", "Correlation between true and estimated breeding values",
                                "selection-accuracy")

        # QTL
        self.p_qtl = _ChartPage("QTL allele frequencies",
                                "Frequency of the favourable allele; colour shows effect size", "qtl-frequencies")
        self.p_qtl.options.addWidget(ui.label("Show top", "muted"))
        self.spin_top = QSpinBox()
        self.spin_top.setRange(3, 60)
        self.spin_top.setValue(12)
        self.spin_top.setSuffix(" QTL")
        self.spin_top.setToolTip("Number of QTL with the largest absolute effect to draw")
        self.spin_top.valueChanged.connect(self._redraw_current)
        self.p_qtl.options.addWidget(self.spin_top)

        self.pages = {"gain": self.p_gain, "variance": self.p_var, "inbreeding": self.p_f,
                      "accuracy": self.p_acc, "qtl": self.p_qtl}
        for key, _t, _i in self.ITEMS:
            self.stack.addWidget(self.pages[key])

        self.nav.currentRowChanged.connect(self._on_nav)
        self._bind_icons()
        self.nav.setCurrentRow(0)

    def _bind_icons(self):
        theme().changed.connect(self._refresh_icons)
        self._refresh_icons()

    def _refresh_icons(self, *_):
        p = palette()
        for row, (_k, _t, name) in enumerate(self.ITEMS):
            self.nav.item(row).setIcon(icon(name, p.text_muted, p.accent, p.text_faint, 16))

    # ------------------------------------------------------------ public
    def current_key(self) -> str:
        item = self.nav.currentItem()
        return item.data(256) if item else "gain"

    def current_chart(self) -> ChartWidget:
        return self.pages[self.current_key()].chart

    def select(self, key: str):
        for row, (k, _t, _i) in enumerate(self.ITEMS):
            if k == key:
                self.nav.setCurrentRow(row)

    def set_run(self, run: SimulationResults | None):
        if run is None:
            return
        self._data = run_data(run)
        d = self._data
        self.trait_combo.blockSignals(True)
        prev = self.trait_combo.currentIndex()
        self.trait_combo.clear()
        self.trait_combo.addItems(d.trait_names)
        self.trait_combo.setCurrentIndex(prev if 0 <= prev < d.n_traits else 0)
        self.trait_combo.blockSignals(False)
        self.trait_box.setVisible(d.n_traits > 1)
        has_qtl = any(q.allele_frequencies for q in run.qtl_info)
        qtl_item = self.nav.item(4)
        qtl_item.setToolTip("" if has_qtl else "This run has no QTL allele frequency data")
        has_components = d.has_series("variance_between_family")
        self.cb_components.setEnabled(has_components)
        has_ebv = d.has_series("mean_ebv")
        self.cb_ebv.setEnabled(has_ebv)
        self.cb_pheno.setEnabled(d.has_series("mean_phenotype"))
        self._stale = set(self.pages)
        self._redraw_current()

    # ------------------------------------------------------------ drawing
    def _on_nav(self, row: int):
        self.stack.setCurrentIndex(row)
        key = self.current_key()
        if self._data is not None and key in self._stale:
            self._redraw_current()
        self.trait_box.setEnabled(key in ("gain", "variance", "accuracy"))

    def _redraw_current(self, *_):
        d = self._data
        if d is None:
            return
        key = self.current_key()
        trait = max(0, self.trait_combo.currentIndex())
        page = self.pages[key]
        if key == "gain":
            band, ebv, ph = self.cb_band.isChecked(), self.cb_ebv.isChecked(), self.cb_pheno.isChecked()
            page.chart.set_renderer(lambda c: draw_gain(c, d, trait, ebv, ph, band))
        elif key == "variance":
            comp = self.cb_components.isChecked()
            page.chart.set_renderer(lambda c: draw_variance(c, d, trait, comp))
        elif key == "inbreeding":
            genomic = self.cb_genomic.isChecked()
            page.chart.set_renderer(lambda c: draw_inbreeding(c, d, genomic))
        elif key == "accuracy":
            page.chart.set_renderer(lambda c: draw_accuracy(c, d, trait))
        elif key == "qtl":
            top = self.spin_top.value()
            page.chart.set_renderer(lambda c: draw_qtl_frequencies(c, d, top), legend=False)
        self._stale.discard(key)
