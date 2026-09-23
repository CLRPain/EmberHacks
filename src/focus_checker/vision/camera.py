"""Webcam access.

Wraps OpenCV's VideoCapture so the rest of the app can just call
``cam.read()`` and always get a fresh frame (or None). Used as a context
manager (``with Camera() as cam:``) so the device is released on exit.

Run this file directly for a live preview window; press q to quit.
"""

import cv2


class CameraError(RuntimeError):
    """Raised when the webcam can't be opened."""
    pass


class Camera:
    """Thin wrapper around cv2.VideoCapture."""

    def __init__(self, index=0, width=1280, height=720):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise CameraError(
                f"Could not open camera {index}. Check that it is connected, "
                "not used by another app, and that camera permission is granted."
            )
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # keep the buffer small (not honored by every backend)

    def read(self):
        """Return the latest frame, or None if the read failed."""
        # Discard any buffered frames so we get a current image,
        # not one captured seconds ago while the loop was waiting.
        for _ in range(2):
            self.cap.grab()       # grab() pulls a frame without decoding it (cheap)
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self):
        self.cap.release()

    # Context-manager support: `with Camera() as cam:` releases the device
    # even if the loop inside raises.
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()


def frames(index=0):
    """Generator that yields frames until the camera stops delivering them."""
    with Camera(index) as cam:
        while True:
            frame = cam.read()
            if frame is None:
                break
            yield frame
            
            
if __name__ == "__main__":
    # Manual test: show the live feed so you can check the camera works.
    import cv2
    with Camera() as cam:
        while True:
            frame = cam.read()
            if frame is None:
                break
            cv2.imshow("Camera test", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    cv2.destroyAllWindows()