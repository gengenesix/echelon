import cv2
import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)

class VirtualCameraOutput:
    def __init__(self, device: str = '/dev/video10', width: int = 1280, height: int = 720, fps: int = 30):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.available = False
        self._camera = None

    def start(self) -> bool:
        try:
            import pyvirtualcam
            self._camera = pyvirtualcam.Camera(
                width=self.width,
                height=self.height,
                fps=self.fps,
                device=self.device,
                fmt=pyvirtualcam.PixelFormat.RGB,
            )
            self.available = True
            logger.info(f"Virtual camera started: {self.device} {self.width}x{self.height}@{self.fps}")
            return True
        except Exception as e:
            logger.warning(f"Virtual camera not available: {e}. Continuing without it.")
            self.available = False
            return False

    def send_frame(self, frame: np.ndarray):
        if not self.available or self._camera is None:
            return
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if rgb.shape[1] != self.width or rgb.shape[0] != self.height:
                rgb = cv2.resize(rgb, (self.width, self.height))
            self._camera.send(rgb)
            self._camera.sleep_until_next_frame()
        except Exception as e:
            logger.warning(f"Virtual camera send error: {e}")

    def stop(self):
        if self._camera:
            try:
                self._camera.__exit__(None, None, None)
            except Exception:
                pass
            self._camera = None
        self.available = False

    def is_active(self) -> bool:
        return self.available and self._camera is not None
