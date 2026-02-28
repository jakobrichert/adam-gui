"""Summary tab showing key metrics at a glance."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
)
from adam_gui.models.results import SimulationResults


class MetricCard(QFrame):
    """Small card showing a single metric."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.04);
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self._title = QLabel(title)
        self._title.setObjectName("muted")
        layout.addWidget(self._title)

        self._value = QLabel("--")
        self._value.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(self._value)

        self._detail = QLabel("")
        self._detail.setObjectName("muted")
        layout.addWidget(self._detail)

    def set_value(self, value: str, detail: str = ""):
        self._value.setText(value)
        self._detail.setText(detail)


class SummaryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(12)

        self.card_generations = MetricCard("Generations")
        self.card_individuals = MetricCard("Total Individuals")
        self.card_genetic_gain = MetricCard("Final Genetic Gain")
        self.card_inbreeding = MetricCard("Final Inbreeding")
        self.card_accuracy = MetricCard("Selection Accuracy")
        self.card_variance = MetricCard("Final Genetic Variance")

        grid.addWidget(self.card_generations, 0, 0)
        grid.addWidget(self.card_individuals, 0, 1)
        grid.addWidget(self.card_genetic_gain, 0, 2)
        grid.addWidget(self.card_inbreeding, 1, 0)
        grid.addWidget(self.card_accuracy, 1, 1)
        grid.addWidget(self.card_variance, 1, 2)

        layout.addLayout(grid)
        layout.addStretch()

    def set_results(self, results: SimulationResults):
        n_gens = results.n_generations
        n_ind = len(results.individuals)
        self.card_generations.set_value(str(n_gens))
        self.card_individuals.set_value(f"{n_ind:,}")

        if results.generations:
            last = results.generations[-1]
            first = results.generations[0]

            # Genetic gain
            if last.mean_tbv and first.mean_tbv:
                gain = last.mean_tbv[0] - first.mean_tbv[0]
                self.card_genetic_gain.set_value(
                    f"{gain:.3f}",
                    f"From {first.mean_tbv[0]:.3f} to {last.mean_tbv[0]:.3f}"
                )

            # Inbreeding
            self.card_inbreeding.set_value(
                f"{last.mean_inbreeding:.4f}",
                f"Rate: {last.mean_inbreeding / max(1, n_gens):.5f}/gen"
            )

            # Accuracy
            if last.selection_accuracy:
                self.card_accuracy.set_value(f"{last.selection_accuracy[0]:.3f}")

            # Variance
            if last.genetic_variance:
                self.card_variance.set_value(
                    f"{last.genetic_variance[0]:.3f}",
                    f"Initial: {first.genetic_variance[0]:.3f}" if first.genetic_variance else ""
                )
