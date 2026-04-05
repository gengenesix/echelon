"""
VirtualCameraOutput — non-blocking virtual camera output.

Key fix: send_frame() is now completely non-blocking.
The pyvirtualcam sleep_until_next_frame() call runs in its own
dedicated background thread so it NEVER stalls the inference pipeline.
"""
import sys
import cv2
import queue
import threading
import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")
IS_MAC     = sys.platform == "darwin"


class VirtualCameraOutput:
    def __init__(self, device: str = '', width: int = 1280, height: int = 720, fps: int = 30):
        self.device = device
        self.width  = width
        self.height = height
        self.fps    = fps
        self.available    = False
        self._camera      = None
        # Internal queue — maxsize=2 means we always hold the latest frame
        self._send_queue: queue.Queue = queue.Queue(maxsize=2)
        self._send_thread: threading.Thread | None = None
        self._send_running = False

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> bool:
        try:
            import pyvirtualcam

            kwargs: dict = dict(
                width=self.width,
                height=self.height,
                fps=self.fps,
                fmt=pyvirtualcam.PixelFormat.RGB,
            )
            # Linux: explicit v4l2loopback device path
            if IS_LINUX and self.device:
                kwargs['device'] = self.device
            # Windows & macOS: let pyvirtualcam pick the default (OBS virt-cam)

            self._camera      = pyvirtualcam.Camera(**kwargs)
            self.available    = True
            self._send_running = True
            self._send_thread  = threading.Thread(
                target=self._send_loop,
                daemon=True,
                name="echelon-vcam-output",
            )
            self._send_thread.start()
            logger.info(f"Virtual camera started: {self.width}x{self.height}@{self.fps}fps")
            return True

        except ModuleNotFoundError:
            logger.warning("pyvirtualcam not installed — virtual camera disabled.")
            self.available = False
            return False
        except Exception as e:
            err = str(e).lower()
            if IS_WINDOWS:
                logger.warning(
                    "Virtual camera unavailable on Windows. "
                    "Install OBS Studio and enable its Virtual Camera."
                )
            elif IS_MAC:
                logger.warning(
                    "Virtual camera unavailable on macOS. "
                    "Install OBS Studio (obsproject.com) and enable Virtual Camera."
                )
            elif IS_LINUX and "v4l2loopback" in err:
                logger.warning(
                    "Virtual camera unavailable. "
                    "Run: sudo apt install v4l2loopback-dkms && "
                    "sudo modprobe v4l2loopback devices=1 video_nr=10 "
                    "card_label='Echelon Camera' exclusive_caps=1"
                )
            else:
                logger.warning(f"Virtual camera unavailable: {e}")
            self.available = False
            return False

    def send_frame(self, frame: np.ndarray) -> None:
        """
        Non-blocking enqueue.  Drops the oldest queued frame if full so we
        always send the most recent output — never stalls the pipeline thread.
        """
        if not self.available or self._camera is None:
            return
        # Discard stale frame so the newest one takes its place
        try:
            self._send_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._send_queue.put_nowait(frame)
        except queue.Full:
            pass  # extremely unlikely after the get_nowait above

    def stop(self) -> None:
        self._send_running = False
        # Unblock the send thread if it's waiting
        try:
            self._send_queue.put_nowait(None)
        except queue.Full:
            pass
        if self._send_thread and self._send_thread.is_alive():
            self._send_thread.join(timeout=3)
        if self._camera:
            try:
                self._camera.__exit__(None, None, None)
            except Exception:
                pass
            self._camera = None
        self.available = False

    def is_active(self) -> bool:
        return self.available and self._camera is not None

    # ── Background send loop ──────────────────────────────────────────────────

    def _send_loop(self) -> None:
        """
        Dedicated thread: pulls frames from the queue, converts BGR→RGB,
        resizes if needed, sends to the virtual camera, then sleeps until
        the next frame slot.  The sleep happens here — NOT in the pipeline.
        """
        while self._send_running:
            try:
                frame = self._send_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if frame is None:
                break  # stop sentinel

            try:
                h, w = frame.shape[:2]
                if w != self.width or h != self.height:
                    frame = cv2.resize(
                        frame, (self.width, self.height),
                        interpolation=cv2.INTER_LINEAR,
                    )
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._camera.send(rgb)
                # This sleep lives here — no effect on pipeline throughput
                self._camera.sleep_until_next_frame()
            except Exception as e:
                logger.debug(f"vcam send error: {e}")
