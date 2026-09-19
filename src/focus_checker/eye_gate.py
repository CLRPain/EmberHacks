import time
from collections import deque

import cv2
import mediapipe as mp
import numpy as np

# Face Mesh landmark indices (with refine_landmarks=True)
# (iris_center, outer_corner, inner_corner, upper_lid, lower_lid)
EYE_A = (468, 33, 133, 159, 145)
EYE_B = (473, 263, 362, 386, 374)


class EyeGate:
    """Buffers frames only when the eyes' gaze direction changes enough."""

    def __init__(
        self,
        buffer_size=5,
        gaze_threshold=0.08,   # how far gaze must shift (0-1 scale) to capture
        blink_ratio=0.18,      # eye openness below this = blink, ignored
        min_interval=1.0,
        heartbeat=None,        # force a capture after N seconds of no change
    ):
        self.buffer = deque(maxlen=buffer_size)
        self.gaze_threshold = gaze_threshold
        self.blink_ratio = blink_ratio
        self.min_interval = min_interval
        self.heartbeat = heartbeat

        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._last_gaze = None      # gaze at last capture (None = no face)
        self._had_reference = False
        self._last_time = 0.0
        self.last_diff = 0.0        # for on-screen debugging
        self.status = "starting"

    @staticmethod
    def _eye_gaze(pts, idx):
        iris, outer, inner, top, bottom = (pts[i] for i in idx)
        axis = inner - outer
        length = np.linalg.norm(axis)
        if length < 1e-6:
            return None
        # Horizontal: iris position along the corner-to-corner line (0..1)
        h = float(np.dot(iris - outer, axis) / (length ** 2))
        lid_gap = np.linalg.norm(bottom - top)
        openness = lid_gap / length
        v = float((iris[1] - top[1]) / max(bottom[1] - top[1], 1e-6))
        return h, v, openness

    def _gaze(self, frame):
        """Return (h, v, openness) averaged over both eyes, or None if no face."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.face_mesh.process(rgb)
        if not result.multi_face_landmarks:
            return None
        lm = result.multi_face_landmarks[0].landmark
        h_img, w_img = frame.shape[:2]
        pts = np.array([(p.x * w_img, p.y * h_img) for p in lm])
        a = self._eye_gaze(pts, EYE_A)
        b = self._eye_gaze(pts, EYE_B)
        if a is None or b is None:
            return None
        return tuple(np.mean([a, b], axis=0))

    def update(self, frame):
        """Feed every frame in. Returns True if this frame was added to the buffer."""
        now = time.time()
        if now - self._last_time < self.min_interval:
            return False

        gaze = self._gaze(frame)
        capture = False

        if gaze is None:
            # Face disappeared (away) -> capture once when that changes
            self.status = "no face"
            self.last_diff = 1.0 if self._last_gaze is not None else 0.0
            if self._last_gaze is not None or not self._had_reference:
                capture = True
                self._last_gaze = None
        else:
            h, v, openness = gaze
            if openness < self.blink_ratio:
                self.status = "blink (ignored)"
                self.last_diff = 0.0
                return False
            self.status = "tracking"
            if self._last_gaze is None:
                # Face just appeared, or first frame
                self.last_diff = 1.0
                capture = True
            else:
                dh = h - self._last_gaze[0]
                dv = v - self._last_gaze[1]
                self.last_diff = float((dh ** 2 + dv ** 2) ** 0.5)
                capture = self.last_diff >= self.gaze_threshold
            if capture:
                self._last_gaze = (h, v)

        stale = self.heartbeat is not None and now - self._last_time >= self.heartbeat
        if capture or stale:
            self.buffer.append(frame.copy())
            self._had_reference = True
            self._last_time = now
            return True
        return False

    def latest(self):
        return self.buffer[-1] if self.buffer else None

    def frames(self):
        return list(self.buffer)

    def close(self):
        self.face_mesh.close()