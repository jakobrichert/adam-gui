"""Fast, numpy-backed table view.

Filtering and sorting happen on numpy index arrays inside the model, so tables
with tens of thousands of rows update instantly (a QSortFilterProxyModel would
call back into Python for every comparison).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

from adam_gui.qt_compat import (
    QAbstractTableModel, QColor, QFont, QHeaderView, QModelIndex, QTableView, Qt,
    QVBoxLayout, QWidget, Signal,
)
from adam_gui.themes import palette, theme


@dataclass
class Column:
    key: str
    title: str
    values: np.ndarray
    fmt: str | Callable[[object], str] = "{}"
    align: str = "right"               # "left" | "right" | "center"
    tooltip: str = ""
    width: int | None = None
    style: Callable[[int], str | None] | None = field(default=None)  # row -> "accent"|"muted"|"bold"|None
    decoration: Callable[[int], object] | None = None                  # row -> QIcon | QColor | None

    def text(self, row: int) -> str:
        v = self.values[row]
        if isinstance(v, (float, np.floating)) and not np.isfinite(v):
            return "—"
        text = self.fmt(v) if callable(self.fmt) else self.fmt.format(v)
        if text.startswith("-") and text[1:] and not text[1:].strip("0.,"):
            text = text[1:]  # "-0.000" -> "0.000"
        return text


class ArrayTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns: list[Column] = []
        self._n = 0
        self._mask: np.ndarray | None = None
        self._order: np.ndarray = np.arange(0)
        self._rows: np.ndarray = np.arange(0)
        self._sort_col = -1
        self._sort_desc = False
        self._bold = QFont()
        self._bold.setBold(True)
        theme().changed.connect(self._repaint)

    # ------------------------------------------------------------ data
    def set_columns(self, columns: Sequence[Column]):
        self.beginResetModel()
        self._columns = list(columns)
        self._n = len(columns[0].values) if columns else 0
        self._mask = None
        self._order = np.arange(self._n)
        self._sort_col = -1
        self._rows = self._order
        self.endResetModel()

    @property
    def columns(self) -> list[Column]:
        return self._columns

    @property
    def total_rows(self) -> int:
        return self._n

    def visible_rows(self) -> np.ndarray:
        """Source row indices in display order."""
        return self._rows

    def source_row(self, row: int) -> int:
        return int(self._rows[row])

    def set_mask(self, mask: np.ndarray | None):
        self.beginResetModel()
        self._mask = mask
        self._apply()
        self.endResetModel()

    def _apply(self):
        order = self._order
        if self._mask is not None:
            order = order[self._mask[order]]
        self._rows = order

    # ------------------------------------------------------------ Qt model
    def rowCount(self, parent=QModelIndex()):  # noqa: B008 - Qt signature
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):  # noqa: B008 - Qt signature
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        col = self._columns[index.column()]
        row = int(self._rows[index.row()])
        if role == Qt.ItemDataRole.DisplayRole:
            return col.text(row)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            h = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter}.get(
                col.align, Qt.AlignmentFlag.AlignRight)
            return int(h | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.UserRole:
            return col.values[row]
        if role == Qt.ItemDataRole.DecorationRole and col.decoration is not None:
            return col.decoration(row)
        if col.style is not None and role in (Qt.ItemDataRole.ForegroundRole, Qt.ItemDataRole.FontRole):
            s = col.style(row)
            if not s:
                return None
            p = palette()
            if role == Qt.ItemDataRole.ForegroundRole:
                color = {"accent": p.accent, "muted": p.text_faint, "danger": p.danger,
                         "warning": p.warning, "bold": p.text}.get(s)
                return QColor(color) if color else None
            if role == Qt.ItemDataRole.FontRole and s in ("accent", "bold"):
                return self._bold
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal or section >= len(self._columns):
            return None
        col = self._columns[section]
        if role == Qt.ItemDataRole.DisplayRole:
            return col.title
        if role == Qt.ItemDataRole.ToolTipRole:
            return col.tooltip or col.title
        if role == Qt.ItemDataRole.TextAlignmentRole:
            h = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter}.get(
                col.align, Qt.AlignmentFlag.AlignRight)
            return int(h | Qt.AlignmentFlag.AlignVCenter)
        return None

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        if column < 0 or column >= len(self._columns):
            return
        self.layoutAboutToBeChanged.emit()
        values = self._columns[column].values
        if values.dtype.kind in "fiub":
            keys = values.astype(float)
            keys = np.where(np.isfinite(keys), keys, np.inf)
            idx = np.argsort(keys, kind="stable")
        else:
            idx = np.argsort(values.astype(str), kind="stable")
        if order == Qt.SortOrder.DescendingOrder:
            idx = idx[::-1]
        self._order = idx
        self._sort_col = column
        self._sort_desc = order == Qt.SortOrder.DescendingOrder
        self._apply()
        self.layoutChanged.emit()

    def _repaint(self, *_):
        if self._rows.size and self._columns:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, len(self._columns) - 1))

    # ------------------------------------------------------------ export
    def export_csv(self, path: str, visible_columns: Sequence[int] | None = None):
        cols = [self._columns[i] for i in (visible_columns if visible_columns is not None
                                           else range(len(self._columns)))]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([c.title for c in cols])
            for r in self._rows:
                row = []
                for c in cols:
                    v = c.values[int(r)]
                    if isinstance(v, (np.floating, float)):
                        row.append("" if not np.isfinite(v) else f"{float(v):.6g}")
                    elif isinstance(v, (np.bool_, bool)):
                        row.append("1" if v else "0")
                    else:
                        row.append(str(v))
                writer.writerow(row)


class DataTable(QWidget):
    """QTableView around an ``ArrayTableModel`` with sensible defaults."""

    row_activated = Signal(int)  # source row

    def __init__(self, parent=None, row_height: int = 28):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.model = ArrayTableModel(self)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSortingEnabled(True)
        self.view.setAlternatingRowColors(True)
        self.view.setShowGrid(False)
        self.view.setWordWrap(False)
        self.view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.view.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.view.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        vh = self.view.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vh.setDefaultSectionSize(row_height)
        hh = self.view.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setSectionsMovable(True)
        hh.setStretchLastSection(False)
        hh.setSortIndicatorShown(True)
        hh.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.view.doubleClicked.connect(lambda idx: self.row_activated.emit(self.model.source_row(idx.row())))
        lay.addWidget(self.view)

    def set_columns(self, columns: Sequence[Column]):
        header = self.view.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        old_key = self.model.columns[sort_col].key if 0 <= sort_col < len(self.model.columns) else None
        self.model.set_columns(columns)
        fm = self.view.fontMetrics()
        for i, c in enumerate(columns):
            n = len(c.values)
            rows = np.unique(np.linspace(0, n - 1, min(n, 60)).astype(int)) if n else []
            widest = max((fm.horizontalAdvance(c.text(int(r))) for r in rows), default=0)
            w = c.width or max(fm.horizontalAdvance(c.title) + 34, widest + 34, 64)
            self.view.setColumnWidth(i, w)
        keys = [c.key for c in columns]
        if old_key in keys:
            self.view.sortByColumn(keys.index(old_key), sort_order)
        else:
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)

    def set_mask(self, mask: np.ndarray | None):
        self.model.set_mask(mask)

    def set_column_visible(self, key: str, visible: bool):
        for i, c in enumerate(self.model.columns):
            if c.key == key:
                self.view.setColumnHidden(i, not visible)

    def visible_column_indices(self) -> list[int]:
        return [i for i in range(len(self.model.columns)) if not self.view.isColumnHidden(i)]

    def export_csv(self, path: str):
        self.model.export_csv(path, self.visible_column_indices())

    def row_count(self) -> int:
        return self.model.rowCount()
