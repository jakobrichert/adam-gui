"""Read-only summary of current simulation parameters."""

from adam_gui.qt_compat import QWidget, QVBoxLayout, QTextEdit
from adam_gui.models.parameters import SimulationParameters


class SummaryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumHeight(180)
        layout.addWidget(self.text)

        self.update_summary(SimulationParameters())

    def update_summary(self, params: SimulationParameters):
        lines = [
            f"<b>{params.name}</b>",
            f"Organism: {params.organism_type.name.replace('_', ' ').title()}",
            f"Genetic model: {params.genetic_model.name.title()}",
            "",
            f"Founders: {params.founder.n_paternal} paternal, {params.founder.n_maternal} maternal",
            f"Chromosomes: {params.founder.n_chromosomes} ({params.founder.ploidy.name.title()})",
            f"Founder generations: {params.founder.n_founder_generations}",
            "",
            f"Traits: {len(params.traits)} "
            f"({', '.join(t.name for t in params.traits)})",
            "",
            f"Breeding: {params.breeding.n_cycles} cycles, "
            f"{params.breeding.generations_per_cycle} gen/cycle, "
            f"{params.breeding.n_replicates} replicates",
            f"Overlapping cycles: {'Yes' if params.breeding.overlapping_cycles else 'No'}",
            "",
            f"Selection: {params.selection.strategy.name.title()} / "
            f"{params.selection.unit.name.replace('_', ' ').title()}",
            f"Truncation: {params.selection.truncation_proportion_male:.0%} male, "
            f"{params.selection.truncation_proportion_female:.0%} female",
            "",
            f"Propagation: {params.propagation.method.name.title()}",
            f"Offspring/cross: {params.propagation.n_offspring_per_cross}",
            f"Speed breeding: {params.propagation.speed_breeding_generations_per_year} gen/year",
        ]
        self.text.setHtml("<br>".join(lines))
