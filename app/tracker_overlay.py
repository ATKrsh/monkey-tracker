"""
Tracker overlay: draws bounding boxes, ID labels, motion trails,
and accumulates a heatmap on OpenCV frames.
"""
from __future__ import annotations
from collections import defaultdict, deque
from typing import List, Dict, Tuple, Deque
import cv2
import numpy as np

from app.detector import Detection


# Palette — 20 visually distinct BGR colours for track IDs
_PALETTE = [
    (0, 200, 255), (0, 255, 128), (255, 100, 0), (180, 0, 255),
    (255, 200, 0), (0, 255, 220), (255, 60, 120), (80, 255, 0),
    (255, 140, 0), (0, 160, 255), (200, 255, 0), (255, 0, 180),
    (0, 255, 80), (120, 80, 255), (255, 220, 80), (0, 255, 200),
    (255, 80, 0), (80, 200, 255), (255, 0, 80), (160, 255, 80),
]


def _color_for(track_id: int) -> Tuple[int, int, int]:
    return _PALETTE[track_id % len(_PALETTE)]


class OverlayRenderer:
    """
    Stateful renderer that keeps per-track motion trails
    and accumulates a positional heatmap.
    """

    def __init__(self, trail_length: int = 40):
        self.trail_length = trail_length
        # track_id → deque of (cx, cy) centres
        self._trails: Dict[int, Deque[Tuple[int, int]]] = defaultdict(
            lambda: deque(maxlen=trail_length)
        )
        self._heatmap: np.ndarray | None = None  # float32

    # ── Public API ───────────────────────────────────────────────

    def render(
        self,
        frame: np.ndarray,
        detections: List[Detection],
        *,
        show_trails: bool = True,
        show_heatmap: bool = False,
        heatmap_opacity: float = 0.35,
        show_confidence: bool = True,
        bbox_thickness: int = 2,
    ) -> np.ndarray:
        """Draw everything onto `frame` (in-place) and return it."""
        h, w = frame.shape[:2]

        # Initialise heatmap to frame size on first call / resize
        if self._heatmap is None or self._heatmap.shape[:2] != (h, w):
            self._heatmap = np.zeros((h, w), dtype=np.float32)

        # Update trails & heatmap
        active_ids = set()
        for det in detections:
            cx, cy = det.center
            self._trails[det.track_id].append((cx, cy))
            active_ids.add(det.track_id)
            # Gaussian splat on heatmap
            self._splat_heatmap(cx, cy)

        # Prune old trail entries for IDs not seen this frame
        # (keep them so trail fades naturally)

        # Draw heatmap underlay
        if show_heatmap and self._heatmap.max() > 0:
            frame = self._draw_heatmap(frame, heatmap_opacity)

        # Draw trails
        if show_trails:
            for tid, trail in self._trails.items():
                if len(trail) < 2:
                    continue
                color = _color_for(tid)
                pts = list(trail)
                for i in range(1, len(pts)):
                    alpha = i / len(pts)
                    c = tuple(int(v * alpha) for v in color)
                    cv2.line(frame, pts[i - 1], pts[i], c, 1, cv2.LINE_AA)

        # Draw bounding boxes + labels
        for det in detections:
            color = _color_for(det.track_id)
            x1, y1, x2, y2 = det.x1, det.y1, det.x2, det.y2

            # Box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, bbox_thickness, cv2.LINE_AA)

            # Corner accents
            self._draw_corners(frame, x1, y1, x2, y2, color, size=12, thickness=3)

            # Label pill background
            id_str = f"#{det.track_id}" if det.track_id >= 0 else "#?"
            conf_str = f" {det.confidence:.0%}" if show_confidence else ""
            label = f" {det.label} {id_str}{conf_str} "
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale, thickness = 0.55, 1
            (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            tag_y1 = max(y1 - th - baseline - 6, 0)
            cv2.rectangle(frame, (x1, tag_y1), (x1 + tw + 4, y1), color, -1)
            # Contrasting text
            brightness = 0.299 * color[2] + 0.587 * color[1] + 0.114 * color[0]
            text_color = (0, 0, 0) if brightness > 128 else (255, 255, 255)
            cv2.putText(frame, label, (x1 + 2, y1 - baseline - 2),
                        font, font_scale, text_color, thickness, cv2.LINE_AA)

        return frame

    def reset_heatmap(self) -> None:
        self._heatmap = None

    # ── Internals ────────────────────────────────────────────────

    def _draw_corners(self, frame, x1, y1, x2, y2, color, size=12, thickness=3):
        for sx, sy, dx, dy in [
            (x1, y1, 1, 1), (x2, y1, -1, 1),
            (x1, y2, 1, -1), (x2, y2, -1, -1),
        ]:
            cv2.line(frame, (sx, sy), (sx + dx * size, sy), color, thickness, cv2.LINE_AA)
            cv2.line(frame, (sx, sy), (sx, sy + dy * size), color, thickness, cv2.LINE_AA)

    def _splat_heatmap(self, cx: int, cy: int, radius: int = 40) -> None:
        h, w = self._heatmap.shape
        y, x = np.ogrid[0:h, 0:w]
        dist2 = (x - cx) ** 2 + (y - cy) ** 2
        blob = np.exp(-dist2 / (2 * (radius / 2) ** 2)).astype(np.float32)
        self._heatmap += blob
        # Prevent unbounded growth — soft normalise
        m = self._heatmap.max()
        if m > 1000:
            self._heatmap /= 2

    def _draw_heatmap(self, frame: np.ndarray, opacity: float) -> np.ndarray:
        hm = self._heatmap / (self._heatmap.max() + 1e-6)
        hm_uint8 = (hm * 255).astype(np.uint8)
        hm_color = cv2.applyColorMap(hm_uint8, cv2.COLORMAP_JET)
        return cv2.addWeighted(frame, 1.0, hm_color, opacity, 0)
