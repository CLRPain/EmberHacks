import os
import queue
import tempfile
import threading
import time

import cv2

from .camera import Camera
from .detector import analyzeAttention
from .script_writer import generate_script

CHECK_INTERVAL = 30    # seconds between checks (free tier quota is tiny)
ALERT_COOLDOWN = 45    # minimum seconds between spoken warnings
FALLBACK_LINE = "Hey, eyes back on your work."
WINDOW = "The TA (q to quit)"


def speak(text):
    """Blocking text-to-speech. Swap in your own engine if you like."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print("TTS unavailable:", e)


class Checker:
    """Runs check -> script -> speech on a worker thread."""

    def __init__(self, ta_name):
        self.ta_name = ta_name
        self.events = queue.Queue()    # status strings for the video overlay
        self.busy = False
        self.quota_dead = False
        self._last_alert = 0.0
        self._recent = []

    def submit(self, frame):
        if self.busy or self.quota_dead:
            return False
        self.busy = True
        threading.Thread(target=self._work, args=(frame.copy(),), daemon=True).start()
        return True

    def _work(self, frame):
        try:
            small = cv2.resize(frame, (640, 360))   # smaller = faster, cheaper upload
            result = analyzeAttention(small)

            label = "Distracted" if result.distracted else "Focused"
            self.events.put(f"{label} ({result.confidence:.2f}): {result.explanation}")

            now = time.time()
            if result.distracted and now - self._last_alert >= ALERT_COOLDOWN:
                self._last_alert = now
                try:
                    line = generate_script(result, self.ta_name, self._recent)
                except Exception as e:
                    print("Script error:", e)
                    line = FALLBACK_LINE
                self._recent.append(line)
                self.events.put(f"{self.ta_name}: {line}")
                speak(line)
        except Exception as e:
            msg = str(e)
            if "PerDay" in msg:
                self.quota_dead = True
                self.events.put("Daily Gemini quota used up. Try again tomorrow.")
            else:
                self.events.put(f"API error: {msg[:80]}")
        finally:
            self.busy = False


def run_camera(ta_name):
    checker = Checker(ta_name)
    status = f"{ta_name} is watching you..."
    last_check = 0.0

    with Camera() as cam:
        try:
            while True:
                frame = cam.read()
                if frame is None:
                    print("Camera stopped delivering frames")
                    break

                now = time.time()
                if now - last_check >= CHECK_INTERVAL and checker.submit(frame):
                    last_check = now

                try:
                    while True:
                        status = checker.events.get_nowait()
                except queue.Empty:
                    pass

                display = frame.copy()
                h = display.shape[0]
                cv2.rectangle(display, (0, h - 40), (display.shape[1], h), (0, 0, 0), -1)
                cv2.putText(display, status[:90], (10, h - 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
                cv2.putText(display, f"TA: {ta_name}", (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow(WINDOW, display)

                key = cv2.waitKey(1) & 0xFF
                closed = cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1
                if key in (ord("q"), ord("Q")) or closed:
                    break
        finally:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    from .title_screen import choose_ta
    ta = choose_ta()
    if ta:
        run_camera(ta)