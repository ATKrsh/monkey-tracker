"""
Event log table widget — shows recent detection events in a scrollable table.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont


class EventLogWidget(QWidget):
    MAX_ROWS = 300

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel("📋  EVENT LOG")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self._table = QTableWidget(0, 4)
        self._table.setObjectName("eventTable")
        self._table.setHorizontalHeaderLabels(["Time", "ID", "Label", "Conf"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setSortingEnabled(False)
        layout.addWidget(self._table)

    # ── Public ───────────────────────────────────────────────────

    def add_event(self, timestamp: str, track_id: int, label: str, confidence: float) -> None:
        row = 0
        self._table.insertRow(row)

        id_str = f"#{track_id}" if track_id >= 0 else "#?"
        conf_str = f"{confidence:.0%}"

        items = [timestamp, id_str, label, conf_str]
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, col, item)

        # Colour the ID cell with the same palette used in the overlay
        from app.tracker_overlay import _color_for
        if track_id >= 0:
            b, g, r = _color_for(track_id)  # BGR → QColor needs RGB
            color = QColor(r, g, b, 80)
            for col in range(4):
                item = self._table.item(row, col)
                if item:
                    item.setBackground(color)

        # Trim old rows
        while self._table.rowCount() > self.MAX_ROWS:
            self._table.removeRow(self._table.rowCount() - 1)

    def load_from_db(self, rows) -> None:
        """Populate table from DB rows [(timestamp, track_id, label, confidence)]."""
        self._table.setRowCount(0)
        for ts, tid, lbl, conf in rows:
            self.add_event(ts, int(tid), lbl, float(conf))
