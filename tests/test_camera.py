"""Manual camera check (not a pytest test): shows the feed and saves a frame.

Saves tests/test_frame.jpg automatically after 3 seconds, and again whenever
you press s. Handy for grabbing a sample image to feed to detector.py.
Note: CAP_DSHOW is the Windows DirectShow backend.
"""

import os
import time
import cv2

INDEX = 0   # which camera to open (0 = default webcam)
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_frame.jpg")

cap = cv2.VideoCapture(INDEX, cv2.CAP_DSHOW)
if not cap.isOpened():
    print(f"Could not open camera {INDEX}")
    raise SystemExit(1)

print("Saving to:", SAVE_PATH)
print("Click the video window, then press 's' to save or 'q' to quit.")
print("A frame will also be saved automatically after 3 seconds.")

start = time.time()
auto_saved = False

def save(frame):
    ok = cv2.imwrite(SAVE_PATH, frame)
    print("Saved!" if ok else "imwrite FAILED", SAVE_PATH)

while True:
    ok, frame = cap.read()
    if not ok:
        print("Failed to read a frame")
        break

    cv2.imshow("Camera test", frame)

    if not auto_saved and time.time() - start > 3:
        save(frame)
        auto_saved = True

    key = cv2.waitKey(1) & 0xFF
    if key in (ord("q"), ord("Q")):
        break
    if key in (ord("s"), ord("S")):
        save(frame)

cap.release()
cv2.destroyAllWindows()