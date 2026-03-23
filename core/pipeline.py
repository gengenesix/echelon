import gc
import time
import traceback
import logging
from collections import deque
from pathlib import Path
from threading import Lock
from PyQt6.QtCore import QThread, pyqtSignal
import cv2
import numpy as np

from config.manager import AppConfig
from core.hardware import HardwareInfo
from core.capture import CameraCapture
from core.face_detector import FaceDetector, DetectedFace
from core.inference import FaceSwapEngine
from core.enhancer import FaceEnhancer
from core.virtual_camera import VirtualCameraOutput
from utils.logger import get_logger

logger = get_logger(__name__)


class FPSCounter:
    def __init__(self, window=30):
        self._times = deque(maxlen=window)

    def tick(self) -> float:
        now = time.perf_counter()
        self._times.append(now)
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        if elapsed <= 0:
            return 0.0
        return (len(self._times) - 1) / elapsed


class EchelonPipeline(QThread):
    frames_ready = pyqtSignal(object, object)
    fps_updated = pyqtSignal(float)
    latency_updated = pyqtSignal(float)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    virtual_cam_status = pyqtSignal(bool)
    frame_skip_changed = pyqtSignal(int)

    def __init__(self, config: AppConfig, hw_info: HardwareInfo, parent=None):
        super().__init__(parent)
        self.config = config
        self.hw_info = hw_info
        model_path = str(Path(config.models_dir) / "inswapper_128.onnx")
        self.capture = CameraCapture(
            device_id=config.camera_device_id,
            width=config.output_width,
            height=config.output_height,
            fps=config.output_fps,
        )
        self.face_detector = FaceDetector(config.models_dir, hw_info.onnx_providers)
        self.face_detector._detect_interval = config.face_detect_interval
        self.swap_engine = FaceSwapEngine(model_path, hw_info.onnx_providers)
        self.virtual_cam = VirtualCameraOutput(
            device=config.virtual_camera_device,
            width=config.output_width,
            height=config.output_height,
            fps=config.output_fps,
        )
        self.source_face = None
        self._lock = Lock()
        self._running = False
        self.performance_mode = config.performance_mode
        self.frame_skip = config.frame_skip
        self._last_swapped_frame = None
        self._frame_count = 0
        self.auto_tune_enabled = config.auto_tune
        self._perf_tuner = None
        self._vcam_active = False
        self.target_face_mode = getattr(config, 'target_face_mode', 'largest')
        self.bg_blur = getattr(config, 'bg_blur', 'off')
        self._enhancer = None
        self._try_load_enhancer()

    def set_source_face(self, face: DetectedFace):
        with self._lock:
            self.source_face = face
        self.face_detector.reset_tracking()

    def set_performance_mode(self, mode: str):
        self.performance_mode = mode
        self.frame_skip = 2 if mode == 'speed' else (1 if mode == 'balanced' else 0)
        self.face_detector._detect_interval = (
            7 if mode == 'speed' else 5 if mode == 'balanced' else 3
        )
        self.frame_skip_changed.emit(self.frame_skip)

    def enable_auto_tune(self, enabled: bool):
        self.auto_tune_enabled = enabled
        if enabled and self._perf_tuner is None:
            from core.performance_tuner import PerformanceTuner
            self._perf_tuner = PerformanceTuner()

    def toggle_virtual_cam(self):
        if self._vcam_active:
            self.virtual_cam.stop()
            self._vcam_active = False
            self.virtual_cam_status.emit(False)
        else:
            ok = self.virtual_cam.start()
            self._vcam_active = ok
            self.virtual_cam_status.emit(ok)

    def set_target_face_mode(self, mode: str):
        self.target_face_mode = mode

    def set_bg_blur(self, strength: str):
        self.bg_blur = strength

    def _try_load_enhancer(self):
        try:
            self._enhancer = FaceEnhancer()
            self._enhancer.load()  # fails silently if gfpgan not installed/model absent
        except Exception:
            self._enhancer = None

    def _get_target_face(self, frame):
        """Return the face to swap based on target_face_mode."""
        mode = self.target_face_mode
        if mode == 'largest':
            return self.face_detector.get_tracked_face(frame)
        faces = self.face_detector.get_tracked_faces(frame)
        if not faces:
            return None
        def area(f):
            b = f.bbox
            return (b[2] - b[0]) * (b[3] - b[1])
        if mode == 'smallest':
            return min(faces, key=area)
        elif mode == 'face_1':
            return faces[0] if len(faces) >= 1 else None
        elif mode == 'face_2':
            return faces[1] if len(faces) >= 2 else None
        elif mode == 'face_3':
            return faces[2] if len(faces) >= 3 else None
        return faces[0] if faces else None

    def _apply_background_blur(self, frame, face_bbox, strength='light'):
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        x1, y1, x2, y2 = face_bbox.astype(int)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        rw = int((x2 - x1) * 1.5)
        rh = int((y2 - y1) * 2.5)
        cv2.ellipse(mask, (cx, cy + rh // 4), (rw, rh), 0, 0, 360, 255, -1)
        mask = cv2.GaussianBlur(mask, (51, 51), 25)
        blur_amount = 15 if strength == 'light' else 35
        blurred = cv2.GaussianBlur(frame, (blur_amount, blur_amount), 0)
        mask_3ch = mask.astype(np.float32) / 255.0
        mask_3ch = np.stack([mask_3ch] * 3, axis=-1)
        result = (frame.astype(np.float32) * mask_3ch
                  + blurred.astype(np.float32) * (1 - mask_3ch))
        return result.astype(np.uint8)

    def _get_processing_size(self):
        if self.performance_mode == 'speed':
            return (480, 360)
        elif self.performance_mode == 'balanced':
            return (640, 480)
        return None

    def run(self):
        try:
            self.status_changed.emit("Loading models...")
            if not self.face_detector.load():
                self.error_occurred.emit("Failed to load face detector. Check models directory.")
                return
            if not self.swap_engine.load():
                self.error_occurred.emit("Failed to load swap model. Download inswapper_128.onnx first.")
                return
            if not self.capture.start():
                self.error_occurred.emit("Failed to open camera. Check camera connection.")
                return
            vcam_ok = self.virtual_cam.start()
            self._vcam_active = vcam_ok
            self.virtual_cam_status.emit(vcam_ok)
            self.status_changed.emit("Live")
            self._running = True
            fps_counter = FPSCounter()
            loop_count = 0

            while self._running:
                frame = self.capture.get_frame()
                if frame is None:
                    time.sleep(0.001)
                    continue

                loop_count += 1
                self._frame_count += 1

                # Frame skip: reuse last swapped frame on skipped frames
                if self.frame_skip > 0 and loop_count % (self.frame_skip + 1) != 0:
                    if self._last_swapped_frame is not None:
                        swapped = self._last_swapped_frame
                        if self._vcam_active:
                            self.virtual_cam.send_frame(swapped)
                        fps = fps_counter.tick()
                        self.frames_ready.emit(frame, swapped)
                        if self._frame_count % 30 == 0:
                            self.fps_updated.emit(fps)
                        continue

                # Downscale for processing if needed
                proc_size = self._get_processing_size()
                if proc_size:
                    proc_frame = cv2.resize(frame, proc_size)
                else:
                    proc_frame = frame

                start_time = time.perf_counter()

                with self._lock:
                    src = self.source_face

                if src is not None:
                    swapped = None
                    blur_face_bbox = None

                    if self.target_face_mode == 'all':
                        faces = self.face_detector.get_tracked_faces(proc_frame)
                        if faces:
                            swapped = proc_frame.copy()
                            for tface in faces:
                                try:
                                    swapped = self.swap_engine.swap_face(swapped, src, tface)
                                except Exception:
                                    pass
                            blur_face_bbox = faces[0].bbox
                    else:
                        target_face = self._get_target_face(proc_frame)
                        if target_face is not None:
                            swapped = self.swap_engine.swap_face(proc_frame, src, target_face)
                            blur_face_bbox = target_face.bbox

                    if swapped is not None:
                        # Background blur
                        if self.bg_blur != 'off' and blur_face_bbox is not None:
                            try:
                                swapped = self._apply_background_blur(
                                    swapped, blur_face_bbox, self.bg_blur)
                            except Exception:
                                pass
                        # Resize back to full resolution
                        if proc_size:
                            swapped = cv2.resize(swapped, (frame.shape[1], frame.shape[0]))
                        # GFPGAN enhancement in quality mode
                        if (self.performance_mode == 'quality'
                                and self._enhancer is not None
                                and self._enhancer.is_loaded()):
                            try:
                                swapped = self._enhancer.enhance(swapped)
                            except Exception:
                                pass
                    else:
                        swapped = frame.copy()
                else:
                    swapped = frame.copy()

                self._last_swapped_frame = swapped
                if self._vcam_active:
                    self.virtual_cam.send_frame(swapped)

                latency = (time.perf_counter() - start_time) * 1000
                fps = fps_counter.tick()
                self.frames_ready.emit(frame, swapped)

                if self._frame_count % 30 == 0:
                    self.fps_updated.emit(fps)
                    self.latency_updated.emit(latency)

                # Memory management — collect every 100 frames
                if loop_count % 100 == 0:
                    gc.collect()

                # Auto-tune — record fps every frame, tune every 60
                if self.auto_tune_enabled and self._perf_tuner:
                    self._perf_tuner.record_fps(fps)
                    if self._frame_count % 60 == 0:
                        msg = self._perf_tuner.auto_tune(self)
                        logger.info(f"Auto-tune: {msg}")
                        self.frame_skip_changed.emit(self.frame_skip)

        except Exception as e:
            logger.error(f"Pipeline error: {traceback.format_exc()}")
            self.error_occurred.emit(str(e))
        finally:
            self.capture.stop()
            self.virtual_cam.stop()
            self._vcam_active = False
            self.swap_engine.unload()
            self.status_changed.emit("Stopped")

    def _scale_frame(self, frame, w, h):
        return cv2.resize(frame, (w, h))

    def stop(self):
        self._running = False
        self.wait(3000)
