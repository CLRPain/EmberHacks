"""Gaze-change gate: only keep frames where the person's eyes moved.

Uses MediaPipe Face Mesh to find the irises, turns their position into a
rough gaze direction, and captures a frame when that direction shifts more
than a threshold (or the face appears/disappears). Blinks are ignored.

The idea is to call Gemini only when something interesting happened instead
of on a fixed timer. It's an alternative to vision.motion_buffer.MotionGate; neither
is wired into main.py right now. See tests/test_eyes.py for a live demo.
"""

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
        min_interval=1.0,      # seconds between captures, avoids duplicates
        heartbeat=None,        # force a capture after N seconds of no change
    ):
        self.buffer = deque(maxlen=buffer_size)   # oldest frame drops automatically
        self.gaze_threshold = gaze_threshold
        self.blink_ratio = blink_ratio
        self.min_interval = min_interval
        self.heartbeat = heartbeat

        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,   # needed for the iris landmarks (468+)
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
        """Return (h, v, openness) for one eye, or None if the eye is degenerate.

        h: 0 = iris at outer corner, 1 = at inner corner (left/right gaze).
        v: 0 = iris at upper lid, 1 = at lower lid (up/down gaze).
        openness: lid gap relative to eye width (small = blinking).
        """
        iris, outer, inner, top, bottom = (pts[i] for i in idx)
        axis = inner - outer
        length = np.linalg.norm(axis)
        if length < 1e-6:
            return None
        # Horizontal: iris position along the corner-to-corner line (0..1)
        # (projection of iris onto the eye's axis, normalized to eye width)
        h = float(np.dot(iris - outer, axis) / (length ** 2))
        lid_gap = np.linalg.norm(bottom - top)
        openness = lid_gap / length
        # Vertical: iris height between the lids (0..1)
        v = float((iris[1] - top[1]) / max(bottom[1] - top[1], 1e-6))
        return h, v, openness

    def _gaze(self, frame):
        """Return (h, v, openness) averaged over both eyes, or None if no face."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)   # OpenCV is BGR, MediaPipe wants RGB
        result = self.face_mesh.process(rgb)
        if not result.multi_face_landmarks:
            return None
        lm = result.multi_face_landmarks[0].landmark
        h_img, w_img = frame.shape[:2]
        # Landmarks come normalized (0-1); convert to pixels so both axes use
        # the same units when measuring distances.
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
                # Distance the gaze moved since the last captured frame
                dh = h - self._last_gaze[0]
                dv = v - self._last_gaze[1]
                self.last_diff = float((dh ** 2 + dv ** 2) ** 0.5)
                capture = self.last_diff >= self.gaze_threshold
            if capture:
                self._last_gaze = (h, v)   # new reference point for future diffs

        # Heartbeat: capture anyway if nothing has been captured for a while
        stale = self.heartbeat is not None and now - self._last_time >= self.heartbeat
        if capture or stale:
            self.buffer.append(frame.copy())
            self._had_reference = True
            self._last_time = now
            return True
        return False

    def latest(self):
        """Most recently captured frame, or None."""
        return self.buffer[-1] if self.buffer else None

    def frames(self):
        """All buffered frames, oldest first."""
        return list(self.buffer)

    def close(self):
        """Free MediaPipe's resources."""
        self.face_mesh.close()