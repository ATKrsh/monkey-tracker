"""
App-wide configuration — persisted to config.json between sessions.
"""
import json
import os
from typing import Union, Optional, List


# COCO class IDs for animals (YOLOv8 default model)
# Monkeys are NOT in COCO-80; use a custom model or detect all wildlife.
COCO_ANIMAL_IDS = {14, 15, 16, 17, 18, 19, 20, 21, 22, 23}
COCO_LABEL_MAP = {
    14: "bird", 15: "cat", 16: "dog", 17: "horse",
    18: "sheep", 19: "cow", 20: "elephant", 21: "bear",
    22: "zebra", 23: "giraffe",
}

# Roboflow / HuggingFace public monkey detection model info
MONKEY_MODEL_INFO = {
    "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8x.pt",
    "description": "YOLOv8x (COCO) — detects all wildlife. "
                   "For dedicated monkey detection, place a custom .pt file in the project folder "
                   "and set model_path in Settings.",
}

CONFIG_FILE = "config.json"


class AppConfig:
    def __init__(self):
        # ── Camera ──────────────────────────────────────────────
        self.camera_source: Union[int, str] = 0   # 0 = USB, or "rtsp://..." or "/path/video.mp4"
        self.camera_width: int = 1280
        self.camera_height: int = 720
        self.camera_fps_limit: int = 30

        # ── Detection ───────────────────────────────────────────
        self.model_path: str = "yolov8n.pt"       # local .pt file or auto-download name
        self.confidence_threshold: float = 0.40
        self.iou_threshold: float = 0.45
        self.tracker: str = "bytetrack.yaml"       # "bytetrack.yaml" or "botsort.yaml"

        # Class IDs to treat as "monkey / wildlife target"
        # None  → all detectable classes
        # list  → only these COCO IDs (or custom model class IDs)
        self.target_class_ids: Optional[List[int]] = None
        # Human-readable label that overrides model class names in the UI
        self.target_label: str = "Monkey"

        # ── Alerts ──────────────────────────────────────────────
        self.alerts_enabled: bool = True
        self.alert_cooldown_seconds: int = 30
        self.alert_sound: bool = True

        # ── Recording / Logging ─────────────────────────────────
        self.save_detections: bool = True
        self.db_path: str = "data/monkey_tracker.db"

        # ── Display ─────────────────────────────────────────────
        self.show_trails: bool = True
        self.trail_length: int = 40
        self.show_heatmap: bool = False
        self.heatmap_opacity: float = 0.35
        self.show_confidence: bool = True
        self.show_fps: bool = True
        self.bbox_thickness: int = 2

    # ── Persistence ─────────────────────────────────────────────

    def save(self) -> None:
        data = {k: v for k, v in self.__dict__.items()}
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls) -> "AppConfig":
        cfg = cls()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
            except Exception:
                pass  # Corrupt config — use defaults
        return cfg
