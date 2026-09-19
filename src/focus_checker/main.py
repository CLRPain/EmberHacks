import os
import queue
import tempfile
import threading
import os
import queue
import tempfile
import threading
import time

import cv2

from .camera import Camera
from .detector import analyzeAttention

INTERVAL = 5       # seconds between checks
ALERT_AFTER = 45   # seconds of continuous "distracted" before alerting


def analyze_frame(frame):
    """Write the frame to a temp file, analyze it, then delete the file."""
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return analyzeAttention(path)
    finally:
        os.remove(path)   # don't leave photos of the user on disk


class BackgroundAnalyzer:
    """Runs analysis on a worker thread so the video loop never blocks."""

    def __init__(self):
        self._jobs = queue.Queue(maxsize=1)
        self._results = queue.Queue()
        self.busy = False
        threading.Thread(target=self._worker, daemon=True).start()

    def submit(self, frame):
        """Queue a frame. Returns False if a request is already in flight."""
        if self.busy:
            return False
        self.busy = True
        self._jobs.put(frame.copy())   # copy: the main loop keeps changing `frame`
        return True

    def poll(self):
        """Return a finished result (or Exception), or None if nothing is ready."""
        try:
            return self._results.get_nowait()
        except queue.Empty:
            return None

    def _worker(self):
        while True:
            frame = self._jobs.get()
            try:
                self._results.put(analyze_frame(frame))
            except Exception as e:
                self._results.put(e)
            finally:
                self.busy = False


def main():
    analyzer = BackgroundAnalyzer()
    last_capture = 0.0
    distracted_since = None
    alerted = False

    with Camera() as cam:
        try:
            while True:
                frame = cam.read()
                if frame is None:
                    print("Camera stopped delivering frames")
                    break

                now = time.time()

                # Start a new check only if the interval passed AND the last
                # request has finished, so slow API calls never pile up.
                if now - last_capture >= INTERVAL and analyzer.submit(frame):
                    last_capture = now

                # Collect a result if one is ready (never waits)
                result = analyzer.poll()
                if isinstance(result, Exception):
                    print("API error:", result)
                elif result is not None:
                    status = "distracted" if result.distracted else "focused"
                    print(f"{status:10} ({result.confidence:.2f}) {result.explanation}")
                    if result.distracted:
                        distracted_since = distracted_since or time.time()
                    else:
                        distracted_since, alerted = None, False

                if distracted_since and not alerted \
                        and time.time() - distracted_since >= ALERT_AFTER:
                    print("⚠️  You've been off-task for a while. Back to work!")
                    alerted = True

                display = frame.copy()
                if analyzer.busy:
                    label = "analyzing..."
                else:
                    label = f"next check in {max(0, INTERVAL - (time.time() - last_capture)):.0f}s"
                cv2.putText(display, label, (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.imshow("Focus Checker (q to quit)", display)
                if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                    break
        finally:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    from .title_screen import choose_ta
    ta = choose_ta()
    if ta:
        run_camera(ta)