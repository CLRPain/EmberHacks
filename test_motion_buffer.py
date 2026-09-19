import os
import cv2
from src.focus_checker.motion_buffer import MotionGate

gate = MotionGate(buffer_size=5, change_ratio=0.02, min_interval=1.0)
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    raise SystemExit("Could not open camera")

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "buffer_out")

print("Move around to trigger captures. Click the window, then 'd' dumps the buffer, 'q' quits.")

while True:
    ok, frame = cap.read()
    if not ok:
        break

    if gate.update(frame):
        print(f"Captured! buffer size = {len(gate.buffer)}")

    cv2.putText(frame, f"diff {gate.difference(frame):.3f} | buffer {len(gate.buffer)}/5",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.imshow("Motion test", frame)

    key = cv2.waitKey(1) & 0xFF
    if key in (ord("q"), ord("Q")):
        break
    if key in (ord("d"), ord("D")):
        os.makedirs(OUT_DIR, exist_ok=True)
        for i, f in enumerate(gate.frames()):
            cv2.imwrite(os.path.join(OUT_DIR, f"frame_{i}.jpg"), f)
        print("Saved buffer to", OUT_DIR)

cap.release()
cv2.destroyAllWindows()