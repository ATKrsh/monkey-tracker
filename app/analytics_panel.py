"""
Analytics panel — right-side panel with:
  • Live detection-count time-series chart (pyqtgraph)
  • Active monkey ID list
  • Session statistics
  • Event log
"""
from __future__ import annotations
import time
from collections import deque
from typing import List, Set

import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from app.detector import Detection
from app.event_log import EventLogWidget
from app.database import Database

# ── pyqtgraph global config ─────────────────────────────────────
pg.setConfigOption("background", "#0a0e1a")
pg.setConfigOption("foreground", "#4a6fa5")
pg.setConfigOption("antialias", True)

_ACCENT = "#00d4ff"
_GREEN  = "#00ff9d"
_RED    = "#ff4466"
_TEXT   = "#c8d6e5"
_DIM    = "#4a6fa5"


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "0", accent: str = _ACCENT, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self._accent = accent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("statTitle")
        self._value_lbl = QLabel(value)
        self._value_lbl.setObjectName("statValue")
        self._value_lbl.setStyleSheet(f"color: {accent}; font-size: 22px; font-weight: 700;")

        layout.addWidget(self._title_lbl)
        layout.addWidget(self._value_lbl)

    def set_value(self, v: str) -> None:
        self._value_lbl.setText(v)


class ActiveMonkeysWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel("🐒  ACTIVE TRACKS")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setFixedHeight(90)
        self._inner = QWidget()
        self._inner_layout = QHBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(6)
        self._inner_layout.addStretch()
        self._scroll.setWidget(self._inner)
        layout.addWidget(self._scroll)

        self._badges: dict = {}

    def update_tracks(self, active_ids: Set[int]) -> None:
        existing = set(self._badges.keys())

        # Add new
        for tid in sorted(active_ids - existing):
            from app.tracker_overlay import _color_for
            b, g, r = _color_for(tid)
            badge = QLabel(f"#{tid}")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(52, 52)
            badge.setStyleSheet(
                f"background: rgba({r},{g},{b},0.20);"
                f"border: 2px solid rgb({r},{g},{b});"
                f"border-radius: 26px;"
                f"color: rgb({r},{g},{b});"
                f"font-weight: 700; font-size: 13px;"
            )
            self._inner_layout.insertWidget(self._inner_layout.count() - 1, badge)
            self._badges[tid] = badge

        # Remove gone
        for tid in existing - active_ids:
            badge = self._badges.pop(tid)
            self._inner_layout.removeWidget(badge)
            badge.deleteLater()


class AnalyticsPanel(QWidget):
    """Full right-side analytics panel."""

    HISTORY_LEN = 120   # seconds of chart history

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._count_history: deque = deque(maxlen=self.HISTORY_LEN)
        self._time_history:  deque = deque(maxlen=self.HISTORY_LEN)
        self._session_start = time.time()
        self._total_seen = 0
        self._peak = 0

        self._build_ui()

        # Refresh DB stats every 5 s
        self._db_timer = QTimer(self)
        self._db_timer.timeout.connect(self._refresh_db_stats)
        self._db_timer.start(5000)

    # ── Build UI ─────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # ── Stat cards row ───────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)

        self._card_active = StatCard("ACTIVE NOW", "0", _ACCENT)
        self._card_total  = StatCard("TOTAL SEEN", "0", _GREEN)
        self._card_peak   = StatCard("PEAK COUNT", "0", "#ffaa00")
        self._card_uptime = StatCard("SESSION TIME", "00:00", _DIM)

        for card in (self._card_active, self._card_total,
                     self._card_peak, self._card_uptime):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cards_row.addWidget(card)

        layout.addLayout(cards_row)

        # ── Time-series chart ────────────────────────────────────
        chart_title = QLabel("📈  DETECTION TIMELINE")
        chart_title.setObjectName("panelTitle")
        layout.addWidget(chart_title)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setFixedHeight(160)
        self._plot_widget.setLabel("left", "Count", color=_DIM)
        self._plot_widget.setLabel("bottom", "Seconds ago", color=_DIM)
        self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self._plot_widget.getAxis("left").setTextPen(_DIM)
        self._plot_widget.getAxis("bottom").setTextPen(_DIM)
        self._plot_widget.setMouseEnabled(x=False, y=False)

        pen = pg.mkPen(color=_ACCENT, width=2)
        self._plot_curve = self._plot_widget.plot([], [], pen=pen)
        fill = pg.FillBetweenItem(
            self._plot_curve,
            self._plot_widget.plot([0], [0]),
            brush=pg.mkBrush(0, 212, 255, 30)
        )
        self._plot_widget.addItem(fill)
        layout.addWidget(self._plot_widget)

        # ── Active tracks ────────────────────────────────────────
        self._active_widget = ActiveMonkeysWidget()
        layout.addWidget(self._active_widget)

        # ── Separator ────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("separator")
        layout.addWidget(sep)

        # ── Event log ────────────────────────────────────────────
        self._event_log = EventLogWidget()
        layout.addWidget(self._event_log, stretch=1)

        # Uptime refresh
        self._uptime_timer = QTimer(self)
        self._uptime_timer.timeout.connect(self._update_uptime)
        self._uptime_timer.start(1000)

    # ── Public update ────────────────────────────────────────────

    def update_detections(self, detections: List[Detection], new_ids: Set[int]) -> None:
        count = len(detections)
        now = time.time()

        self._count_history.append(count)
        self._time_history.append(now)
        if count > self._peak:
            self._peak = count

        self._card_active.set_value(str(count))
        self._card_peak.set_value(str(self._peak))

        # Update chart
        if len(self._time_history) > 1:
            t0 = self._time_history[-1]
            xs = [t - t0 for t in self._time_history]
            ys = list(self._count_history)
            self._plot_curve.setData(xs, ys)

        # Active tracks
        active_ids = {d.track_id for d in detections if d.track_id >= 0}
        self._active_widget.update_tracks(active_ids)

        # Log new entries
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        for det in detections:
            if det.track_id in new_ids:
                self._event_log.add_event(ts, det.track_id, det.label, det.confidence)

    # ── DB stats ─────────────────────────────────────────────────

    def _refresh_db_stats(self) -> None:
        total = self.db.total_count()
        self._total_seen = total
        self._card_total.set_value(str(total))

    # ── Uptime ───────────────────────────────────────────────────

    def _update_uptime(self) -> None:
        elapsed = int(time.time() - self._session_start)
        m, s = divmod(elapsed, 60)
        h, m = divmod(m, 60)
        if h:
            self._card_uptime.set_value(f"{h:02d}:{m:02d}:{s:02d}")
        else:
            self._card_uptime.set_value(f"{m:02d}:{s:02d}")
