import os
import cv2
from src.focus_checker.eye_gate import EyeGate

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "buffer_out")
os.makedirs(OUT_DIR, exist_ok=True)

gate = EyeGate(buffer_size=5, gaze_threshold=0.12, min_interval=1.0)
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    raise SystemExit("Could not open camera")

print("Saving to:", OUT_DIR)
print("Look around the screen, then down at your desk. Click the window, 'q' quits.")

count = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break

    if gate.update(frame):
        count += 1
        path = os.path.join(OUT_DIR, f"eye_capture_{count:03d}.jpg")
        cv2.imwrite(path, gate.latest())
        print(f"Captured #{count} (gaze shift {gate.last_diff:.3f}) -> {path}")

    display = frame.copy()
    cv2.putText(display, f"{gate.status} | shift {gate.last_diff:.2f} | buffer {len(gate.buffer)}/5",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imshow("Eye gate test", display)

    if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
        break

gate.close()
cap.release()
cv2.destroyAllWindows()