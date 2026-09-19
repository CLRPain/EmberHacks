import queue
import threading
import time

import cv2

from .camera import Camera
from .detector import analyzeAttention
from .scorer import generate_script
from .motion_buffer import MotionGate

MOTION_RATIO = 0.03  # fraction of pixels that must change (raise if it fires too often)
MIN_INTERVAL = 2.0  # never check more often than this, however much you move
HEARTBEAT = 120  # check anyway after this many seconds of stillness (None to disable)

CHECK_INTERVAL = 5  # seconds between checks (free tier quota is tiny)
ALERT_COOLDOWN = 45  # minimum seconds between spoken warnings
FALLBACK_LINE = "Hey, eyes back on your work."
WINDOW = "The TA (q to quit)"
BREAK_DURATION = 30  # 5 minutes default break duration (in seconds)


# --- ADDED: Play Alarm Helper (Threaded to avoid freezing video) ---
def play_alarm():
    """Plays an audio file when the break ends."""

    def _play():
        try:
            import pygame
            import os

            # Initialize pygame mixer for multi-track audio
            pygame.mixer.init()

            audio_files = [
                "audio_files\\brr_brr_brr_patapim.mp3",
                "audio_files\\extreme_alarm_clock.mp3",
                "audio_files\\fire_alarm.mp3",
                "audio_files\\iphone_alarm.mp3",
                "audio_files\\loudest_alarm_clock.mp3",
                "audio_files\\perfect_alarm.mp3",
                "audio_files\\wake_up.mp3"
            ]

            print("Loading and playing files simultaneously...")

            # Get the absolute path of the directory this script is in
            current_dir = os.path.dirname(os.path.abspath(__file__))

            playing_channels = []

            for filename in audio_files:
                file_path = os.path.join(current_dir, filename)

                # Check if file exists first so we don't crash
                if not os.path.exists(file_path):
                    print(f"Warning: Could not find '{file_path}'")
                    continue

                try:
                    sound = pygame.mixer.Sound(file_path)
                    # Find an available channel and play the sound
                    channel = pygame.mixer.find_channel()
                    if channel:
                        channel.play(sound)
                        playing_channels.append(channel)
                except Exception as ex:
                    print(f"Failed to play {filename}: {ex}")

            if not playing_channels:
                print("No sounds were successfully loaded.")
                return

            # Keep thread alive while ANY channel is still playing audio
            while any(channel.get_busy() for channel in playing_channels):
                time.sleep(0.1)

            print("\n[ALARM] Break time is over!\n")

        except ImportError:
            print("Pygame is not installed. Please run: pip install pygame")
        except Exception as e:
            print(f"Error in audio thread: {e}")

    # FIX: This line MUST be outdented to line up with `def _play():`
    # Otherwise, the thread is never actually started!
    threading.Thread(target=_play, daemon=True).start()

# -------------------------------------------------------------------

def check_break_status(break_end_time):
    """
    Calculates remaining break time without blocking the main thread loop.
    Returns tuple: (is_on_break: bool, remaining_seconds: int)
    """
    if break_end_time is None:
        return False, 0
    now = time.time()
    remaining = int(break_end_time - now)
    if remaining > 0:
        return True, remaining
    return False, 0


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
        self.events = queue.Queue()  # status strings for the video overlay
        self.busy = False
        self.quota_dead = False
        self._last_alert = 0.0
        self._recent = []

    def submit(self, frame):
        if self.busy or self.quota_dead:
            return False
        self.busy = True
        threading.Thread(target=self._work, args=(frame.copy(),),
                         daemon=True).start()
        return True

    def _work(self, frame):
        try:
            small = cv2.resize(frame,
                               (640, 360))  # smaller = faster, cheaper upload
            result = analyzeAttention(small)

            label = "Distracted" if result.distracted else "Focused"
            self.events.put(
                f"{label} ({result.confidence:.2f}): {result.explanation}")

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
                self.events.put(
                    "Daily Gemini quota used up. Try again tomorrow.")
            else:
                self.events.put(f"API error: {msg[:80]}")
        finally:
            self.busy = False


def run_camera(ta_name):
    checker = Checker(ta_name)
    gate = MotionGate(buffer_size=5, change_ratio=MOTION_RATIO,
                      min_interval=MIN_INTERVAL, heartbeat=HEARTBEAT)
    status = f"{ta_name} is watching you..."

    break_end_time = None
    was_on_break = False  # ADDED: Track previous frame's break status to detect exactly when it ends

    with Camera() as cam:
        try:
            while True:
                frame = cam.read()
                if frame is None:
                    print("Camera stopped delivering frames")
                    break

                diff = gate.difference(frame)  # for the on-screen readout

                is_on_break, break_left = check_break_status(break_end_time)

                # --- 1. NATURAL BREAK END (Timer hit 0) ---
                if was_on_break and not is_on_break:
                    play_alarm()
                    status = f"Break over! {ta_name} is watching you again..."

                # Update tracker for the next frame
                was_on_break = is_on_break

                # Only feed the gate when we can actually use a capture AND not on break.
                if not is_on_break and not checker.busy and not checker.quota_dead:
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

                if is_on_break:
                    mins, secs = divmod(break_left, 60)
                    disp_status = f"[ON BREAK] {mins:02d}:{secs:02d} left | Press 'b' to end early"
                else:
                    disp_status = status[:90]

                cv2.putText(display, disp_status, (10, h - 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
                cv2.putText(display,
                            f"TA: {ta_name} | motion {diff:.3f} | Press 'B' for Break",
                            (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow(WINDOW, display)

                key = cv2.waitKey(1) & 0xFF
                closed = cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1
                if key in (ord("q"), ord("Q")) or closed:
                    break

                elif key in (ord("b"), ord("B")):
                    if is_on_break:
                        # --- 2. MANUAL BREAK END (Ended early) ---
                        break_end_time = None
                        is_on_break = False
                        was_on_break = False  # Reset so natural timer doesn't falsely trigger next frame
                        status = f"Break ended early. {ta_name} is watching you..."

                        # (Optional) You can call play_alarm() here too if you want
                        # the sound to play when you manually cancel the break.

                    else:
                        break_end_time = time.time() + BREAK_DURATION

        finally:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    from .title_screen import choose_ta

    ta = choose_ta()
    if ta:
        run_camera(ta)