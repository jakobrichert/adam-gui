"""UI tests for the application shell, setup editor, runner and settings."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from adam_gui.models.enums import OrganismType, PropagationMethod, SelectionStrategy  # noqa: E402
from adam_gui.models.parameters import SimulationParameters  # noqa: E402
from adam_gui.qt_compat import QApplication, QLocale  # noqa: E402
from adam_gui.services import validation  # noqa: E402
from adam_gui.session import Session  # noqa: E402
from adam_gui.themes import theme  # noqa: E402
from adam_gui.views.parameter_editor.presets import PRESETS  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
    theme().apply("dark")
    return app


@pytest.fixture
def settings(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("ADAM_GUI_SETTINGS", str(tmp_path / "settings.ini"))
    from adam_gui.settings import AppSettings
    return AppSettings()


@pytest.fixture
def editor(settings):
    from adam_gui.views.parameter_editor import ParameterEditorView
    session = Session()
    view = ParameterEditorView(session, settings)
    view.resize(1400, 900)
    return view


def _normalise(d: dict) -> dict:
    d = dict(d)
    d["trait_correlations"] = [c for c in d["trait_correlations"]
                               if c["genetic_correlation"] or c["environmental_correlation"]]
    return d


# ---------------------------------------------------------------- validation

def test_default_parameters_validate_cleanly():
    issues = validation.validate(SimulationParameters())
    assert not [i for i in issues if i.level == validation.ERROR]


def test_validation_catches_common_mistakes():
    p = SimulationParameters()
    p.traits[0].heritability = 0.0
    p.organism_type = OrganismType.ANIMAL
    p.propagation.method = PropagationMethod.SELFING
    p.selection.truncation_proportion_male = 0.001
    messages = " ".join(i.message for i in validation.validate(p) if i.level == validation.ERROR)
    assert "heritability" in messages
    assert "crossing" in messages
    assert "no males" in messages


def test_genomic_selection_requires_genomic_model():
    from adam_gui.models.enums import GeneticModel
    p = SimulationParameters()
    p.genetic_model = GeneticModel.INFINITESIMAL
    p.selection.strategy = SelectionStrategy.GBLUP
    assert any(i.section == "selection" and i.level == validation.ERROR for i in validation.validate(p))


def test_selected_parent_counts():
    p = SimulationParameters()
    p.organism_type = OrganismType.ANIMAL
    p.founder.n_paternal = p.founder.n_maternal = 100
    p.selection.truncation_proportion_male = 0.1
    p.selection.truncation_proportion_female = 0.5
    assert validation.selected_parents(p) == (10, 50)


# ---------------------------------------------------------------- session

def test_session_labels_are_unique_and_current_follows_removal(qapp):
    from adam_gui.models.results import SimulationResults
    s = Session()
    a = SimulationResults(run_id="a", parameters=SimulationParameters(name="X"))
    b = SimulationResults(run_id="b", parameters=SimulationParameters(name="X"))
    s.add_run(a)
    s.add_run(b)
    assert s.label(a) == "X" and s.label(b) == "X (2)"
    assert s.current is b and s.dirty
    s.remove_run("b")
    assert s.current is a


def test_session_project_roundtrip(tmp_path, qapp):
    from adam_gui.services.demo_data import DemoDataGenerator
    s = Session()
    params = PRESETS[1][2]()
    params.breeding.n_cycles = 3
    s.load_parameters(params)
    s.add_run(DemoDataGenerator(seed=1).generate(params))
    path = s.save_project(tmp_path / "trial.adam-project")
    assert not s.dirty and path.exists()
    loaded = Session()
    received = []
    loaded.parameters_loaded.connect(received.append)
    loaded.load_project(path)
    assert loaded.project_name == "trial"
    assert len(loaded.runs) == 1 and loaded.current is not None
    assert received and received[0].name == params.name


# ---------------------------------------------------------------- editor

def test_editor_starts_in_sync_with_defaults(editor):
    assert _normalise(editor.get_parameters().to_dict()) == _normalise(SimulationParameters().to_dict())


@pytest.mark.parametrize("name,factory", [(n, f) for n, _d, f in PRESETS])
def test_presets_roundtrip_through_editor(editor, name, factory):
    params = factory()
    editor.session.load_parameters(params)
    assert _normalise(editor.get_parameters().to_dict()) == _normalise(params.to_dict()), name


def test_editing_updates_session_and_summary(editor):
    session = editor.session
    editor.sections["basics"].name_edit.setText("My programme")
    assert session.parameters.name == "My programme"
    assert session.dirty
    editor.sections["founders"].n_chromosomes.setValue(3)
    assert len(session.parameters.founder.chromosomes) == 3
    assert session.parameters.founder.n_chromosomes == 3


def test_animal_hides_plant_only_options(editor):
    from adam_gui.views.parameter_editor.fields import set_combo_value
    prop = editor.sections["propagation"]
    set_combo_value(prop.method, PropagationMethod.SELFING)
    set_combo_value(editor.sections["basics"].organism, OrganismType.ANIMAL)
    params = editor.session.parameters
    assert params.organism_type == OrganismType.ANIMAL
    assert params.propagation.method == PropagationMethod.CROSSING
    assert not editor.sections["selection"].female_cell.isHidden()


def test_trait_add_remove_and_correlations(editor):
    traits = editor.sections["traits"]
    traits._add_trait()
    assert len(editor.session.parameters.traits) == 2
    assert traits.corr_table.rowCount() == 1
    traits.table.selectRow(1)
    traits._remove()
    assert len(editor.session.parameters.traits) == 1
    assert traits.corr_table.isHidden()


def test_summary_blocks_demo_on_errors(editor):
    traits = editor.sections["traits"]
    from adam_gui.qt_compat import Qt
    traits.table.item(0, 2).setData(Qt.ItemDataRole.EditRole, 0.0)
    assert editor.has_errors
    assert not editor.summary.demo_btn.isEnabled()


def test_parameter_file_export_import(editor, tmp_path, monkeypatch):
    from adam_gui.qt_compat import QFileDialog
    target = tmp_path / "setup.adam-params"
    editor.sections["basics"].name_edit.setText("Exported")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    editor.export_parameters()
    assert target.exists()
    editor.session.load_parameters(SimulationParameters())
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(target), ""))
    editor.import_parameters()
    assert editor.session.parameters.name == "Exported"


# ---------------------------------------------------------------- runner

def test_demo_run_adds_results(settings, qtbot):
    from adam_gui.views.simulation_runner import RunnerView
    session = Session()
    params = SimulationParameters()
    params.breeding.n_cycles = 2
    session.load_parameters(params)
    view = RunnerView(session, settings)
    qtbot.addWidget(view)
    nav = []
    view.request_navigate.connect(nav.append)
    view.demo_runs.setValue(2)
    with qtbot.waitSignal(view.running_changed, timeout=20000, check_params_cb=lambda r: r is False):
        view.start_demo()
    assert len(session.runs) == 2
    assert nav == ["results"]
    assert [e.status for e in view._history] == ["done", "done"]


def test_demo_run_can_be_cancelled(settings, qtbot):
    from adam_gui.views.simulation_runner import RunnerView
    session = Session()
    params = SimulationParameters()
    params.breeding.n_cycles = 200
    session.load_parameters(params)
    view = RunnerView(session, settings)
    qtbot.addWidget(view)
    with qtbot.waitSignal(view.running_changed, timeout=30000, check_params_cb=lambda r: r is False):
        view.start_demo(1)
        view.stop()
    assert session.runs == []
    assert view._history[0].status == "cancelled"


def test_adam_worker_reports_missing_output(tmp_path, qtbot):
    """A fake 'ADAM' that exits 0 without writing files must fail cleanly."""
    import stat
    from adam_gui.views.simulation_runner.workers import AdamWorker
    exe = tmp_path / "fake_adam.sh"
    exe.write_text("#!/bin/sh\necho generation 1\necho generation 2\nexit 0\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    worker = AdamWorker(SimulationParameters(), str(exe), str(tmp_path / "runs"))
    failures, lines = [], []
    worker.run_failed.connect(failures.append)
    worker.log.connect(lines.append)
    worker.run()  # synchronous for the test
    assert failures and "no recognised output" in failures[0]
    assert "generation 2" in lines
    assert worker.run_dir is not None and (worker.run_dir / "parameters.txt").exists()
    assert (worker.run_dir / "adam.log").read_text().count("generation") == 2


def test_adam_worker_parses_output(tmp_path, qtbot):
    import stat
    from adam_gui.views.simulation_runner.workers import AdamWorker
    exe = tmp_path / "fake_adam.sh"
    exe.write_text(
        "#!/bin/sh\n"
        "printf 'Generation Cycle N MeanTBV Var F Acc Gain\\n0 0 10 0.0 1.0 0.0 0.5 0.0\\n"
        "1 0 10 0.3 0.9 0.01 0.6 0.3\\n' > population.txt\n"
        "exit 0\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    worker = AdamWorker(SimulationParameters(), str(exe), str(tmp_path / "runs"))
    done = []
    worker.run_finished.connect(done.append)
    worker.run()
    assert done and done[0].n_generations == 2


# ---------------------------------------------------------------- settings

def test_settings_persist(settings, tmp_path):
    settings.adam_executable = "/nope/adam"
    assert not settings.adam_available
    project = tmp_path / "p.adam-project"
    project.write_text("{}")
    settings.add_recent_project(str(project))
    from adam_gui.settings import AppSettings
    again = AppSettings()
    assert again.adam_executable == "/nope/adam"
    assert again.recent_projects == [str(project.resolve())]
