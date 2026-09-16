#!/usr/bin/env python3
"""Regenerate the README screenshots by driving the real application.

    python capture_screenshots.py              # real window (crisp on HiDPI screens)
    python capture_screenshots.py --offscreen  # headless (CI / Linux without a display)

Uses the built-in demo simulator with fixed seeds, a throw-away settings file,
and writes PNGs (max 2000 px wide) to ./screenshots.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "screenshots"
MAX_WIDTH = 2000

if "--offscreen" in sys.argv:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ.setdefault("QT_SCALE_FACTOR", "2")
os.environ["ADAM_GUI_SETTINGS"] = str(Path(tempfile.mkdtemp()) / "settings.ini")
sys.path.insert(0, str(ROOT))


def main() -> int:
    from adam_gui.app import AdamApplication
    from adam_gui.models.enums import SelectionStrategy, SelectionUnit
    from adam_gui.qt_compat import Qt, QTimer
    from adam_gui.views.parameter_editor.presets import PRESETS
    from adam_gui.widgets.ui import Toast

    app = AdamApplication(sys.argv[:1], show=False)
    app.settings.theme = "dark"
    app._apply_theme_setting()
    win = app.main_window
    win.resize(1440, 900)
    win.show()
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()

    presets = {name: factory for name, _desc, factory in PRESETS}
    ryegrass = presets["Perennial ryegrass"]()
    ryegrass.random_seed = 11
    phenotypic = ryegrass.deep_copy()
    phenotypic.name = "Perennial ryegrass — phenotypic"
    phenotypic.selection.strategy = SelectionStrategy.PHENOTYPIC
    phenotypic.selection.unit = SelectionUnit.INDIVIDUAL
    phenotypic.random_seed = 12

    steps: list = []

    def pump(n: int = 8):
        for _ in range(n):
            app.processEvents()

    def shot(name: str):
        for toast in win.findChildren(Toast):
            toast.hide()
        pump()
        viz = app.viz_view
        if viz.isVisible():
            viz.canvas.render_now()
            pump()
        image = win.grab().toImage()
        if image.width() > MAX_WIDTH:
            image = image.scaledToWidth(MAX_WIDTH, Qt.TransformationMode.SmoothTransformation)
        path = OUT / f"{name}.png"
        image.save(str(path), "PNG", 0)  # 0 = smallest file
        print(f"  {path.relative_to(ROOT)}  {image.width()}x{image.height()}", flush=True)

    def run_demo(params, then):
        app.session.load_parameters(params)
        app.runner_view.demo_runs.setValue(1)
        app._run_from_setup("demo")

        def wait():
            if app.runner_view.is_running:
                QTimer.singleShot(50, wait)
            else:
                then()
        QTimer.singleShot(50, wait)

    def step_setup():
        app.session.load_parameters(ryegrass)
        win.navigate_to("parameters")
        app.param_editor.scroll.verticalScrollBar().setValue(0)
        shot("01_setup")
        run_demo(phenotypic, lambda: run_demo(ryegrass, next_step))

    def step_run():
        win.navigate_to("run")
        shot("02_run")
        next_step()

    def step_results():
        rv = app.result_viewer
        win.navigate_to("results")
        app.session.set_current(app.session.runs[-1].run_id)
        for key, name in (("overview", "03_results_overview"), ("trends", None),
                          ("individuals", "05_results_individuals"),
                          ("pedigree", "06_results_pedigree"),
                          ("genotypes", "07_results_genotypes")):
            rv.select_tab(key)
            if key == "trends":
                rv.trends_tab.select("qtl")
                shot("04_results_trends")
            else:
                shot(name)
        rv.select_tab("compare")
        shot("08_results_compare")
        next_step()

    def step_viz():
        viz = app.viz_view
        win.navigate_to("viz")
        pump()
        viz.set_scene("pedigree")
        pump()
        run = app.session.current
        last_gen = max(i.generation for i in run.individuals)
        parents = {s for s, _c in run.pedigree_edges}
        pick = max((i for i in run.individuals
                    if i.generation == last_gen - 1 and i.individual_id in parents),
                   key=lambda i: i.ebv[0])
        viz.find_individual(pick.individual_id)
        shot("09_3d_pedigree")
        viz.clear_selection()
        viz.set_scene("chromosomes")
        viz.chromosome_controls.slider.setValue(viz.chromosome_controls.slider.maximum() // 2)
        shot("10_3d_chromosomes")
        viz.set_scene("pca")
        shot("11_3d_pca")
        viz.set_scene("landscape")
        shot("12_3d_landscape")
        next_step()

    def step_light():
        app.settings.theme = "light"
        app._apply_theme_setting()
        pump()
        win.navigate_to("parameters")
        shot("13_light_setup")
        win.navigate_to("results")
        app.result_viewer.select_tab("overview")
        shot("14_light_results")
        win.navigate_to("viz")
        app.viz_view.set_scene("pca")
        shot("15_light_3d")
        next_step()

    def finish():
        app.session.mark_dirty(False)
        win.close()
        app.quit()

    steps.extend([step_setup, step_run, step_results, step_viz, step_light, finish])

    def next_step():
        QTimer.singleShot(150, steps.pop(0))

    next_step()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
