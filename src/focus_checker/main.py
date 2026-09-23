"""The main webcam loop: watch, ask Gemini, speak.

run_camera() shows the live feed in an OpenCV window. Every CHECK_INTERVAL
seconds it hands a frame to a Checker, which calls Gemini on a background
thread (so the video never freezes) and, if you look distracted, speaks the
TA's line aloud with text-to-speech. Status text flows back to the window
through a queue.
"""

import queue
import threading
import time

import cv2

from .vision.camera import Camera
from .ai.detector import analyzeAttention
from .ai.scorer import select_ta
from .vision.motion_buffer import MotionGate
import io
import os


os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"   # silences pygame's startup banner

# Settings for MotionGate. Not used by run_camera() yet, which checks on a
# fixed timer instead.
MOTION_RATIO = 0.01    # fraction of pixels that must change (raise if it fires too often)
MIN_INTERVAL = 2.0     # never check more often than this, however much you move
HEARTBEAT = 120         # check anyway after this many seconds of stillness (None to disable)

# Settings for the live loop
CHECK_INTERVAL = 2    # seconds between checks (free tier quota is tiny)
ALERT_COOLDOWN = 45    # minimum seconds between spoken warnings
FALLBACK_LINE = "Hey, eyes back on your work."
WINDOW = "The TA (q to quit)"




# Voice per TA, keyed by display name (must match ai.scorer.TAS names).
# tld picks the regional accent of the voice; slow=True gives a deliberate delivery
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
        # Imported here so a missing package only disables online speech
        import pygame
        from gtts import gTTS

        # Generate an MP3 in memory, then play it with pygame
        buf = io.BytesIO()
        gTTS(text=text, lang="en", tld=cfg.get("tld", "com"),
             slow=cfg.get("slow", False)).write_to_fp(buf)
        buf.seek(0)

        with _speak_lock:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(buf, "mp3")
            pygame.mixer.music.play()
            # Block until done so the lock is held for the whole line
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
    except Exception as e:
        print("gTTS failed, using offline voice:", e)
        _speak_offline(text)


def _speak_offline(text):
    """Speak with the OS's built-in voice (pyttsx3). Works without internet."""
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
        self.ta_key = ta_key           # persona key from ai.scorer.TAS
        self.events = queue.Queue()    # status strings for the video overlay
        self.busy = False              # True while a Gemini call is in flight
        self.quota_dead = False        # set once the daily quota runs out; stops all checks
        self._last_alert = 0.0         # time of the last spoken warning (for ALERT_COOLDOWN)
        self._recent = []              # lines already spoken, passed back so the TA varies them

    def submit(self, frame):
        """Start a check on this frame in the background.

        Returns False (and does nothing) if a check is already running or the
        quota is used up, so the caller knows to try again next tick.
        """
        if self.busy or self.quota_dead:
            return False
        self.busy = True
        threading.Thread(target=self._work, args=(frame.copy(),), daemon=True).start()
        return True

    def _work(self, frame):
        """Runs on the worker thread: call Gemini, report, maybe speak."""
        try:
            small = cv2.resize(frame, (640, 360))   # smaller = faster, cheaper upload
            result = analyzeAttention(small, ta_key=self.ta_key, recent_lines=self._recent)

            label = "Distracted" if result.distracted else "Focused"
            self.events.put(f"{label} ({result.confidence:.2f}): {result.script}")

            # Only speak when distracted, and not more than once per cooldown
            now = time.time()
            if result.distracted and now - self._last_alert >= ALERT_COOLDOWN:
                self._last_alert = now
                line = result.script or FALLBACK_LINE
                self._recent.append(line)
                self.events.put(f"{self.ta_name}: {line}")
                speak(line, self.ta_name)
        except Exception as e:
            msg = str(e)
            # A per-day quota error won't fix itself, so stop trying
            if "PerDay" in msg:
                self.quota_dead = True
                self.events.put("Daily Gemini quota used up. Try again tomorrow.")
            else:
                self.events.put(f"API error: {msg[:80]}")
        finally:
            self.busy = False   # always free up the checker, even after errors


def run_camera(ta_name):
    """Run the camera loop for the selected TA (key or displayed name)."""
    ta_key = select_ta(ta_name)
    checker = Checker(ta_name, ta_key)
    status = f"{ta_name} is watching you..."
    last_check = 0.0

    with Camera() as cam:
        try:
            while True:
                frame = cam.read()
                if frame is None:
                    print("Camera stopped delivering frames")
                    break

                # Take a picture every CHECK_INTERVAL seconds. submit() refuses
                # if the previous request is still running, so slow API calls
                # skip a tick instead of piling up.
                now = time.time()
                if now - last_check >= CHECK_INTERVAL and checker.submit(frame):
                    last_check = now

                # Grab the newest status message, if any (drain the queue,
                # keeping only the last one)
                try:
                    while True:
                        status = checker.events.get_nowait()
                except queue.Empty:
                    pass

                # Draw the overlay: status bar at the bottom, TA + countdown on top
                display = frame.copy()
                h, w = display.shape[:2]
                cv2.rectangle(display, (0, h - 40), (w, h), (0, 0, 0), -1)
                cv2.putText(display, status[:90], (10, h - 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
                countdown = max(0, CHECK_INTERVAL - (time.time() - last_check))
                label = "analyzing..." if checker.busy else f"next pic in {countdown:.0f}s"
                cv2.putText(display, f"TA: {ta_name} | {label}", (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow(WINDOW, display)

                # Quit on q, or when the user closes the window with the X
                key = cv2.waitKey(1) & 0xFF
                closed = cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1
                if key in (ord("q"), ord("Q")) or closed:
                    break
        finally:
            cv2.destroyAllWindows()

def main():
    """Same flow as run.py, for `python -m src.focus_checker.main`."""
    from .ui.title_screen import choose_ta

    ta = choose_ta()
    if ta is not None:
        run_camera(ta)


if __name__ == "__main__":
    main()
