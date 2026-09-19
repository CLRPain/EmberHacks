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
        self._last_small = None
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
            return 1.0
        diff = cv2.absdiff(small, self._last_small)
        _, mask = cv2.threshold(diff, self.pixel_threshold, 255, cv2.THRESH_BINARY)
        return cv2.countNonZero(mask) / mask.size

    def update(self, frame):
        """Feed every frame in. Returns True if this frame was added to the buffer."""
        now = time.time()
        if now - self._last_time < self.min_interval:
            return False

        changed = self.difference(frame) >= self.change_ratio
        stale = self.heartbeat is not None and now - self._last_time >= self.heartbeat

        if changed or stale:
            self.buffer.append(frame.copy())
            self._last_small = self._prepare(frame)
            self._last_time = now
            return True
        return False

    def latest(self):
        return self.buffer[-1] if self.buffer else None

    def frames(self):
        return list(self.buffer)