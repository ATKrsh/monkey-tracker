"""
Main application window.
"""
from __future__ import annotations
import time
from typing import List, Set

import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QSplitter, QToolBar, QStatusBar,
    QMessageBox, QFileDialog, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize
from PyQt6.QtGui import QImage, QPixmap, QIcon, QAction, QFont, QColor

from app.config import AppConfig
from app.database import Database
from app.alerts import AlertManager
from app.camera_thread import CameraThread
from app.analytics_panel import AnalyticsPanel
from app.settings_dialog import SettingsDialog
from app.detector import Detection


class CameraView(QLabel):
    """Displays annotated OpenCV frames. Scales to available space."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(480, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName("cameraView")
        self._show_placeholder()

    def show_frame(self, frame: np.ndarray) -> None:
        h, w, ch = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.setPixmap(
            pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _show_placeholder(self) -> None:
        self.setText(
            "📷\n\nNo Camera Signal\n\n"
            "Press  ▶ Start  to begin\n"
            "or configure source in  ⚙ Settings"
        )
        self.setStyleSheet(
            "color: #4a6fa5; font-size: 18px; font-weight: 600;"
            "background: #080c15; border: 2px dashed #1e3a5f; border-radius: 8px;"
        )


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🐒  Monkey Tracker Pro")
        self.setMinimumSize(1200, 720)
        self.resize(1440, 860)

        self._config = AppConfig.load()
        self._db = Database(self._config.db_path)
        self._alerts = AlertManager(
            cooldown_seconds=self._config.alert_cooldown_seconds,
            sound_enabled=self._config.alert_sound,
        )
        self._camera_thread: CameraThread | None = None
        self._prev_ids: Set[int] = set()
        self._is_recording = False

        self._build_ui()
        self._build_toolbar()
        self._build_statusbar()
        self._load_stylesheet()

    # ── UI Construction ──────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setObjectName("mainSplitter")

        # ── Left: camera feed ────────────────────────────────────
        left_wrapper = QWidget()
        left_wrapper.setObjectName("leftPanel")
        left_layout = QVBoxLayout(left_wrapper)
        left_layout.setContentsMargins(8, 8, 4, 8)
        left_layout.setSpacing(6)

        # Rec indicator row
        rec_row = QHBoxLayout()
        self._rec_dot = QLabel("●")
        self._rec_dot.setObjectName("recDotOff")
        self._cam_label = QLabel("CAMERA FEED")
        self._cam_label.setObjectName("feedTitle")
        rec_row.addWidget(self._rec_dot)
        rec_row.addWidget(self._cam_label)
        rec_row.addStretch()
        self._count_badge = QLabel("0 DETECTED")
        self._count_badge.setObjectName("countBadge")
        rec_row.addWidget(self._count_badge)
        left_layout.addLayout(rec_row)

        self._camera_view = CameraView()
        left_layout.addWidget(self._camera_view, stretch=1)

        splitter.addWidget(left_wrapper)

        # ── Right: analytics ─────────────────────────────────────
        right_wrapper = QWidget()
        right_wrapper.setObjectName("rightPanel")
        right_wrapper.setMinimumWidth(340)
        right_wrapper.setMaximumWidth(460)
        right_layout = QVBoxLayout(right_wrapper)
        right_layout.setContentsMargins(4, 8, 8, 8)

        self._analytics = AnalyticsPanel(self._db)
        right_layout.addWidget(self._analytics)

        splitter.addWidget(right_wrapper)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Controls")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setObjectName("mainToolBar")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        # App title
        title = QLabel("  🐒  MONKEY TRACKER PRO  ")
        title.setObjectName("appTitle")
        tb.addWidget(title)

        spacer1 = QWidget(); spacer1.setFixedWidth(20)
        tb.addWidget(spacer1)

        self._action_start = QAction("▶  Start", self)
        self._action_start.setToolTip("Start camera and detection")
        self._action_start.triggered.connect(self._on_start)
        tb.addAction(self._action_start)

        self._action_stop = QAction("⏹  Stop", self)
        self._action_stop.setToolTip("Stop detection")
        self._action_stop.setEnabled(False)
        self._action_stop.triggered.connect(self._on_stop)
        tb.addAction(self._action_stop)

        tb.addSeparator()

        self._action_heatmap = QAction("🔥  Heatmap", self)
        self._action_heatmap.setCheckable(True)
        self._action_heatmap.setChecked(self._config.show_heatmap)
        self._action_heatmap.triggered.connect(self._toggle_heatmap)
        tb.addAction(self._action_heatmap)

        self._action_trails = QAction("〰  Trails", self)
        self._action_trails.setCheckable(True)
        self._action_trails.setChecked(self._config.show_trails)
        self._action_trails.triggered.connect(self._toggle_trails)
        tb.addAction(self._action_trails)

        tb.addSeparator()

        action_settings = QAction("⚙  Settings", self)
        action_settings.triggered.connect(self._open_settings)
        tb.addAction(action_settings)

        action_export = QAction("📤  Export DB", self)
        action_export.setToolTip("Export detection log to CSV")
        action_export.triggered.connect(self._export_csv)
        tb.addAction(action_export)

        action_about = QAction("ℹ  About", self)
        action_about.triggered.connect(self._show_about)
        tb.addAction(action_about)

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        sb.setObjectName("mainStatusBar")

        self._sb_camera = QLabel("📷  Not started")
        self._sb_model  = QLabel(f"🎯  {self._config.model_path}")
        self._sb_fps    = QLabel("🔄  — FPS")
        self._sb_status = QLabel("⏸  Idle")

        for lbl in (self._sb_camera, self._sb_model, self._sb_fps, self._sb_status):
            lbl.setObjectName("statusLabel")
            sb.addPermanentWidget(lbl)
            sep = QLabel("|"); sep.setObjectName("statusSep")
            sb.addPermanentWidget(sep)

    def _load_stylesheet(self) -> None:
        import os
        qss_path = os.path.join(os.path.dirname(__file__), "..", "assets", "style.qss")
        try:
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            pass  # Fallback to system theme

    # ── Camera control ───────────────────────────────────────────

    def _on_start(self) -> None:
        if self._camera_thread and self._camera_thread.isRunning():
            return

        self._camera_view.setStyleSheet("")  # Remove placeholder styling
        self._camera_view.setText("")

        self._camera_thread = CameraThread(self._config, self._db, self._alerts)
        self._camera_thread.frame_ready.connect(self._on_frame)
        self._camera_thread.fps_updated.connect(self._on_fps)
        self._camera_thread.status_changed.connect(self._on_status)
        self._camera_thread.error_occurred.connect(self._on_error)
        self._camera_thread.start()

        self._action_start.setEnabled(False)
        self._action_stop.setEnabled(True)
        self._rec_dot.setObjectName("recDotOn")
        self._rec_dot.setStyleSheet("color: #ff4444; font-size: 14px;")
        self._sb_camera.setText(f"📷  {self._config.camera_source}")

    def _on_stop(self) -> None:
        if self._camera_thread:
            self._camera_thread.stop()
            self._camera_thread = None

        self._action_start.setEnabled(True)
        self._action_stop.setEnabled(False)
        self._rec_dot.setObjectName("recDotOff")
        self._rec_dot.setStyleSheet("color: #4a6fa5; font-size: 14px;")
        self._camera_view._show_placeholder()
        self._sb_status.setText("⏸  Stopped")

    # ── Slots ────────────────────────────────────────────────────

    @pyqtSlot(np.ndarray, list)
    def _on_frame(self, frame: np.ndarray, detections: List[Detection]) -> None:
        self._camera_view.show_frame(frame)

        current_ids = {d.track_id for d in detections if d.track_id >= 0}
        new_ids = current_ids - self._prev_ids
        self._prev_ids = current_ids

        count = len(detections)
        self._count_badge.setText(f"{count} DETECTED")
        if count > 0:
            self._count_badge.setStyleSheet("color: #00d4ff; font-weight: 700;")
        else:
            self._count_badge.setStyleSheet("color: #4a6fa5; font-weight: 600;")

        self._analytics.update_detections(detections, new_ids)

    @pyqtSlot(float)
    def _on_fps(self, fps: float) -> None:
        if self._config.show_fps:
            color = "#00ff9d" if fps >= 20 else "#ffaa00" if fps >= 10 else "#ff4444"
            self._sb_fps.setText(f"🔄  {fps:.1f} FPS")
            self._sb_fps.setStyleSheet(f"color: {color};")

    @pyqtSlot(str)
    def _on_status(self, msg: str) -> None:
        self._sb_status.setText(f"⚡  {msg}")

    @pyqtSlot(str)
    def _on_error(self, msg: str) -> None:
        self._sb_status.setText(f"⚠  {msg}")
        self._sb_status.setStyleSheet("color: #ff4466;")

    # ── Actions ──────────────────────────────────────────────────

    def _toggle_heatmap(self, checked: bool) -> None:
        self._config.show_heatmap = checked

    def _toggle_trails(self, checked: bool) -> None:
        self._config.show_trails = checked

    def _open_settings(self) -> None:
        was_running = self._camera_thread and self._camera_thread.isRunning()
        if was_running:
            self._on_stop()

        dlg = SettingsDialog(self._config, self)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()

        if was_running:
            self._on_start()

    @pyqtSlot(AppConfig)
    def _on_settings_saved(self, config: AppConfig) -> None:
        self._config = config
        self._alerts.cooldown_seconds = config.alert_cooldown_seconds
        self._alerts.enabled = config.alerts_enabled
        self._alerts.sound_enabled = config.alert_sound
        self._sb_model.setText(f"🎯  {config.model_path}")
        self._action_heatmap.setChecked(config.show_heatmap)
        self._action_trails.setChecked(config.show_trails)

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Detection Log", "monkey_detections.csv", "CSV (*.csv)"
        )
        if not path:
            return
        rows = self._db.fetch_recent(limit=100000)
        with open(path, "w") as f:
            f.write("timestamp,track_id,label,confidence\n")
            for row in rows:
                f.write(",".join(str(v) for v in row) + "\n")
        QMessageBox.information(self, "Exported", f"Saved {len(rows)} events to:\n{path}")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Monkey Tracker Pro",
            "<h3>🐒 Monkey Tracker Pro</h3>"
            "<p>Real-time CCTV wildlife detection dashboard.</p>"
            "<p><b>Engine:</b> YOLOv8 + ByteTrack<br>"
            "<b>UI:</b> PyQt6<br>"
            "<b>Storage:</b> SQLite</p>"
            "<p>Place a custom <code>.pt</code> model file (trained on primates)<br>"
            "and set its path in <b>Settings → Detection</b> for best accuracy.</p>"
        )

    # ── Lifecycle ────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._on_stop()
        self._db.close()
        self._config.save()
        event.accept()
