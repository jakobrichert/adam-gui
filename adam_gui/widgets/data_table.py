"""Sortable data table widget with export support."""

from adam_gui.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QFileDialog, Signal, Qt,
)


class DataTable(QWidget):
    """A sortable, filterable table for displaying tabular data."""

    row_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[list] = []
        self._headers: list[str] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Info bar
        top = QHBoxLayout()
        self.info_label = QLabel("0 rows")
        top.addWidget(self.info_label)
        top.addStretch()

        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setFixedWidth(100)
        self.export_btn.clicked.connect(self._export_csv)
        top.addWidget(self.export_btn)

        layout.addLayout(top)

        # Table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.currentCellChanged.connect(self._on_row_changed)
        layout.addWidget(self.table)

    def set_data(self, headers: list[str], data: list[list]):
        """Populate the table with data."""
        self._headers = headers
        self._data = data

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(data))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        for r, row in enumerate(data):
            for c, val in enumerate(row):
                item = QTableWidgetItem()
                if isinstance(val, (int, float)):
                    item.setData(Qt.ItemDataRole.DisplayRole, val)
                else:
                    item.setText(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, c, item)

        self.table.setSortingEnabled(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        if headers:
            header.setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)

        self.info_label.setText(f"{len(data)} rows")

    def filter_rows(self, text: str):
        """Show only rows containing the filter text."""
        text = text.lower()
        for r in range(self.table.rowCount()):
            visible = not text or any(
                text in (self.table.item(r, c).text().lower() if self.table.item(r, c) else "")
                for c in range(self.table.columnCount())
            )
            self.table.setRowHidden(r, not visible)

    def _on_row_changed(self, row: int, _col, _prev_row, _prev_col):
        if row >= 0:
            self.row_selected.emit(row)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV Files (*.csv)")
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write(",".join(self._headers) + "\n")
            for row in self._data:
                f.write(",".join(str(v) for v in row) + "\n")

    def clear(self):
        self.table.setRowCount(0)
        self._data = []
        self.info_label.setText("0 rows")
