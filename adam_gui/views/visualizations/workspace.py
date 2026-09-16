"""3D Explorer: one shared VTK canvas, four scenes, floating overlays."""

from __future__ import annotations

import re
import time

from adam_gui.icons import pixmap
from adam_gui.models.results import SimulationResults
from adam_gui.qt_compat import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QScrollArea, QShortcut, QKeySequence, QSizePolicy,
    QSplitter, QStackedWidget, Qt, QVBoxLayout, QWidget, Signal,
)
from adam_gui.session import Session
from adam_gui.themes import palette, theme
from adam_gui.themes.colormaps import categorical
from adam_gui.views.visualizations.controls import (
    ChromosomeControls, LandscapeControls, PCAControls, PedigreeControls,
)
from adam_gui.views.visualizations.overlays import (
    CameraToolbar, HintOverlay, InfoOverlay, LegendOverlay, OverlayHost,
)
from adam_gui.vtk_pipelines.chromosome_pipeline import ChromosomeScene, GenomeData
from adam_gui.vtk_pipelines.common import setup_lighting
from adam_gui.vtk_pipelines.pedigree_pipeline import PedigreeData, PedigreeScene
from adam_gui.vtk_pipelines.scatter_pipeline import PCAData, PCAScene
from adam_gui.vtk_pipelines.surface_pipeline import DistributionData, LandscapeScene
from adam_gui.widgets.run_selector import RunSelector
from adam_gui.widgets.ui import Card, EmptyState, Page, button, label, toast
from adam_gui.widgets.vtk_canvas import VTKCanvas

SCENES = [
    ("pedigree", "Pedigree network", "pedigree", "Who descends from whom across recent generations"),
    ("chromosomes", "Chromosome map", "dna", "QTL positions, effects and allele frequencies"),
    ("pca", "Population PCA", "scatter", "Genetic structure and drift between generations"),
    ("landscape", "Value landscape", "landscape", "How breeding values shift and narrow over time"),
]
HINTS = {
    "pedigree": "Drag to rotate · Shift-drag to pan · Scroll to zoom · Click an individual",
    "chromosomes": "Drag to rotate · Shift-drag to pan · Scroll to zoom · Click a QTL",
    "pca": "Drag to rotate · Shift-drag to pan · Scroll to zoom · Click a point",
    "landscape": "Drag to rotate · Shift-drag to pan · Scroll to zoom",
}


class SceneButton(QFrame):
    clicked = Signal(str)

    def __init__(self, key: str, title: str, icon: str, description: str, parent=None):
        super().__init__(parent)
        self.key = key
        self._icon_name = icon
        self.setObjectName("SceneButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 9, 10, 9)
        lay.setSpacing(11)
        self.icon = QLabel()
        self.icon.setFixedSize(34, 34)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(1)
        self.title = label(title)
        self.title.setStyleSheet("font-weight: 600;")
        text.addWidget(self.title)
        self.desc = label(description, "faint", wrap=True)
        text.addWidget(self.desc)
        lay.addLayout(text, 1)
        self._selected = False
        self.set_selected(False)

    def set_selected(self, on: bool):
        self._selected = on
        self.setProperty("selected", "true" if on else "false")
        p = palette()
        tone = p.accent if on else p.text_muted
        bg = p.accent_soft if on else p.surface_3
        self.icon.setStyleSheet(f"background-color: {bg}; border-radius: 9px;")
        self.icon.setPixmap(pixmap(self._icon_name, tone, 18))
        self.style().unpolish(self)
        self.style().polish(self)

    def refresh(self):
        self.set_selected(self._selected)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)
        super().mouseReleaseEvent(event)


class VisualizationView(QWidget):
    """3D Explorer page bound to the session's current run."""

    request_navigate = Signal(str)
    request_demo_run = Signal()

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._scene_key = "pedigree"
        self._cache: dict[tuple[str, str], object] = {}
        self._cameras: dict[tuple[str, str], tuple] = {}
        self._built_for: dict[str, str] = {}
        self._dirty = True
        self.timings: dict[str, float] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.page = Page("3D Explorer", "Explore the pedigree, genome and population structure of a run")
        root.addWidget(self.page)
        self.run_selector = RunSelector(session)
        self.page.header.add_action(self.run_selector)

        self.stack = QStackedWidget()
        self.page.root.addWidget(self.stack, 1)

        demo_btn = button("Generate demo data", "primary", "zap")
        demo_btn.clicked.connect(self.request_demo_run.emit)
        cfg_btn = button("Configure simulation", None, "sliders")
        cfg_btn.clicked.connect(lambda: self.request_navigate.emit("parameters"))
        self.empty = EmptyState(
            "box", "Nothing to explore yet",
            "Run a simulation or generate demo data, then come back to explore its pedigree, "
            "chromosomes and population structure in 3D.",
            actions=[demo_btn, cfg_btn])
        self.stack.addWidget(self.empty)

        self.content = QSplitter(Qt.Orientation.Horizontal)
        self.content.setChildrenCollapsible(False)
        self.stack.addWidget(self.content)

        # Left column: scene list + controls
        left = QWidget()
        left.setMinimumWidth(260)
        left.setMaximumWidth(360)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 6, 0)
        ll.setSpacing(14)
        scenes_card = Card(padding=8, spacing=2)
        self.scene_buttons: dict[str, SceneButton] = {}
        for key, title, icon, desc in SCENES:
            b = SceneButton(key, title, icon, desc)
            b.clicked.connect(self.set_scene)
            scenes_card.add(b)
            self.scene_buttons[key] = b
        self._scenes_card = scenes_card
        ll.addWidget(scenes_card)

        self.controls_card = Card("Options", padding=16, spacing=12)
        self.controls = QStackedWidget()
        self.pedigree_controls = PedigreeControls()
        self.chromosome_controls = ChromosomeControls()
        self.pca_controls = PCAControls()
        self.landscape_controls = LandscapeControls()
        self._control_pages = {
            "pedigree": self.pedigree_controls,
            "chromosomes": self.chromosome_controls,
            "pca": self.pca_controls,
            "landscape": self.landscape_controls,
        }
        for w in self._control_pages.values():
            self.controls.addWidget(w)
        self.controls.currentChanged.connect(self._fit_controls)
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setFrameShape(QFrame.Shape.NoFrame)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls_scroll.viewport().setAutoFillBackground(False)
        controls_scroll.setWidget(self.controls)
        self.controls.setAutoFillBackground(False)  # setWidget() turns it back on
        self.controls_card.add(controls_scroll, 1)
        ll.addWidget(self.controls_card, 1)
        self.content.addWidget(left)

        # Right: canvas with overlays
        viewport = Card(padding=0, spacing=0)
        self.canvas = VTKCanvas()
        self.canvas.set_hover_tracking(True)
        viewport.add(self.canvas, 1)
        self.content.addWidget(viewport)
        self.content.setStretchFactor(0, 0)
        self.content.setStretchFactor(1, 1)
        self.content.setSizes([290, 1000])
        self._viewport = viewport
        self._apply_viewport_style()

        self.info = InfoOverlay(self.canvas)
        self.toolbar = CameraToolbar(self.canvas)
        self.legend = LegendOverlay(self.canvas)
        self.hint = HintOverlay(self.canvas)
        self.overlays = OverlayHost(self.canvas, self.info, self.toolbar, self.legend, self.hint)

        setup_lighting(self.canvas.renderer)
        self.scenes = {
            "pedigree": PedigreeScene(),
            "chromosomes": ChromosomeScene(),
            "pca": PCAScene(),
            "landscape": LandscapeScene(),
        }

        # Wiring
        self.toolbar.reset.connect(self.reset_view)
        self.toolbar.view.connect(self.canvas.set_view)
        self.toolbar.save.connect(self.save_image)
        self.canvas.clicked.connect(self._on_click)
        self.canvas.hovered.connect(self._on_hover)
        self.info.close_requested.connect(self.clear_selection)
        self.canvas.home_view = self.reset_view
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self.canvas, activated=self.clear_selection)

        self.pedigree_controls.changed.connect(lambda: self.refresh(scene_only="pedigree"))
        self.pedigree_controls.find_requested.connect(self.find_individual)
        self.chromosome_controls.generation_changed.connect(self._on_generation)
        self.pca_controls.changed.connect(lambda: self._update_pca())
        self.pca_controls.range_changed.connect(lambda: self._update_pca())
        self.landscape_controls.changed.connect(lambda: self.refresh(scene_only="landscape"))

        session.current_run_changed.connect(self._on_run_changed)
        session.runs_changed.connect(self._prune_cache)
        theme().changed.connect(self._on_theme)

        self._select_button(self._scene_key)
        self.controls.setCurrentWidget(self._control_pages[self._scene_key])
        self._fit_controls(self.controls.currentIndex())
        self._on_run_changed(session.current)

    # ------------------------------------------------------------ data
    @property
    def scene(self):
        return self.scenes[self._scene_key]

    @property
    def run(self) -> SimulationResults | None:
        return self.session.current

    def _data(self, run: SimulationResults, kind: str):
        key = (run.run_id, kind)
        if key not in self._cache:
            builder = {"pedigree": PedigreeData, "genome": GenomeData,
                       "pca": PCAData, "dist": DistributionData}[kind]
            self._cache[key] = builder.from_results(run)
        return self._cache[key]

    def _prune_cache(self):
        if self.session.current is None and self.stack.currentWidget() is not self.empty:
            self._on_run_changed(None)
        ids = {r.run_id for r in self.session.runs}
        for key in [k for k in self._cache if k[0] not in ids]:
            del self._cache[key]
        for key in [k for k in self._cameras if k[0] not in ids]:
            del self._cameras[key]

    # ------------------------------------------------------------ run / scene switching
    def _on_run_changed(self, run):
        self._stop_animations()
        for s in self.scenes.values():
            if hasattr(s, "selected_row"):
                s.selected_row = None
            if hasattr(s, "selected_point"):
                s.selected_point = None
            if hasattr(s, "_selected_qtl"):
                s._selected_qtl = None
        self._built_for.clear()
        if run is None:
            for s in self.scenes.values():
                s.clear(self.canvas.renderer)
            self.stack.setCurrentWidget(self.empty)
            return
        self.stack.setCurrentWidget(self.content)
        self._configure_controls(run)
        self._dirty = True
        if self.isVisible():
            self.refresh()

    def _configure_controls(self, run: SimulationResults):
        ped = self._data(run, "pedigree")
        self.pedigree_controls.configure(ped.trait_names, ped.is_animal, len(ped.generations))
        genome = self._data(run, "genome")
        self.chromosome_controls.configure(genome.n_generations, genome.has_qtl)
        pca = self._data(run, "pca")
        self.pca_controls.configure([int(g) for g in pca.stored_gens], pca.trait_names)
        dist = self._data(run, "dist")
        self.landscape_controls.configure(dist.trait_names)

    def set_scene(self, key: str):
        if key not in self.scenes or key == self._scene_key and self._built_for.get(key):
            return
        self._stop_animations()
        self._save_camera()
        self.scene.clear(self.canvas.renderer)
        self._built_for.pop(self._scene_key, None)
        self._scene_key = key
        self._select_button(key)
        self.controls.setCurrentWidget(self._control_pages[key])
        self.hint.set_default(HINTS[key])
        self.refresh()

    def _select_button(self, key: str):
        for k, b in self.scene_buttons.items():
            b.set_selected(k == key)

    def _camera_key(self):
        run = self.run
        return (run.run_id if run else "", self._scene_key)

    def _save_camera(self):
        if not self.scene.is_built or self.run is None:
            return
        cam = self.canvas.renderer.GetActiveCamera()
        self._cameras[self._camera_key()] = (cam.GetPosition(), cam.GetFocalPoint(),
                                             cam.GetViewUp(), cam.GetViewAngle())

    def _restore_camera(self) -> bool:
        state = self._cameras.get(self._camera_key())
        if not state:
            return False
        cam = self.canvas.renderer.GetActiveCamera()
        cam.SetPosition(*state[0])
        cam.SetFocalPoint(*state[1])
        cam.SetViewUp(*state[2])
        cam.SetViewAngle(state[3])
        self.canvas.renderer.ResetCameraClippingRange()
        return True

    # ------------------------------------------------------------ building
    def refresh(self, scene_only: str | None = None, reset_camera: bool = False):
        """(Re)build the current scene for the current run."""
        if scene_only is not None and scene_only != self._scene_key:
            return
        run = self.run
        if run is None:
            return
        if not self.isVisible():
            self._dirty = True
            return
        self._dirty = False
        renderer = self.canvas.renderer
        key = self._scene_key
        for k, s in self.scenes.items():
            if k != key:
                s.clear(renderer)
        first_time = self._built_for.get(key) != run.run_id
        p = palette()
        t0 = time.perf_counter()
        if key == "pedigree":
            self.scene.build(renderer, self._data(run, "pedigree"), p, **self.pedigree_controls.options())
        elif key == "chromosomes":
            self.scene.build(renderer, self._data(run, "genome"), p, **self.chromosome_controls.options())
        elif key == "pca":
            self.scene.build(renderer, self._data(run, "pca"), p, **self.pca_controls.options())
        else:
            self.scene.build(renderer, self._data(run, "dist"), p, **self.landscape_controls.options())
        self.timings[key] = time.perf_counter() - t0
        self._built_for[key] = run.run_id
        if reset_camera or (first_time and not self._restore_camera()):
            self.scene.default_camera(renderer)
        else:
            renderer.ResetCameraClippingRange()
        self._update_overlays()
        self.canvas.request_render()

    def _update_pca(self):
        if self._scene_key != "pca" or self.run is None:
            return
        if not self.scene.is_built:
            self.refresh()
            return
        self.scene.update_points(self.canvas.renderer, **self.pca_controls.options())
        self._update_overlays()
        self.canvas.request_render()

    def _on_generation(self, generation: int):
        if self._scene_key != "chromosomes" or not self.scene.is_built:
            return
        self.scene.set_generation(generation)
        self._update_overlays()
        self.canvas.request_render()

    def _on_theme(self, *_):
        self._apply_viewport_style()
        for b in self.scene_buttons.values():
            b.refresh()
        if self.run is not None and self.scene.is_built:
            self._save_camera()
            self.refresh()
            self._restore_camera()
            self.canvas.request_render()

    def _fit_controls(self, index: int):
        """Size the scroll area to the visible options page only."""
        for i in range(self.controls.count()):
            policy = QSizePolicy.Policy.Preferred if i == index else QSizePolicy.Policy.Ignored
            self.controls.widget(i).setSizePolicy(policy, policy)
        self.controls.adjustSize()

    def _apply_viewport_style(self):
        p = palette()
        self._scenes_card.setStyleSheet(
            "QFrame#SceneButton { background: transparent; border: 1px solid transparent; border-radius: 10px; }"
            f"QFrame#SceneButton:hover {{ background: {p.surface_2}; }}"
            f"QFrame#SceneButton[selected=\"true\"] {{ background: {p.surface_2}; border-color: {p.border_strong}; }}"
        )

    def reset_view(self):
        if self.scene.is_built:
            self.scene.default_camera(self.canvas.renderer)
            self.canvas.request_render()

    # ------------------------------------------------------------ overlays
    def _update_overlays(self):
        scene = self.scene
        self.legend.set_spec(scene.legend() if scene.is_built else None)
        details = scene.details() if hasattr(scene, "details") else None
        p = palette()
        title = dict((k, t) for k, t, _, _ in SCENES)[self._scene_key]
        if details and self._scene_key == "pedigree":
            d = details
            rows = [("Generation", str(d["generation"]))]
            if d["sex"] != "—":
                rows.append(("Sex", d["sex"]))
            rows += [
                ("Sire", "—" if d["sire"] is None else f"#{d['sire']}"),
                ("Dam", "—" if d["dam"] is None else f"#{d['dam']}"),
                ("TBV", f"{d['tbv']:.3f}"),
                ("EBV", f"{d['ebv']:.3f}"),
                ("Inbreeding F", f"{d['inbreeding']:.3f}"),
                ("Selected", "Yes" if d["selected"] else "No"),
                ("Ancestors shown", f"{d['ancestors']:,}"),
                ("Descendants shown", f"{d['descendants']:,}"),
            ]
            dots = {"Ancestors shown": categorical(p, 0), "Descendants shown": categorical(p, 1)}
            self.info.set_content(f"Individual #{d['id']}", rows, closable=True, dots=dots)
        elif details and self._scene_key == "chromosomes":
            d = details
            rows = [
                ("Allele effect", f"{d['effect']:+.3f}"),
                ("Favourable freq.", f"{d['fav_now']:.2f}"),
                ("First → last gen", f"{d['fav_first']:.2f} → {d['fav_last']:.2f}"),
            ]
            self.info.set_content(f"QTL · Chr {d['chromosome']}", rows,
                                  subtitle=f"{d['position']:.1f} cM", closable=True)
        elif details and self._scene_key == "pca":
            d = details
            rows = [("Generation", str(d["generation"])), ("TBV", f"{d['tbv']:.3f}"),
                    ("Selected", "Yes" if d["selected"] else "No"),
                    ("PC1 / PC2 / PC3", " / ".join(f"{v:.1f}" for v in d["pc"]))]
            self.info.set_content(f"Individual #{d['id']}", rows, closable=True)
        else:
            run = self.run
            subtitle = self.session.label(run) if run else ""
            self.info.set_content(title, scene.stats() if scene.is_built else [], subtitle=subtitle)
        self.overlays.place()

    def _on_click(self, x: int, y: int):
        if self.scene.pick(self.canvas.renderer, x, y):
            self._update_overlays()
            self.canvas.request_render()

    def _on_hover(self, x: int, y: int):
        self.hint.show_hover(self.scene.hover(self.canvas.renderer, x, y))
        self.overlays.place()

    def clear_selection(self):
        scene = self.scene
        changed = False
        if getattr(scene, "selected_row", None) is not None:
            scene.select_row(self.canvas.renderer, None)
            changed = True
        elif getattr(scene, "selected_point", None) is not None:
            scene.selected_point = None
            scene.update_points(self.canvas.renderer, **scene._opts)
            changed = True
        elif getattr(scene, "_selected_qtl", None) is not None:
            scene._selected_qtl = None
            scene._apply_focus(self.canvas.renderer)
            changed = True
        if changed:
            self._update_overlays()
            self.canvas.request_render()

    def find_individual(self, individual_id: int):
        run = self.run
        if run is None:
            return
        if self._scene_key != "pedigree":
            self.set_scene("pedigree")
        data = self._data(run, "pedigree")
        rows = (data.ids == individual_id).nonzero()[0]
        if len(rows) == 0:
            self.pedigree_controls.set_find_status(f"No individual #{individual_id} in this run.")
            return
        row = int(rows[0])
        gens = data.generations
        needed = int((gens >= data.gen[row]).sum())
        controls = self.pedigree_controls
        if needed > controls.gens.maximum():
            controls.set_find_status(
                f"#{individual_id} is in generation {data.gen[row]}, older than the "
                f"{controls.gens.maximum()} most recent generations that can be shown.")
            return
        controls.set_find_status("")
        if needed > controls.gens.value():
            controls.gens.blockSignals(True)
            controls.gens.setValue(needed)
            controls.gens_value.setText(str(needed))
            controls.gens.blockSignals(False)
            self.refresh()
        self.scene.select_row(self.canvas.renderer, row)
        self._update_overlays()
        self.canvas.request_render()

    # ------------------------------------------------------------ misc
    def save_image(self):
        run = self.run
        base = re.sub(r"[^A-Za-z0-9_-]+", "-", self.session.label(run) if run else "scene").strip("-")
        default = f"{base}-{self._scene_key}.png"
        path, _ = QFileDialog.getSaveFileName(self, "Save 3D view as image", default, "PNG image (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        ok = self.export_image(path)
        toast(self, f"Saved {path.rsplit('/', 1)[-1]}" if ok else "Could not save the image",
              "accent" if ok else "danger")

    def export_image(self, path: str) -> bool:
        """Save the canvas with legend and info panel (without toolbar and hint)."""
        self.toolbar.hide()
        self.hint.hide()
        try:
            self.canvas.render_now()
            return self.canvas.grab().save(path)
        finally:
            self.toolbar.show()
            self.hint.show()

    def _stop_animations(self):
        self.chromosome_controls.play.stop()
        self.pca_controls.play.stop()

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty and self.run is not None:
            self.refresh()
        self.overlays.place()

    def hideEvent(self, event):
        self._stop_animations()
        super().hideEvent(event)
