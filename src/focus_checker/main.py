import queue
import threading
import time

import cv2

from .camera import Camera
from .detector import analyzeAttention
from .scorer import select_ta
from .motion_buffer import MotionGate
import io
import os


os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"   # silences pygame's startup banner

MOTION_RATIO = 0.03     # fraction of pixels that must change (raise if it fires too often)
MIN_INTERVAL = 2.0     # never check more often than this, however much you move
HEARTBEAT = 120         # check anyway after this many seconds of stillness (None to disable)

CHECK_INTERVAL = 5    # seconds between checks (free tier quota is tiny)
ALERT_COOLDOWN = 45    # minimum seconds between spoken warnings
FALLBACK_LINE = "Hey, eyes back on your work."
WINDOW = "The TA (q to quit)"


# tld picks the regional accent of the voice;s slow=True gives a deliberate delivery
TA_VOICES = {
    "The Termtestinator": {"tld": "com",    "slow": True},
    "Mr. President":      {"tld": "com",    "slow": False},
    "The Torontonian":    {"tld": "ca",     "slow": False},
    "John Resident":      {"tld": "co.uk",  "slow": False},
}

_speak_lock = threading.Lock()   # never let two lines play over each other


def speak(text, ta_name=None):
    """Speak with gTTS (needs internet). Falls back to offline pyttsx3 on failure."""
    cfg = TA_VOICES.get(ta_name, {})
    try:
        import pygame
        from gtts import gTTS

        buf = io.BytesIO()
        gTTS(text=text, lang="en", tld=cfg.get("tld", "com"),
             slow=cfg.get("slow", False)).write_to_fp(buf)
        buf.seek(0)

        with _speak_lock:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(buf, "mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
    except Exception as e:
        print("gTTS failed, using offline voice:", e)
        _speak_offline(text)


def _speak_offline(text):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print("TTS unavailable:", e)


class Checker:
    """Runs check -> speech on a worker thread.

    The detector returns the verdict and the TA's spoken line in one Gemini
    call, so there is no separate script step.
    """

    def __init__(self, ta_name, ta_key):
        self.ta_name = ta_name         # display name from the title screen
        self.ta_key = ta_key           # persona key from scorer.TAS
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
            result = analyzeAttention(small, ta_key=self.ta_key, recent_lines=self._recent)

            label = "Distracted" if result.distracted else "Focused"
            self.events.put(f"{label} ({result.confidence:.2f}): {result.script}")

            now = time.time()
            if result.distracted and now - self._last_alert >= ALERT_COOLDOWN:
                self._last_alert = now
                line = result.script or FALLBACK_LINE
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
    """Run the camera loop for the selected TA (key or displayed name)."""
    ta_key = select_ta(ta_name)
    checker = Checker(ta_name, ta_key)
    gate = MotionGate(buffer_size=5, change_ratio=MOTION_RATIO,
                      min_interval=MIN_INTERVAL, heartbeat=HEARTBEAT)
    status = f"{ta_name} is watching you..."

    with Camera() as cam:
        try:
            while True:
                frame = cam.read()
                if frame is None:
                    print("Camera stopped delivering frames")
                    break

                diff = gate.difference(frame)   # for the on-screen readout

                # Only feed the gate when we can actually use a capture.
                # If it fired while a request was in flight, the change would be
                # consumed (its reference frame reset) and the check would be lost.
                if not checker.busy and not checker.quota_dead:
                    if gate.update(frame):
                        checker.submit(gate.latest())

                # Grab the newest status message, if any
                try:
                    while True:
                        status = checker.events.get_nowait()
                except queue.Empty:
                    pass

                display = frame.copy()
                h, w = display.shape[:2]
                cv2.rectangle(display, (0, h - 40), (w, h), (0, 0, 0), -1)
                cv2.putText(display, status[:90], (10, h - 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
                cv2.putText(display, f"TA: {ta_name} | motion {diff:.3f}", (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow(WINDOW, display)

                key = cv2.waitKey(1) & 0xFF
                closed = cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1
                if key in (ord("q"), ord("Q")) or closed:
                    break
        finally:
            cv2.destroyAllWindows()


def main():
    from .title_screen import choose_ta

    ta = choose_ta()
    if ta is not None:
        run_camera(ta)


if __name__ == "__main__":
    main()
