"""Combo box bound to the session's run list and current run."""

from __future__ import annotations

from adam_gui.qt_compat import QComboBox, QSizePolicy
from adam_gui.session import Session


class RunSelector(QComboBox):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._syncing = False
        self.setMinimumWidth(240)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setToolTip("Simulation run shown on this page")
        session.runs_changed.connect(self._rebuild)
        session.current_run_changed.connect(self._select_current)
        self.currentIndexChanged.connect(self._on_index)
        self._rebuild()

    def _rebuild(self):
        self._syncing = True
        self.clear()
        for run in self._session.runs:
            self.addItem(self._session.label(run), run.run_id)
            self.setItemData(self.count() - 1, Session.describe(run), 3)  # ToolTipRole
        self.setEnabled(self.count() > 0)
        if self.count() == 0:
            self.addItem("No runs yet")
            self.setEnabled(False)
        self._syncing = False
        self._select_current(self._session.current)

    def _select_current(self, run):
        self._syncing = True
        if run is not None:
            idx = self.findData(run.run_id)
            if idx >= 0:
                self.setCurrentIndex(idx)
        self._syncing = False

    def _on_index(self, index: int):
        if self._syncing or index < 0:
            return
        run_id = self.itemData(index)
        if run_id:
            self._session.set_current(run_id)
