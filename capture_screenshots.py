#!/usr/bin/env python3
"""Programmatically capture screenshots of all ADAM GUI views with demo data."""

import sys
import os
from pathlib import Path

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    from adam_gui.qt_compat import QApplication, QTimer, QPixmap
    from adam_gui.app import AdamApplication
    from adam_gui.constants import (
        PAGE_PARAMETERS, PAGE_RUNNER, PAGE_RESULTS, PAGE_VISUALIZATIONS,
    )
    from adam_gui.services.demo_data import DemoDataGenerator
    from adam_gui.models.parameters import SimulationParameters

    app = AdamApplication(sys.argv)
    win = app.main_window
    win.resize(1400, 900)

    captures = []

    def grab(name: str):
        """Capture the main window to a PNG file."""
        app.processEvents()
        path = SCREENSHOT_DIR / f"{name}.png"
        pixmap = win.grab()
        pixmap.save(str(path), "PNG")
        captures.append(name)
        print(f"  Captured: {path}")

    def run_captures():
        print("Generating demo data...")
        params = SimulationParameters(name="Demo Breeding Program")
        gen = DemoDataGenerator(seed=42)
        results = gen.generate(params)
        app._on_simulation_done(results)
        app.processEvents()

        # 1. Parameter Editor
        print("Capturing views...")
        win.navigate_to(PAGE_PARAMETERS)
        app.processEvents()
        grab("01_parameter_editor")

        # 2. Simulation Runner
        win.navigate_to(PAGE_RUNNER)
        app.processEvents()
        grab("02_simulation_runner")

        # 3. Result Viewer - Summary
        win.navigate_to(PAGE_RESULTS)
        app.processEvents()
        app.result_viewer.tabs.setCurrentIndex(0)
        app.processEvents()
        grab("03_results_summary")

        # 4. Result Viewer - Population Chart
        app.result_viewer.tabs.setCurrentIndex(1)
        app.processEvents()
        grab("04_results_population")

        # 5. Result Viewer - Breeding Values
        app.result_viewer.tabs.setCurrentIndex(2)
        app.processEvents()
        grab("05_results_breeding_values")

        # 6. Result Viewer - Pedigree
        app.result_viewer.tabs.setCurrentIndex(3)
        app.processEvents()
        grab("06_results_pedigree")

        # 7. Result Viewer - Genotype
        app.result_viewer.tabs.setCurrentIndex(4)
        app.processEvents()
        grab("07_results_genotype")

        # 8. Result Viewer - Comparison (needs 2 runs)
        results2 = DemoDataGenerator(seed=99).generate(
            SimulationParameters(name="Alt Strategy")
        )
        app._on_simulation_done(results2)
        app.processEvents()
        app.result_viewer.tabs.setCurrentIndex(5)
        app.processEvents()
        # Select both runs and compare
        comp_tab = app.result_viewer.comparison_tab
        for i in range(comp_tab.run_list.count()):
            comp_tab.run_list.item(i).setSelected(True)
        comp_tab._run_comparison()
        app.processEvents()
        grab("08_results_comparison")

        # 9. 3D Viz Hub
        win.navigate_to(PAGE_VISUALIZATIONS)
        app.processEvents()
        app.viz_stack.setCurrentIndex(0)
        app.processEvents()
        grab("09_viz_hub")

        # 10-13. Individual 3D views
        viz_names = [
            (1, "10_viz_pedigree_3d"),
            (2, "11_viz_chromosome_3d"),
            (3, "12_viz_pca_scatter_3d"),
            (4, "13_viz_landscape_3d"),
        ]
        for idx, name in viz_names:
            app.viz_stack.setCurrentIndex(idx)
            app.processEvents()
            # Give VTK a moment to render
            for _ in range(5):
                app.processEvents()
            grab(name)

        # 14. Light theme
        app._toggle_theme()
        app.processEvents()
        win.navigate_to(PAGE_RESULTS)
        app.processEvents()
        app.result_viewer.tabs.setCurrentIndex(0)
        app.processEvents()
        grab("14_light_theme")

        # Switch back to dark
        app._toggle_theme()
        app.processEvents()

        print(f"\nDone! {len(captures)} screenshots saved to {SCREENSHOT_DIR}/")
        app.quit()

    # Schedule captures after the event loop starts
    QTimer.singleShot(500, run_captures)
    app.exec()


if __name__ == "__main__":
    main()
