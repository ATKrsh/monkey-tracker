"""
Windows desktop alerts via win11toast (optional — falls back to no-op).
"""
import time
import threading
from typing import Callable, Optional


try:
    from win11toast import notify as _win11_notify
    _TOAST_AVAILABLE = True
except ImportError:
    _TOAST_AVAILABLE = False


class AlertManager:
    """
    Fires a Windows toast notification when a new monkey enters the scene.
    Respects a cooldown to avoid spamming the user.
    """

    def __init__(self, cooldown_seconds: int = 30, sound_enabled: bool = True):
        self.cooldown_seconds = cooldown_seconds
        self.sound_enabled = sound_enabled
        self._enabled = True
        self._last_alert: float = 0.0
        self._lock = threading.Lock()

    # ── Public ───────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, v: bool) -> None:
        self._enabled = v

    def maybe_alert(self, count: int, new_ids: set) -> None:
        """Call every frame. Fires a notification if cooldown has elapsed."""
        if not self._enabled or not new_ids:
            return
        now = time.time()
        with self._lock:
            if now - self._last_alert < self.cooldown_seconds:
                return
            self._last_alert = now

        ids_str = ", ".join(f"#{i}" for i in sorted(new_ids))
        msg = f"{count} active | New: {ids_str}"
        threading.Thread(target=self._send, args=(msg,), daemon=True).start()

    # ── Internal ─────────────────────────────────────────────────

    def _send(self, body: str) -> None:
        if _TOAST_AVAILABLE:
            try:
                _win11_notify(
                    "🐒 Monkey Detected!",
                    body=body,
                    app_id="MonkeyTracker",
                    duration="short",
                    audio={"silent": "true"} if not self.sound_enabled else None,
                )
            except Exception:
                pass
        else:
            # Fallback — print to stdout (visible in terminal)
            print(f"[ALERT] 🐒 {body}")
