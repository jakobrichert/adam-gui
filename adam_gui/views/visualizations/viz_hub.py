"""Visualization hub - gallery launcher for 3D views."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QFrame, Qt, Signal, QSizePolicy,
)
from adam_gui.models.results import SimulationResults


class VizCard(QFrame):
    """Clickable card for a visualization type."""

    clicked = Signal()

    def __init__(self, title: str, description: str, icon_text: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.04);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.06);
                padding: 20px;
            }
            QFrame:hover {
                background-color: rgba(255, 255, 255, 0.08);
                border-color: rgba(137, 180, 250, 0.3);
            }
        """)
        self.setMinimumSize(250, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        icon_label = QLabel(icon_text)
        icon_label.setStyleSheet("font-size: 36px; background: transparent;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setObjectName("muted")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

    def mousePressEvent(self, event):
        self.clicked.emit()


class VizHubView(QWidget):
    """Gallery of visualization types."""

    open_pedigree = Signal()
    open_chromosome = Signal()
    open_pca = Signal()
    open_landscape = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Header
        top = QHBoxLayout()
        title = QLabel("3D Visualizations")
        title.setObjectName("heading")
        top.addWidget(title)
        top.addStretch()

        top.addWidget(QLabel("Data source:"))
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(200)
        self.source_combo.setEnabled(False)
        top.addWidget(self.source_combo)
        layout.addLayout(top)

        # No data message
        self.no_data_label = QLabel(
            "No simulation results available. Generate demo data first."
        )
        self.no_data_label.setObjectName("subheading")
        self.no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.no_data_label)

        # Card grid
        self.card_grid = QWidget()
        grid = QGridLayout(self.card_grid)
        grid.setSpacing(16)

        card_pedigree = VizCard(
            "Pedigree Network",
            "3D family tree showing breeding flow and genetic contributions across generations",
            "\u26B6",  # ⚶
        )
        card_pedigree.clicked.connect(self.open_pedigree.emit)
        grid.addWidget(card_pedigree, 0, 0)

        card_chromosome = VizCard(
            "Chromosome Maps",
            "3D karyogram with QTL positions, marker density, and allele frequencies",
            "\u29BF",  # ⦿
        )
        card_chromosome.clicked.connect(self.open_chromosome.emit)
        grid.addWidget(card_chromosome, 0, 1)

        card_pca = VizCard(
            "Population PCA",
            "3D scatter of individuals in principal component space across generations",
            "\u2B22",  # ⬢
        )
        card_pca.clicked.connect(self.open_pca.emit)
        grid.addWidget(card_pca, 1, 0)

        card_landscape = VizCard(
            "Genetic Gain Landscape",
            "3D surface showing breeding progress, variance, and inbreeding over time",
            "\u25B3",  # △
        )
        card_landscape.clicked.connect(self.open_landscape.emit)
        grid.addWidget(card_landscape, 1, 1)

        self.card_grid.setVisible(False)
        layout.addWidget(self.card_grid, stretch=1)

    def set_results(self, results: SimulationResults):
        self._results = results
        label = f"{results.parameters.name if results.parameters else 'Run'} ({results.run_id[:8]})"
        self.source_combo.addItem(label)
        self.source_combo.setEnabled(True)
        self.no_data_label.setVisible(False)
        self.card_grid.setVisible(True)

    @property
    def current_results(self) -> SimulationResults | None:
        return self._results
