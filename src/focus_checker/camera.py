import cv2


class CameraError(RuntimeError):
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
            self.cap.grab()
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self):
        self.cap.release()

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