"""Live summary of the setup with validation results and run buttons."""

from __future__ import annotations

from adam_gui.icons import pixmap
from adam_gui.models.enums import OrganismType
from adam_gui.models.parameters import SimulationParameters
from adam_gui.qt_compat import QGridLayout, QHBoxLayout, QLabel, Qt, QVBoxLayout, QWidget, Signal
from adam_gui.services.validation import (
    ERROR, INFO, WARNING, Issue, population_size, selected_parents, total_generations,
)
from adam_gui.themes import palette, theme
from adam_gui.views.parameter_editor.sections import (
    ORGANISM_LABELS, PROPAGATION_LABELS, STRATEGY_LABELS, UNIT_LABELS,
)
from adam_gui.widgets.ui import Card, button, divider, label


class _IssueRow(QWidget):
    clicked = Signal(str)

    def __init__(self, issue: Issue, parent=None):
        super().__init__(parent)
        self._section = issue.section
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Show this setting")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(8)
        p = palette()
        icon, color = {ERROR: ("alert-circle", p.danger), WARNING: ("alert-triangle", p.warning),
                       INFO: ("info", p.info)}[issue.level]
        ic = QLabel()
        ic.setPixmap(pixmap(icon, color, 15))
        lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        text = label(issue.message, wrap=True)
        lay.addWidget(text, 1)

    def mouseReleaseEvent(self, event):
        self.clicked.emit(self._section)
        super().mouseReleaseEvent(event)


class SummaryPanel(Card):
    run_requested = Signal(str)       # "demo" | "adam"
    section_requested = Signal(str)   # section key

    FACTS = ["Organism", "Evaluation", "Propagation", "Population", "Parents",
             "Generations", "Traits", "Replicates"]

    def __init__(self, parent=None):
        super().__init__("Summary", parent=parent, padding=18, spacing=12)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)
        self._values: dict[str, QLabel] = {}
        for r, name in enumerate(self.FACTS):
            grid.addWidget(label(name, "muted"), r, 0, Qt.AlignmentFlag.AlignTop)
            value = label("", wrap=True)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value, r, 1)
            self._values[name] = value
        self.add(grid)
        self.add(divider())

        head = QHBoxLayout()
        head.addWidget(label("Checks", "section"))
        head.addStretch(1)
        self.check_badge = label("", "badge")
        head.addWidget(self.check_badge)
        self.add(head)
        self._issues_box = QVBoxLayout()
        self._issues_box.setSpacing(4)
        self.add(self._issues_box)
        self.add(divider())

        self.demo_btn = button("Run demo simulation", "primary", icon="zap",
                               tooltip="Simulate with the built-in demo simulator (Ctrl+Shift+R)")
        self.adam_btn = button("Run with ADAM", icon="play", tooltip="Run the configured ADAM executable (Ctrl+R)")
        self.demo_btn.clicked.connect(lambda: self.run_requested.emit("demo"))
        self.adam_btn.clicked.connect(lambda: self.run_requested.emit("adam"))
        self.add(self.demo_btn)
        self.add(self.adam_btn)
        self.engine_note = label("", "help", wrap=True)
        self.add(self.engine_note)
        self._issues: list[Issue] = []
        theme().changed.connect(self._on_theme)

    def set_adam_available(self, available: bool):
        self.adam_btn.setEnabled(available)
        self.adam_btn.setToolTip("Run the configured ADAM executable (Ctrl+R)" if available
                                 else "Configure the ADAM executable in Settings first")
        self.engine_note.setText(
            "Demo runs use the built-in simulator, not ADAM; they take seconds."
            if available else
            "ADAM is not configured, so only demo runs are available. The built-in "
            "simulator is not ADAM, but it uses the same setup.")

    def update_summary(self, params: SimulationParameters, issues: list[Issue]):
        animal = params.organism_type == OrganismType.ANIMAL
        n = population_size(params)
        males, females = selected_parents(params)
        v = self._values
        v["Organism"].setText(f"{ORGANISM_LABELS[params.organism_type]} · {params.genetic_model.name.title()}")
        v["Evaluation"].setText(f"{STRATEGY_LABELS[params.selection.strategy]}\n"
                                f"{UNIT_LABELS[params.selection.unit]}")
        v["Propagation"].setText(PROPAGATION_LABELS[params.propagation.method])
        v["Population"].setText(f"{n:,} per generation")
        v["Parents"].setText(f"{males:,} ♂ · {females:,} ♀" if animal else f"{males:,} plants")
        v["Generations"].setText(f"{total_generations(params):,} "
                                 f"({params.breeding.n_cycles} × {params.breeding.generations_per_cycle})")
        v["Traits"].setText(", ".join(f"{t.name} (h² {t.heritability:.2f})" for t in params.traits) or "—")
        v["Replicates"].setText(f"{params.breeding.n_replicates:,}")
        self._issues = issues
        self._render_issues()

    def _on_theme(self, *_):
        self._render_issues()

    def _render_issues(self):
        while self._issues_box.count():
            item = self._issues_box.takeAt(0)
            if item.widget():
                item.widget().hide()  # deleteLater waits for the event loop
                item.widget().deleteLater()
        errors = sum(1 for i in self._issues if i.level == ERROR)
        warnings = sum(1 for i in self._issues if i.level == WARNING)
        if not self._issues:
            ic = QLabel()
            ic.setPixmap(pixmap("check-circle", palette().accent, 15))
            holder = QWidget()
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(8)
            hl.addWidget(ic)
            hl.addWidget(label("Everything looks good."), 1)
            self._issues_box.addWidget(holder)
            self.check_badge.setText("Ready")
            self.check_badge.setProperty("role", "badge-accent")
        else:
            order = {ERROR: 0, WARNING: 1, INFO: 2}
            for issue in sorted(self._issues, key=lambda i: order[i.level])[:6]:
                w = _IssueRow(issue)
                w.clicked.connect(self.section_requested.emit)
                self._issues_box.addWidget(w)
            if len(self._issues) > 6:
                self._issues_box.addWidget(label(f"+ {len(self._issues) - 6} more", "help"))
            if errors:
                self.check_badge.setText(f"{errors} error{'s' if errors != 1 else ''}")
                self.check_badge.setProperty("role", "badge-danger")
            elif warnings:
                self.check_badge.setText(f"{warnings} warning{'s' if warnings != 1 else ''}")
                self.check_badge.setProperty("role", "badge-warning")
            else:
                self.check_badge.setText("Notes")
                self.check_badge.setProperty("role", "badge-info")
        style = self.check_badge.style()
        style.unpolish(self.check_badge)
        style.polish(self.check_badge)
        self.demo_btn.setEnabled(errors == 0)
        self.demo_btn.setToolTip("Fix the errors listed above first" if errors
                                 else "Simulate with the built-in demo simulator (Ctrl+Shift+R)")

    @property
    def has_errors(self) -> bool:
        return any(i.level == ERROR for i in self._issues)
