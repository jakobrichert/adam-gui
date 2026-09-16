"""UI tests for the Results page (headless)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import csv  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from adam_gui.qt_compat import QApplication, Qt  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    from adam_gui.themes import theme
    theme().apply("dark")
    yield app


def _pump(app, n=3):
    for _ in range(n):
        app.processEvents()


@pytest.fixture(scope="module")
def runs():
    from adam_gui.models.enums import OrganismType, SelectionStrategy
    from adam_gui.models.parameters import SimulationParameters, TraitSpec
    from adam_gui.services.demo_data import DemoDataGenerator

    small = dict(n_cycles=2, generations_per_cycle=3)

    p1 = SimulationParameters(name="Plant run")
    p1.breeding.n_cycles, p1.breeding.generations_per_cycle = small.values()
    p1.founder.n_paternal = p1.founder.n_maternal = 30
    r1 = DemoDataGenerator(seed=1).generate(p1)

    p2 = SimulationParameters(name="Animal run")
    p2.organism_type = OrganismType.ANIMAL
    p2.selection.strategy = SelectionStrategy.GBLUP
    p2.traits = [TraitSpec(name="Yield"), TraitSpec(name="Health", heritability=0.1)]
    p2.breeding.n_cycles, p2.breeding.generations_per_cycle = small.values()
    p2.founder.n_paternal = p2.founder.n_maternal = 30
    r2 = DemoDataGenerator(seed=2).generate(p2)
    return r1, r2


@pytest.fixture
def view(qapp):
    from adam_gui.session import Session
    from adam_gui.views.result_viewer import ResultViewerView

    session = Session()
    v = ResultViewerView(session)
    v.resize(1300, 850)
    v.show()
    _pump(qapp)
    yield v, session
    v.close()
    v.deleteLater()
    _pump(qapp)


def test_empty_state(view):
    v, _session = view
    assert v.body.currentIndex() == 0
    assert not v.export_btn.isEnabled()
    assert not v.remove_btn.isEnabled()


def test_empty_state_buttons_emit(view):
    v, _session = view
    got = []
    v.request_demo_run.connect(lambda: got.append("demo"))
    v.request_navigate.connect(got.append)
    buttons = [b for b in v.empty.findChildren(type(v.export_btn))]
    for b in buttons:
        b.click()
    assert "demo" in got and "parameters" in got


def test_load_run_and_visit_all_tabs(qapp, view, runs):
    from adam_gui.views.result_viewer.viewer_view import TABS

    v, session = view
    session.add_run(runs[0])
    _pump(qapp)
    assert v.body.currentIndex() == 1
    assert "generations" in v.header.subtitle.text()
    for i, (key, _t, _i) in enumerate(TABS):
        v.tabs.setCurrentIndex(i)
        _pump(qapp)
        assert v.current_key() == key
    # Every run-dependent tab has been refreshed once visited
    assert v._stale == set()
    # Trends sub-charts all render
    for key, _t, _i in v.trends_tab.ITEMS:
        v.select_tab("trends")
        v.trends_tab.select(key)
        _pump(qapp)
        assert v.trends_tab.current_chart().figure.axes
    # Genotype views all render
    v.select_tab("genotypes")
    for key in ("heatmap", "afs", "maf", "change"):
        v.genotype_tab.view.set_current(key, emit=True)
        _pump(qapp)
        assert v.genotype_tab.stack.currentIndex() == 0


def test_lazy_refresh_on_run_switch(qapp, view, runs):
    v, session = view
    session.add_run(runs[0])
    session.add_run(runs[1])
    _pump(qapp)
    v.select_tab("overview")
    session.set_current(runs[0].run_id)
    _pump(qapp)
    # Only the visible tab was refreshed
    assert "overview" not in v._stale
    assert "individuals" in v._stale


def test_individuals_filter_and_sort(qapp, view, runs):
    v, session = view
    run = runs[1]  # animal, two traits
    session.add_run(run)
    v.select_tab("individuals")
    _pump(qapp)
    tab = v.individuals_tab
    n = len(run.individuals)
    assert tab.table.row_count() == n

    # Generation filter
    gen1 = tab.gen_combo.findData(1)
    tab.gen_combo.setCurrentIndex(gen1)
    expected = sum(1 for i in run.individuals if i.generation == 1)
    assert tab.table.row_count() == expected

    # Selected filter (combined with generation)
    tab.filter.set_current("selected", emit=True)
    expected = sum(1 for i in run.individuals if i.generation == 1 and i.selected)
    assert tab.table.row_count() == expected

    # Sex filters exist for animal runs
    tab.filter.set_current("F", emit=True)
    expected = sum(1 for i in run.individuals if i.generation == 1 and i.sex == "F")
    assert tab.table.row_count() == expected

    # Reset and search by ID
    tab.gen_combo.setCurrentIndex(0)
    tab.filter.set_current("all", emit=True)
    target = run.individuals[5].individual_id
    tab.search.setText(str(target))
    tab._apply_filter()
    ids = [int(tab.table.model.columns[0].values[r]) for r in tab.table.model.visible_rows()]
    assert target in ids and all(str(target) in str(i) for i in ids)
    tab.search.clear()
    tab._apply_filter()

    # Numeric sort on TBV (descending)
    model = tab.table.model
    col = next(k for k, c in enumerate(model.columns) if c.key == "tbv:0")
    model.sort(col, Qt.SortOrder.DescendingOrder)
    vals = [model.columns[col].values[r] for r in model.visible_rows()]
    assert vals == sorted(vals, reverse=True)
    # Both traits have columns
    keys = {c.key for c in model.columns}
    assert {"tbv:0", "tbv:1", "sex"} <= keys


def test_plant_run_hides_sex_filters(qapp, view, runs):
    v, session = view
    session.add_run(runs[0])
    v.select_tab("individuals")
    _pump(qapp)
    tab = v.individuals_tab
    assert not tab.filter._group.button(2).isVisibleTo(tab)
    assert "sex" not in {c.key for c in tab.table.model.columns}


def test_individuals_export(qapp, view, runs, tmp_path):
    v, session = view
    session.add_run(runs[0])
    v.select_tab("individuals")
    _pump(qapp)
    path = tmp_path / "rows.csv"
    v.individuals_tab.table.export_csv(str(path))
    rows = list(csv.reader(path.open()))
    assert rows[0][0] == "ID"
    assert len(rows) == len(runs[0].individuals) + 1


def test_pedigree_lookup(qapp, view, runs):
    v, session = view
    run = runs[0]
    session.add_run(run)
    v.select_tab("pedigree")
    _pump(qapp)
    tab = v.pedigree_tab
    last = max(i.generation for i in run.individuals)
    child = next(i for i in run.individuals if i.generation == last)
    tab.search.setText(str(child.individual_id))
    tab._search()
    root = tab.tree.topLevelItem(0)
    assert root.data(0, Qt.ItemDataRole.UserRole) == child.individual_id
    parent_ids = {root.child(k).data(0, Qt.ItemDataRole.UserRole) for k in range(root.childCount())}
    assert child.sire_id in parent_ids and child.dam_id in parent_ids

    # Unknown ID shows an inline error and keeps the focus
    tab.search.setText("999999999")
    tab._search()
    assert tab.search_error.isVisibleTo(tab)
    assert tab.tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole) == child.individual_id

    # A founder has descendants
    founder = next(i for i in run.individuals if i.generation == 0 and i.selected)
    tab.focus(founder.individual_id)
    from adam_gui.views.result_viewer.data import run_data
    counts = run_data(run).descendants_by_generation(founder.individual_id)
    assert counts and min(counts) == 1


def test_individual_double_click_opens_pedigree(qapp, view, runs):
    v, session = view
    session.add_run(runs[0])
    v.select_tab("individuals")
    _pump(qapp)
    v.individuals_tab.table.row_activated.emit(10)
    _pump(qapp)
    assert v.current_key() == "pedigree"
    assert v.pedigree_tab._current_id == runs[0].individuals[10].individual_id


def test_compare_needs_two_runs(qapp, view, runs):
    v, session = view
    session.add_run(runs[0])
    v.select_tab("compare")
    _pump(qapp)
    assert v.comparison_tab.stack.currentIndex() == 0
    session.add_run(runs[1])
    _pump(qapp)
    tab = v.comparison_tab
    assert tab.stack.currentIndex() == 1
    assert tab.run_list.count() == 2
    assert tab.table.row_count() == 2
    for key in ("mean_tbv", "genetic_variance", "mean_inbreeding", "selection_accuracy", "genetic_gain"):
        tab.metric.set_current(key, emit=True)
        _pump(qapp)
        assert len(tab.chart.ax.lines) >= 2
    # Colour slots follow the run, not its position
    slots = dict(tab._slots)
    tab.run_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert tab.table.row_count() == 1
    assert tab._slots == slots


def test_export_summary_and_chart(qapp, view, runs, tmp_path):
    v, session = view
    session.add_run(runs[1])
    _pump(qapp)
    summary = tmp_path / "summary.csv"
    v.export_summary_csv(str(summary))
    rows = list(csv.reader(summary.open()))
    assert rows[0][0] == "generation"
    assert any(h.endswith("_Health") for h in rows[0])
    assert len(rows) == len(runs[1].generations) + 1
    inds = tmp_path / "inds.csv"
    v.export_individuals_csv(str(inds))
    assert len(list(csv.reader(inds.open()))) == len(runs[1].individuals) + 1
    png = tmp_path / "chart.png"
    v.select_tab("overview")
    _pump(qapp)
    v.export_chart("png", str(png))
    assert png.stat().st_size > 1000


def test_remove_run_updates_view(qapp, view, runs):
    v, session = view
    session.add_run(runs[0])
    session.add_run(runs[1])
    _pump(qapp)
    session.remove_run(runs[1].run_id)
    _pump(qapp)
    assert session.current is runs[0]
    session.remove_run(runs[0].run_id)
    _pump(qapp)
    assert v.body.currentIndex() == 0


def test_chart_hover_and_theme_toggle(qapp, view, runs):
    from matplotlib.backend_bases import MouseEvent

    from adam_gui.themes import theme

    v, session = view
    session.add_run(runs[0])
    session.add_run(runs[1])
    for key in ("overview", "trends", "individuals", "pedigree", "genotypes", "compare"):
        v.select_tab(key)
        _pump(qapp)
    chart = v.overview_tab.gain_chart
    chart.canvas.draw()
    ax = chart.ax
    x, y = ax.transData.transform((2, 0.5))
    event = MouseEvent("motion_notify_event", chart.canvas, x, y)
    chart._on_move(event)
    assert chart._hover_artists  # crosshair + tooltip drawn
    theme().toggle()
    _pump(qapp)
    assert chart.figure.get_facecolor() is not None
    theme().toggle()
    _pump(qapp)
    assert theme().is_dark


def test_run_without_genotypes_or_qtl(qapp, view, runs):
    import copy

    v, session = view
    run = copy.copy(runs[0])
    run.run_id = "no-geno"
    run.genotype_data = {}
    run.qtl_info = []
    run.adam_version = ""
    session.add_run(run)
    v.select_tab("genotypes")
    _pump(qapp)
    assert v.genotype_tab.stack.currentIndex() == 1
    v.select_tab("trends")
    v.trends_tab.select("qtl")
    _pump(qapp)
    texts = [t.get_text() for t in v.trends_tab.current_chart().ax.texts]
    assert any("No QTL" in t for t in texts)


def test_data_table_handles_large_tables(qapp):
    import time

    from adam_gui.widgets.data_table import Column, DataTable

    n = 20000
    rng = np.random.default_rng(0)
    table = DataTable()
    table.set_columns([Column("id", "ID", np.arange(n)), Column("v", "Value", rng.normal(size=n), "{:.3f}")])
    t = time.perf_counter()
    table.model.sort(1, Qt.SortOrder.AscendingOrder)
    table.set_mask(rng.random(n) > 0.5)
    assert time.perf_counter() - t < 0.2
    assert 9000 < table.row_count() < 11000
