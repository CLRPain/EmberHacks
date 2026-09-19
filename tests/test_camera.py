import cv2
from src.focus_checker.camera import Camera

with Camera() as cam:
    while True:
        frame = cam.read()
        if frame is None:
            print("No frame received")
            break
        cv2.imshow("Camera test", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
cv2.destroyAllWindows()