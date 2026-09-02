"""
YOLOv8 detector + ByteTrack multi-object tracker wrapper.
Runs inside CameraThread — do not call from the main/UI thread.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Set
import numpy as np


@dataclass
class Detection:
    track_id: int
    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def center(self):
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    @property
    def area(self):
        return (self.x2 - self.x1) * (self.y2 - self.y1)


class MonkeyDetector:
    """
    Wraps Ultralytics YOLO with ByteTrack.

    Parameters
    ----------
    model_path       : YOLO model name or path (e.g. "yolov8n.pt", "custom.pt")
    confidence       : minimum detection confidence
    iou              : NMS IoU threshold
    target_class_ids : set of COCO (or custom) class IDs to keep; None = keep all
    target_label     : display label override (e.g. "Monkey")
    tracker          : tracker config ("bytetrack.yaml" or "botsort.yaml")
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence: float = 0.40,
        iou: float = 0.45,
        target_class_ids: Optional[Set[int]] = None,
        target_label: str = "Monkey",
        tracker: str = "bytetrack.yaml",
    ):
        from ultralytics import YOLO  # lazy import — may download model on first call
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.iou = iou
        self.target_class_ids = target_class_ids  # None → keep all
        self.target_label = target_label
        self.tracker = tracker
        self._model_names = self.model.names  # {0: "person", 1: "bicycle", ...}

    # ── Main interface ───────────────────────────────────────────

    def detect_and_track(self, frame: np.ndarray) -> List[Detection]:
        """
        Run inference + tracking on a single BGR frame.
        Returns a list of Detection objects for matched targets.
        """
        results = self.model.track(
            frame,
            persist=True,
            conf=self.confidence,
            iou=self.iou,
            tracker=self.tracker,
            verbose=False,
        )

        detections: List[Detection] = []
        if results is None or len(results) == 0:
            return detections

        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return detections

        boxes = result.boxes
        for i in range(len(boxes)):
            # Track ID (may be None if tracker loses the object)
            tid_tensor = boxes.id
            track_id = int(tid_tensor[i].item()) if tid_tensor is not None else -1

            cls_id = int(boxes.cls[i].item())
            conf = float(boxes.conf[i].item())

            # Filter by target classes if configured
            if self.target_class_ids is not None and cls_id not in self.target_class_ids:
                continue

            # Bounding box in pixel coords
            xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
            x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])

            # Use model class name or override label
            raw_label = self._model_names.get(cls_id, str(cls_id))
            label = self.target_label if self.target_class_ids is not None else raw_label

            detections.append(Detection(
                track_id=track_id,
                label=label,
                confidence=conf,
                x1=x1, y1=y1, x2=x2, y2=y2,
            ))

        return detections

    def update_settings(
        self,
        confidence: float,
        iou: float,
        target_class_ids: Optional[Set[int]],
        target_label: str,
    ) -> None:
        self.confidence = confidence
        self.iou = iou
        self.target_class_ids = target_class_ids
        self.target_label = target_label
