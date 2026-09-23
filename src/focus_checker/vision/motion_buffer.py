"""Motion gate: only keep frames where the scene visibly changed.

Compares each frame to the last captured one (shrunk, grayscale, blurred) and
captures when enough pixels changed. Cheap, no ML involved. Meant to decide
when a frame is worth sending to Gemini; main.py imports it but currently
uses a fixed timer instead. See tests/test_motion_buffer.py for a live demo.
"""

import time
from collections import deque

import cv2


class MotionGate:
    """Keeps the last N frames, adding one only when the scene changes enough."""

    def __init__(
        self,
        buffer_size=5,
        pixel_threshold=25,      # how much a pixel must change (0-255) to count
        change_ratio=0.02,       # fraction of pixels that must change (2%)
        min_interval=1.0,        # seconds between captures, avoids duplicates
        heartbeat=None,          # e.g. 60 = force a capture after 60s of no change
    ):
        self.buffer = deque(maxlen=buffer_size)   # oldest frame drops automatically
        self.pixel_threshold = pixel_threshold
        self.change_ratio = change_ratio
        self.min_interval = min_interval
        self.heartbeat = heartbeat
        self._last_small = None   # prepared copy of the last captured frame
        self._last_time = 0.0

    @staticmethod
    def _prepare(frame):
        """Shrink, grayscale, and blur so noise and lighting flicker are ignored."""
        small = cv2.resize(frame, (160, 90))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (7, 7), 0)

    def difference(self, frame):
        """Return the fraction (0-1) of pixels that changed vs the last capture."""
        small = self._prepare(frame)
        if self._last_small is None:
            return 1.0   # nothing to compare yet, treat as fully changed
        diff = cv2.absdiff(small, self._last_small)
        # Pixels that changed by more than pixel_threshold become white (255)
        _, mask = cv2.threshold(diff, self.pixel_threshold, 255, cv2.THRESH_BINARY)
        return cv2.countNonZero(mask) / mask.size

    def update(self, frame):
        """Feed every frame in. Returns True if this frame was added to the buffer."""
        now = time.time()
        if now - self._last_time < self.min_interval:
            return False

        changed = self.difference(frame) >= self.change_ratio
        # Heartbeat: capture anyway if nothing has been captured for a while
        stale = self.heartbeat is not None and now - self._last_time >= self.heartbeat

        if changed or stale:
            self.buffer.append(frame.copy())
            self._last_small = self._prepare(frame)
            self._last_time = now
            return True
        return False

    def latest(self):
        """Most recently captured frame, or None."""
        return self.buffer[-1] if self.buffer else None

    def frames(self):
        """All buffered frames, oldest first."""
        return list(self.buffer)