"""
Settings dialog for configuring camera, model, detection thresholds, and alerts.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QWidget, QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox,
    QPushButton, QLabel, QComboBox, QFileDialog, QGroupBox,
    QDialogButtonBox, QSlider
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from app.config import AppConfig, COCO_ANIMAL_IDS, COCO_LABEL_MAP


class SettingsDialog(QDialog):
    settings_saved = pyqtSignal(AppConfig)

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙  Settings — Monkey Tracker")
        self.setMinimumWidth(480)
        self.setMinimumHeight(420)
        self._config = config
        self._build_ui()
        self._populate(config)

    # ── Build ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._camera_tab(), "📷  Camera")
        tabs.addTab(self._detection_tab(), "🎯  Detection")
        tabs.addTab(self._display_tab(), "🖥  Display")
        tabs.addTab(self._alerts_tab(), "🔔  Alerts")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── Tabs ─────────────────────────────────────────────────────

    def _camera_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._cam_src = QLineEdit()
        self._cam_src.setPlaceholderText("0  |  rtsp://192.168.1.1/stream  |  /path/video.mp4")
        form.addRow("Camera Source:", self._cam_src)

        self._cam_w = QSpinBox(); self._cam_w.setRange(320, 3840); self._cam_w.setSingleStep(16)
        self._cam_h = QSpinBox(); self._cam_h.setRange(240, 2160); self._cam_h.setSingleStep(16)
        self._cam_fps = QSpinBox(); self._cam_fps.setRange(1, 120)

        wh = QHBoxLayout()
        wh.addWidget(self._cam_w); wh.addWidget(QLabel("×")); wh.addWidget(self._cam_h)
        form.addRow("Resolution:", wh)
        form.addRow("FPS Limit:", self._cam_fps)
        return w

    def _detection_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        # Model path
        model_row = QHBoxLayout()
        self._model_path = QLineEdit()
        self._model_path.setPlaceholderText("yolov8n.pt  or  /path/to/custom.pt")
        btn = QPushButton("Browse…")
        btn.setFixedWidth(80)
        btn.clicked.connect(self._browse_model)
        model_row.addWidget(self._model_path)
        model_row.addWidget(btn)
        form.addRow("Model (.pt):", model_row)

        hint = QLabel(
            "<small>YOLOv8 auto-downloads if file not found.<br>"
            "For monkey-specific detection, use a custom .pt from Roboflow.</small>"
        )
        hint.setWordWrap(True)
        hint.setObjectName("hintLabel")
        form.addRow("", hint)

        # Confidence
        self._conf = QDoubleSpinBox()
        self._conf.setRange(0.10, 0.99); self._conf.setSingleStep(0.05)
        form.addRow("Confidence:", self._conf)

        # IoU
        self._iou = QDoubleSpinBox()
        self._iou.setRange(0.10, 0.95); self._iou.setSingleStep(0.05)
        form.addRow("IoU (NMS):", self._iou)

        # Tracker
        self._tracker_combo = QComboBox()
        self._tracker_combo.addItems(["bytetrack.yaml", "botsort.yaml"])
        form.addRow("Tracker:", self._tracker_combo)

        # Target label
        self._target_label = QLineEdit()
        self._target_label.setPlaceholderText("Monkey")
        form.addRow("Display Label:", self._target_label)

        # Target class IDs (blank = all)
        self._class_ids = QLineEdit()
        self._class_ids.setPlaceholderText("blank = all  |  e.g.: 0,14,21 for custom model")
        form.addRow("Target Class IDs:", self._class_ids)

        coco_hint = QLabel(
            f"<small>COCO animals: {', '.join(f'{v}={k}' for k, v in COCO_LABEL_MAP.items())}</small>"
        )
        coco_hint.setWordWrap(True)
        coco_hint.setObjectName("hintLabel")
        form.addRow("", coco_hint)

        return w

    def _display_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._show_trails = QCheckBox("Show motion trails")
        self._trail_len = QSpinBox(); self._trail_len.setRange(5, 200)
        self._show_heatmap = QCheckBox("Show position heatmap")
        self._show_conf = QCheckBox("Show confidence %")
        self._show_fps = QCheckBox("Show FPS in status bar")
        self._bbox_thickness = QSpinBox(); self._bbox_thickness.setRange(1, 6)

        form.addRow(self._show_trails)
        form.addRow("Trail Length:", self._trail_len)
        form.addRow(self._show_heatmap)
        form.addRow(self._show_conf)
        form.addRow(self._show_fps)
        form.addRow("Box Thickness:", self._bbox_thickness)
        return w

    def _alerts_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._alerts_enabled = QCheckBox("Enable Windows toast notifications")
        self._alert_sound = QCheckBox("Play sound with alert")
        self._alert_cooldown = QSpinBox()
        self._alert_cooldown.setRange(5, 3600)
        self._alert_cooldown.setSuffix(" sec")
        self._save_detections = QCheckBox("Save detections to SQLite database")

        form.addRow(self._alerts_enabled)
        form.addRow(self._alert_sound)
        form.addRow("Alert Cooldown:", self._alert_cooldown)
        form.addRow(self._save_detections)
        return w

    # ── Populate / Save ──────────────────────────────────────────

    def _populate(self, c: AppConfig) -> None:
        # Camera
        self._cam_src.setText(str(c.camera_source))
        self._cam_w.setValue(c.camera_width)
        self._cam_h.setValue(c.camera_height)
        self._cam_fps.setValue(c.camera_fps_limit)
        # Detection
        self._model_path.setText(c.model_path)
        self._conf.setValue(c.confidence_threshold)
        self._iou.setValue(c.iou_threshold)
        idx = self._tracker_combo.findText(c.tracker)
        if idx >= 0:
            self._tracker_combo.setCurrentIndex(idx)
        self._target_label.setText(c.target_label)
        if c.target_class_ids:
            self._class_ids.setText(",".join(str(i) for i in c.target_class_ids))
        # Display
        self._show_trails.setChecked(c.show_trails)
        self._trail_len.setValue(c.trail_length)
        self._show_heatmap.setChecked(c.show_heatmap)
        self._show_conf.setChecked(c.show_confidence)
        self._show_fps.setChecked(c.show_fps)
        self._bbox_thickness.setValue(c.bbox_thickness)
        # Alerts
        self._alerts_enabled.setChecked(c.alerts_enabled)
        self._alert_sound.setChecked(c.alert_sound)
        self._alert_cooldown.setValue(c.alert_cooldown_seconds)
        self._save_detections.setChecked(c.save_detections)

    def _save(self) -> None:
        c = self._config
        # Camera
        src = self._cam_src.text().strip()
        c.camera_source = int(src) if src.isdigit() else src
        c.camera_width = self._cam_w.value()
        c.camera_height = self._cam_h.value()
        c.camera_fps_limit = self._cam_fps.value()
        # Detection
        c.model_path = self._model_path.text().strip() or "yolov8n.pt"
        c.confidence_threshold = self._conf.value()
        c.iou_threshold = self._iou.value()
        c.tracker = self._tracker_combo.currentText()
        c.target_label = self._target_label.text().strip() or "Monkey"
        ids_txt = self._class_ids.text().strip()
        if ids_txt:
            try:
                c.target_class_ids = [int(x.strip()) for x in ids_txt.split(",") if x.strip()]
            except ValueError:
                c.target_class_ids = None
        else:
            c.target_class_ids = None
        # Display
        c.show_trails = self._show_trails.isChecked()
        c.trail_length = self._trail_len.value()
        c.show_heatmap = self._show_heatmap.isChecked()
        c.show_confidence = self._show_conf.isChecked()
        c.show_fps = self._show_fps.isChecked()
        c.bbox_thickness = self._bbox_thickness.value()
        # Alerts
        c.alerts_enabled = self._alerts_enabled.isChecked()
        c.alert_sound = self._alert_sound.isChecked()
        c.alert_cooldown_seconds = self._alert_cooldown.value()
        c.save_detections = self._save_detections.isChecked()

        c.save()
        self.settings_saved.emit(c)
        self.accept()

    def _browse_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select YOLO model", "", "PyTorch (*.pt)")
        if path:
            self._model_path.setText(path)
