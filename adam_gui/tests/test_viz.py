"""Tests for the 3D Explorer: scene pipelines, offscreen canvas and workspace."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import copy  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from adam_gui.models.enums import OrganismType  # noqa: E402
from adam_gui.models.parameters import SimulationParameters  # noqa: E402
from adam_gui.models.results import SimulationResults  # noqa: E402
from adam_gui.qt_compat import QApplication  # noqa: E402
from adam_gui.services.demo_data import DemoDataGenerator  # noqa: E402


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    from adam_gui.themes import theme
    theme().apply("dark")
    yield instance
    theme().apply("dark")


def _params(name: str, animal: bool = False) -> SimulationParameters:
    p = SimulationParameters(name=name)
    p.breeding.n_cycles = 3
    p.breeding.generations_per_cycle = 3
    p.founder.n_paternal = 40
    p.founder.n_maternal = 40
    if animal:
        p.organism_type = OrganismType.ANIMAL
    return p


@pytest.fixture(scope="module")
def plant_run():
    return DemoDataGenerator(seed=42).generate(_params("Plant"))


@pytest.fixture(scope="module")
def animal_run():
    return DemoDataGenerator(seed=3).generate(_params("Animal", animal=True))


@pytest.fixture(scope="module")
def bare_run(plant_run):
    run = copy.copy(plant_run)
    run.run_id = "bare"
    run.qtl_info = []
    run.marker_info = []
    run.genotype_data = {}
    return run


@pytest.fixture(scope="module")
def empty_run():
    return SimulationResults(run_id="empty", parameters=SimulationParameters(name="Empty"))


@pytest.fixture
def canvas(app):
    from adam_gui.vtk_pipelines.common import setup_lighting
    from adam_gui.widgets.vtk_canvas import VTKCanvas

    c = VTKCanvas()
    c.resize(640, 420)
    c.show()
    setup_lighting(c.renderer)
    yield c
    c.close()
    c.deleteLater()


def _render(canvas):
    img = canvas.grab_image()
    assert not img.isNull()
    assert img.width() >= 640
    return img


RUNS = ["plant_run", "animal_run", "bare_run", "empty_run"]


@pytest.mark.parametrize("run_name", RUNS)
def test_pedigree_scene(canvas, request, run_name):
    from adam_gui.themes import palette
    from adam_gui.vtk_pipelines.pedigree_pipeline import COLOR_OPTIONS, PedigreeData, PedigreeScene

    run = request.getfixturevalue(run_name)
    data = PedigreeData.from_results(run)
    scene = PedigreeScene()
    for color in COLOR_OPTIONS:
        for arrange, links in (("ebv", "all"), ("family", "selected"), ("ebv", "none")):
            scene.build(canvas.renderer, data, palette(), n_gens=4, color_by=color,
                        arrange=arrange, links=links)
    scene.default_camera(canvas.renderer)
    _render(canvas)
    if data.n:
        assert scene.is_built
        assert len(scene.rows) == int(np.isin(data.gen, data.generations[-4:]).sum())
        assert scene.legend() is not None
        assert scene.stats()
    else:
        assert scene.legend() is None


def test_pedigree_pick_highlights_lineage(canvas, plant_run):
    from adam_gui.themes import palette
    from adam_gui.vtk_pipelines.common import project_points
    from adam_gui.vtk_pipelines.pedigree_pipeline import PedigreeData, PedigreeScene

    scene = PedigreeScene()
    scene.build(canvas.renderer, PedigreeData.from_results(plant_run), palette(), n_gens=4)
    scene.default_camera(canvas.renderer)
    _render(canvas)
    # pick a node in the newest generation: it must have ancestors in view
    idx = int(np.argmax(scene.pos[:, 1]))
    disp, _ = project_points(canvas.renderer, scene.pos[[idx]])
    assert scene.pick(canvas.renderer, disp[0, 0], disp[0, 1])
    details = scene.details()
    assert details is not None
    assert details["ancestors"] > 0
    assert scene.hover(canvas.renderer, disp[0, 0], disp[0, 1])
    _render(canvas)
    # clicking empty space clears the selection
    assert scene.pick(canvas.renderer, 1, 1)
    assert scene.details() is None


@pytest.mark.parametrize("run_name", RUNS)
def test_chromosome_scene(canvas, request, run_name):
    from adam_gui.themes import palette
    from adam_gui.vtk_pipelines.chromosome_pipeline import ChromosomeScene, GenomeData

    run = request.getfixturevalue(run_name)
    data = GenomeData.from_results(run)
    scene = ChromosomeScene()
    scene.build(canvas.renderer, data, palette(), generation=0)
    scene.default_camera(canvas.renderer)
    _render(canvas)
    if data.has_qtl:
        before = data.favourable_freq(0).copy()
        last = data.n_generations - 1
        scene.set_generation(last)
        assert np.allclose(data.favourable_freq(last), data.favourable_freq(last))
        assert scene.stats()
        assert scene.legend() is not None
        assert not np.allclose(before, data.favourable_freq(last))
        _render(canvas)
    else:
        assert scene.legend() is None
        scene.set_generation(3)  # must be a no-op, not an error


def test_chromosome_handles_many_qtl(canvas):
    from adam_gui.themes import palette
    from adam_gui.vtk_pipelines.chromosome_pipeline import ChromosomeScene, GenomeData

    run = DemoDataGenerator(seed=5).generate(SimulationParameters())
    data = GenomeData.from_results(run)
    assert len(data.qtl_chrom) >= 300
    scene = ChromosomeScene()
    scene.build(canvas.renderer, data, palette(), generation=10)
    _render(canvas)
    assert len(scene.qtl_xyz) == len(data.qtl_chrom)


@pytest.mark.parametrize("run_name", RUNS)
def test_pca_scene(canvas, request, run_name):
    from adam_gui.themes import palette
    from adam_gui.vtk_pipelines.scatter_pipeline import PCAData, PCAScene

    run = request.getfixturevalue(run_name)
    data = PCAData.from_results(run)
    scene = PCAScene()
    for color in ("generation", "tbv", "selected"):
        scene.build(canvas.renderer, data, palette(), color_by=color)
    if data.n:
        scene.default_camera(canvas.renderer)
        g = data.stored_gens
        scene.update_points(canvas.renderer, "generation", 0, int(g[0]), int(g[0]))
        assert len(scene.visible_idx) == int((data.gen == g[0]).sum())
        assert np.all(np.isfinite(data.coords))
        assert data.centroids.shape == (len(g), 3)
    _render(canvas)


def test_pca_generations_share_space(plant_run):
    from adam_gui.vtk_pipelines.scatter_pipeline import PCAData

    data = PCAData.from_results(plant_run)
    # later generations drift along PC1 (oriented to increase with generation)
    assert data.centroids[-1, 0] > data.centroids[0, 0]
    assert 0 < data.evr.sum() <= 1.0 + 1e-9


@pytest.mark.parametrize("run_name", RUNS)
def test_landscape_scene(canvas, request, run_name):
    from adam_gui.themes import palette
    from adam_gui.vtk_pipelines.surface_pipeline import METRICS, DistributionData, LandscapeScene

    run = request.getfixturevalue(run_name)
    data = DistributionData.from_results(run)
    scene = LandscapeScene()
    for metric in METRICS:
        for contours, normalise in ((True, True), (False, False)):
            scene.build(canvas.renderer, data, palette(), metric=metric,
                        contours=contours, normalise=normalise)
    scene.default_camera(canvas.renderer)
    _render(canvas)
    if data.n:
        assert scene.legend() is not None
        assert scene.stats()


def test_density_grid_is_normalised():
    from adam_gui.vtk_pipelines.surface_pipeline import density_grid, morph_rows

    rng = np.random.default_rng(0)
    gens = np.repeat(np.arange(5), 100)
    values = rng.normal(gens * 0.5, 1.0)
    ug, centres, dens, means = density_grid(values, gens, normalise=True)
    assert np.allclose(dens.max(axis=1), 1.0)
    assert np.allclose(means, [values[gens == g].mean() for g in ug])
    fine_g, fine_d, fine_m = morph_rows(ug, centres, dens, means, steps=4)
    assert len(fine_m) == len(fine_g)
    assert len(fine_g) == 4 * (len(ug) - 1) + 1
    assert fine_d.shape == (len(fine_g), len(centres))


def test_workspace_end_to_end(app, plant_run, animal_run, bare_run, tmp_path):
    from adam_gui.session import Session
    from adam_gui.themes import theme
    from adam_gui.views.visualizations import VisualizationView
    from adam_gui.vtk_pipelines.common import project_points

    session = Session()
    view = VisualizationView(session)
    view.resize(1200, 800)
    view.show()
    app.processEvents()
    assert view.stack.currentWidget() is view.empty

    session.add_run(animal_run)
    session.add_run(bare_run)
    session.add_run(plant_run)
    app.processEvents()
    assert view.stack.currentWidget() is view.content

    for key in ("pedigree", "chromosomes", "pca", "landscape"):
        view.set_scene(key)
        app.processEvents()
        assert view.scene.is_built, key
        assert key in view.timings

    # pedigree pick via the canvas signal
    view.set_scene("pedigree")
    app.processEvents()
    view.canvas.render_now()
    scene = view.scene
    idx = int(np.argmax(scene.pos[:, 1]))
    disp, _ = project_points(view.canvas.renderer, scene.pos[[idx]])
    view.canvas.clicked.emit(int(disp[0, 0]), int(disp[0, 1]))
    assert scene.details() is not None
    assert view.info.close_btn.isVisibleTo(view.info)
    view.clear_selection()
    assert scene.details() is None

    # find an individual from the newest generation
    newest = max(i.generation for i in plant_run.individuals)
    target = next(i for i in plant_run.individuals if i.generation == newest)
    view.find_individual(target.individual_id)
    assert scene.details()["id"] == target.individual_id
    view.find_individual(10 ** 9)
    assert view.pedigree_controls.find_status.isVisibleTo(view.pedigree_controls)

    # theme toggle rebuilds without losing the scene
    theme().apply("light")
    app.processEvents()
    assert view.scene.is_built
    theme().apply("dark")
    app.processEvents()

    # chromosome animation ticks advance the generation
    view.set_scene("chromosomes")
    slider = view.chromosome_controls.slider
    start = slider.value()
    view.chromosome_controls.play.tick.emit()
    assert slider.value() == (start + 1) % (slider.maximum() + 1)
    view.chromosome_controls.play.btn.setChecked(True)
    assert view.chromosome_controls.play.timer.isActive()
    view.set_scene("pca")
    assert not view.chromosome_controls.play.timer.isActive()

    # pca reveal ticks move the upper bound
    pca = view.pca_controls
    pca.start_play()
    first = pca.gen_to.currentIndex()
    pca.play.tick.emit()
    assert pca.gen_to.currentIndex() == first + 1
    assert len(view.scene.visible_idx) > 0

    # runs without QTL / genotypes show notes instead of failing
    session.set_current(bare_run.run_id)
    app.processEvents()
    view.set_scene("chromosomes")
    assert view.chromosome_controls.note.isVisibleTo(view.chromosome_controls)
    view.set_scene("pca")
    assert not view.scene.is_built

    # export composite image
    session.set_current(plant_run.run_id)
    view.set_scene("landscape")
    app.processEvents()
    out = tmp_path / "landscape.png"
    assert view.export_image(str(out))
    assert out.stat().st_size > 1000

    # removing every run returns to the empty state
    for run in list(session.runs):
        session.remove_run(run.run_id)
    app.processEvents()
    assert view.stack.currentWidget() is view.empty
    view.close()


def test_old_qvtk_widget_removed():
    with pytest.raises(ImportError):
        import adam_gui.widgets.vtk_widget  # noqa: F401
