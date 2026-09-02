"""
QThread that captures frames from camera/file/RTSP and runs detection.
Emits annotated frames and detection data back to the main thread.
"""
from __future__ import annotations
import time
from collections import deque
from typing import List, Optional, Union, Set

import cv2
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

from app.detector import Detection, MonkeyDetector
from app.tracker_overlay import OverlayRenderer
from app.database import Database, DetectionEvent
from app.alerts import AlertManager
from app.config import AppConfig


class CameraThread(QThread):
    # ── Signals ─────────────────────────────────────────────────
    frame_ready = pyqtSignal(np.ndarray, list)       # (annotated BGR frame, [Detection])
    fps_updated = pyqtSignal(float)
    status_changed = pyqtSignal(str)                  # status messages
    error_occurred = pyqtSignal(str)

    def __init__(self, config: AppConfig, db: Database, alerts: AlertManager):
        super().__init__()
        self.config = config
        self.db = db
        self.alerts = alerts
        self._running = False
        self._detector: Optional[MonkeyDetector] = None
        self._overlay = OverlayRenderer(trail_length=config.trail_length)
        self._fps_buf: deque = deque(maxlen=30)
        self._seen_ids: Set[int] = set()

    # ── Control ──────────────────────────────────────────────────

    def stop(self) -> None:
        self._running = False
        self.wait(3000)

    def reload_detector(self) -> None:
        """Called from main thread to rebuild the detector after settings change."""
        self._detector = None  # triggers re-init in run loop

    # ── Thread body ──────────────────────────────────────────────

    def run(self) -> None:
        self._running = True
        self.status_changed.emit("Initialising detector…")

        try:
            self._detector = self._build_detector()
        except Exception as exc:
            self.error_occurred.emit(f"Model load failed: {exc}")
            return

        self.status_changed.emit(f"Opening camera: {self.config.camera_source}")

        src = self.config.camera_source
        cap_src = int(src) if isinstance(src, str) and src.isdigit() else src
        cap = cv2.VideoCapture(cap_src)
        if not cap.isOpened():
            self.error_occurred.emit(f"Cannot open camera: {src}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera_height)
        cap.set(cv2.CAP_PROP_FPS, self.config.camera_fps_limit)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # minimal buffer lag

        self.status_changed.emit("Running")

        while self._running:
            t0 = time.perf_counter()

            ret, frame = cap.read()
            if not ret:
                # End of file or camera error — loop video files
                if isinstance(cap_src, str):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                self.error_occurred.emit("Camera read error — retrying…")
                time.sleep(0.5)
                continue

            # ── Detection ────────────────────────────────────────
            try:
                if self._detector is None:
                    self._detector = self._build_detector()
                detections: List[Detection] = self._detector.detect_and_track(frame)
            except Exception as exc:
                detections = []
                self.error_occurred.emit(f"Detection error: {exc}")

            # ── Logging + Alerts ─────────────────────────────────
            current_ids = {d.track_id for d in detections if d.track_id >= 0}
            new_ids = current_ids - self._seen_ids
            self._seen_ids = current_ids

            if self.config.save_detections:
                for det in detections:
                    if det.track_id in new_ids:   # log only on first appearance
                        self.db.log(DetectionEvent(
                            det.track_id, det.label, det.confidence,
                            det.x1, det.y1, det.x2, det.y2
                        ))

            self.alerts.maybe_alert(len(current_ids), new_ids)

            # ── Overlay rendering ────────────────────────────────
            annotated = self._overlay.render(
                frame,
                detections,
                show_trails=self.config.show_trails,
                show_heatmap=self.config.show_heatmap,
                heatmap_opacity=self.config.heatmap_opacity,
                show_confidence=self.config.show_confidence,
                bbox_thickness=self.config.bbox_thickness,
            )

            # ── FPS tracking ─────────────────────────────────────
            elapsed = time.perf_counter() - t0
            self._fps_buf.append(elapsed)
            avg = sum(self._fps_buf) / len(self._fps_buf)
            fps = 1.0 / avg if avg > 0 else 0.0
            self.fps_updated.emit(fps)

            self.frame_ready.emit(annotated, detections)

        cap.release()
        self.status_changed.emit("Stopped")

    # ── Helpers ──────────────────────────────────────────────────

    def _build_detector(self) -> MonkeyDetector:
        target_ids = (
            set(self.config.target_class_ids)
            if self.config.target_class_ids is not None
            else None
        )
        return MonkeyDetector(
            model_path=self.config.model_path,
            confidence=self.config.confidence_threshold,
            iou=self.config.iou_threshold,
            target_class_ids=target_ids,
            target_label=self.config.target_label,
            tracker=self.config.tracker,
        )
