import time

import cv2

from .camera import Camera
from .motion_buffer import MotionGate
from .detector import checkAttention

ALERT_AFTER = 45   # seconds of continuous "distracted" before alerting


def main():
    gate = MotionGate(buffer_size=5, change_ratio=0.02, min_interval=5.0, heartbeat=60)
    distracted_since = None
    alerted = False

    with Camera() as cam:
        try:
            while True:
                frame = cam.read()
                if frame is None:
                    print("Camera stopped delivering frames")
                    break

                diff = gate.difference(frame)   # for the on-screen readout

                if gate.update(frame):
                    try:
                        result = checkAttention(gate.latest())
                    except Exception as e:
                        print("API error:", e)
                        result = None

                    if result:
                        status = "distracted" if result.distracted else "focused"
                        print(f"{status:10} "
                              f"({result.confidence:.2f}) {result.explanation}")

                        if result.distracted:
                            distracted_since = distracted_since or time.time()
                        else:
                            distracted_since, alerted = None, False

                # State persists between captures, so check the timer every loop
                if distracted_since and not alerted \
                        and time.time() - distracted_since >= ALERT_AFTER:
                    print("⚠️  You've been off-task for a while. Back to work!")
                    alerted = True

                display = frame.copy()
                cv2.putText(display, f"diff {diff:.3f} | buffer {len(gate.buffer)}/5",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.imshow("Focus Checker (q to quit)", display)
                if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                    break
        finally:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()