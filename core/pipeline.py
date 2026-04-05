"""
Echelon Pipeline v3.0 — stable, glitch-free, cross-platform

Key fixes over v2.5:
  1. Virtual camera output is now NON-BLOCKING (moved to VirtualCameraOutput's
     own thread via the updated virtual_camera.py) — removes the 33ms stall
     that was locking the entire pipeline every frame.
  2. Real face NEVER shown — _last_swapped is initialised to a black frame the
     moment the first camera frame arrives, so there is zero window where the
     raw face leaks to the virtual camera.
  3. Source embedding is pre-computed ONCE (via swap_engine.prepare_source)
     instead of running a 512×512 matmul on every frame.
  4. ONNX warmup call before entering the loop — eliminates the 3-10× latency
     spike on the very first real frame.
  5. Tracking/detection counter sync fixed — when optical flow returns None we
     fall back to the tracker's last known position rather than setting
     target_face=None and exposing the real face.
  6. max_track_frames increased so the tracker never expires before the
     detection counter fires.
  7. GC frequency reduced (every 300 loops instead of 100) to reduce pauses.
"""
import gc
import time
import traceback
import logging
from collections import deque
from pathlib import Path
from threading import Lock
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal
import cv2
import numpy as np

from config.manager import AppConfig
from core.hardware import HardwareInfo
from core.capture import CameraCapture
from core.face_detector import FaceDetector, DetectedFace, get_global_detector
from core.face_tracker import FaceTracker, TrackedFace
from core.inference import FaceSwapEngine
from core.enhancer import FaceEnhancer
from core.virtual_camera import VirtualCameraOutput
from utils.logger import get_logger

logger = get_logger(__name__)


class FPSCounter:
    def __init__(self, window: int = 30):
        self._times = deque(maxlen=window)

    def tick(self) -> float:
        now = time.perf_counter()
        self._times.append(now)
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return 0.0 if elapsed <= 0 else (len(self._times) - 1) / elapsed


class EchelonPipeline(QThread):
    frames_ready        = pyqtSignal(object, object)
    fps_updated         = pyqtSignal(float)
    latency_updated     = pyqtSignal(float)
    status_changed      = pyqtSignal(str)
    error_occurred      = pyqtSignal(str)
    virtual_cam_status  = pyqtSignal(bool)
    frame_skip_changed  = pyqtSignal(int)

    def __init__(self, config: AppConfig, hw_info: HardwareInfo, parent=None):
        super().__init__(parent)
        self.config   = config
        self.hw_info  = hw_info
        model_path    = str(Path(config.models_dir) / "inswapper_128.onnx")

        self.capture = CameraCapture(
            device_id=config.camera_device_id,
            width=config.output_width,
            height=config.output_height,
            fps=config.output_fps,
        )

        # Use global cached detector (no cold-start delay on face upload)
        self.face_detector = get_global_detector(config.models_dir, hw_info.onnx_providers)
        self.face_detector._detect_interval = config.face_detect_interval

        self.swap_engine = FaceSwapEngine(model_path, hw_info.onnx_providers)

        self.virtual_cam = VirtualCameraOutput(
            device=config.virtual_camera_device,
            width=config.output_width,
            height=config.output_height,
            fps=config.output_fps,
        )

        self.source_face      = None
        self._lock            = Lock()
        self._running         = False
        self.performance_mode = config.performance_mode
        self.frame_skip       = config.frame_skip
        self.auto_tune_enabled = config.auto_tune
        self._perf_tuner      = None
        self._vcam_active     = False
        self.target_face_mode = getattr(config, 'target_face_mode', 'largest')
        self.bg_blur          = getattr(config, 'bg_blur', 'off')
        self._enhancer        = None
        self._try_load_enhancer()

        # max_track_frames well above _detect_every so the tracker never
        # declares tracking lost before the detection counter fires
        self._tracker          = FaceTracker(max_track_frames=30)
        self._last_swapped     = None   # guaranteed never None once loop starts
        self._last_raw         = None
        self._frame_count      = 0
        self._detect_every     = config.face_detect_interval
        self._frames_since_det = 0

    # ── Source face management ────────────────────────────────────────────────

    def set_source_face(self, face: DetectedFace) -> None:
        with self._lock:
            self.source_face = face
        # Pre-compute embedding transform so swap_face never does the matmul
        if self.swap_engine.is_loaded:
            self.swap_engine.prepare_source(face)
        self.face_detector.reset_tracking()
        self._tracker.reset()
        # Keep _last_swapped — smoother transition; new face renders in ~1 frame

    # ── Performance controls ──────────────────────────────────────────────────

    def set_performance_mode(self, mode: str) -> None:
        self.performance_mode = mode
        if mode == 'speed':
            self.frame_skip    = 2
            self._detect_every = 8
        elif mode == 'balanced':
            self.frame_skip    = 1
            self._detect_every = 5
        else:  # quality
            self.frame_skip    = 0
            self._detect_every = 3
        self.face_detector._detect_interval = self._detect_every
        self.frame_skip_changed.emit(self.frame_skip)

    def enable_auto_tune(self, enabled: bool) -> None:
        self.auto_tune_enabled = enabled
        if enabled and self._perf_tuner is None:
            from core.performance_tuner import PerformanceTuner
            self._perf_tuner = PerformanceTuner()

    def toggle_virtual_cam(self) -> None:
        if self._vcam_active:
            self.virtual_cam.stop()
            self._vcam_active = False
            self.virtual_cam_status.emit(False)
        else:
            ok = self.virtual_cam.start()
            self._vcam_active = ok
            self.virtual_cam_status.emit(ok)

    def set_target_face_mode(self, mode: str) -> None:
        self.target_face_mode = mode

    def set_bg_blur(self, strength: str) -> None:
        self.bg_blur = strength

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        try:
            self.status_changed.emit("Loading models...")

            # ── Load face detector ──────────────────────────────────────────
            if not self.face_detector.is_loaded:
                if not self.face_detector.load():
                    self.error_occurred.emit(
                        "Failed to load face detector. Check models directory."
                    )
                    return

            # ── Load swap engine ────────────────────────────────────────────
            if not self.swap_engine.load():
                self.error_occurred.emit(
                    "Failed to load swap model. Download inswapper_128.onnx first."
                )
                return

            # ── WARMUP: pre-compile ONNX graph so first real frame is fast ──
            self.status_changed.emit("Warming up...")
            self.swap_engine.warmup()

            # ── Pre-compute source embedding if face already loaded ─────────
            with self._lock:
                src_snapshot = self.source_face
            if src_snapshot is not None:
                self.swap_engine.prepare_source(src_snapshot)

            # ── Open camera ─────────────────────────────────────────────────
            if not self.capture.start():
                self.error_occurred.emit(
                    "Failed to open camera. Check camera connection."
                )
                return

            # ── Start virtual camera (send_frame is now non-blocking) ───────
            vcam_ok = self.virtual_cam.start()
            self._vcam_active = vcam_ok
            self.virtual_cam_status.emit(vcam_ok)

            self.status_changed.emit("Live")
            self._running  = True
            fps_counter    = FPSCounter()
            loop_count     = 0
            first_frame    = True   # used to init _last_swapped as black

            while self._running:
                frame = self.capture.get_frame()
                if frame is None:
                    time.sleep(0.001)
                    continue

                # ── Guarantee _last_swapped is never None after first frame ─
                if first_frame:
                    first_frame = False
                    self._last_swapped = np.zeros_like(frame)  # black frame

                loop_count        += 1
                self._frame_count += 1
                self._last_raw     = frame

                # ── Frame skip: reuse last swapped — NEVER show real face ───
                if self.frame_skip > 0 and loop_count % (self.frame_skip + 1) != 0:
                    output = self._last_swapped   # always a valid array now
                    if self._vcam_active:
                        self.virtual_cam.send_frame(output)
                    fps = fps_counter.tick()
                    self.frames_ready.emit(frame, output)
                    if self._frame_count % 30 == 0:
                        self.fps_updated.emit(fps)
                    continue

                # ── Scale down for processing ────────────────────────────────
                proc_size  = self._get_processing_size()
                proc_frame = cv2.resize(frame, proc_size) if proc_size else frame

                start_time = time.perf_counter()

                with self._lock:
                    src = self.source_face

                if src is not None:
                    swapped        = None
                    blur_face_bbox = None

                    # ── Detection / tracking ─────────────────────────────────
                    self._frames_since_det += 1
                    run_detection = (self._frames_since_det >= self._detect_every)

                    if run_detection:
                        self._frames_since_det = 0
                        if self.target_face_mode == 'all':
                            faces       = self.face_detector.detect_faces(proc_frame)
                            target_face = faces[0] if faces else None
                        else:
                            target_face = self.face_detector.get_primary_face(proc_frame)
                        self._tracker.update_from_detection(target_face, proc_frame)
                        tracked = self._tracker.get_last()
                    else:
                        tracked = self._tracker.track(proc_frame)
                        if tracked is None:
                            # Optical flow lost — force detection next frame
                            self._frames_since_det = self._detect_every
                            # Use last known position as fallback for THIS frame
                            tracked = self._tracker.get_last()

                    if tracked is not None:
                        target_face = self._face_to_detected(tracked)
                    else:
                        target_face = None

                    # ── Swap ─────────────────────────────────────────────────
                    if target_face is not None:
                        try:
                            swapped = self.swap_engine.swap_face(
                                proc_frame, src, target_face
                            )
                            blur_face_bbox = target_face.bbox
                        except Exception as e:
                            logger.debug(f"swap_face error: {e}")
                            swapped = None

                    if swapped is not None:
                        # Background blur
                        if self.bg_blur != 'off' and blur_face_bbox is not None:
                            try:
                                swapped = self._apply_background_blur(
                                    swapped, blur_face_bbox, self.bg_blur
                                )
                            except Exception:
                                pass

                        # Scale back to original resolution
                        if proc_size:
                            swapped = cv2.resize(
                                swapped,
                                (frame.shape[1], frame.shape[0]),
                                interpolation=cv2.INTER_LINEAR,
                            )

                        # Quality enhancement (quality mode only)
                        if (
                            self.performance_mode == 'quality'
                            and self._enhancer is not None
                            and self._enhancer.is_loaded()
                        ):
                            try:
                                swapped = self._enhancer.enhance(swapped)
                            except Exception:
                                pass

                        # Update the "last good swap" — used by frame-skip path
                        self._last_swapped = swapped

                    else:
                        # No swap produced — reuse last good frame
                        # Real face is NEVER sent; _last_swapped is always valid
                        swapped = self._last_swapped

                else:
                    # No source face selected yet
                    swapped = self._last_swapped  # black or last good frame

                # ── Output (virtual cam send is non-blocking now) ────────────
                if self._vcam_active:
                    self.virtual_cam.send_frame(swapped)

                latency = (time.perf_counter() - start_time) * 1000
                fps     = fps_counter.tick()
                self.frames_ready.emit(frame, swapped)

                if self._frame_count % 30 == 0:
                    self.fps_updated.emit(fps)
                    self.latency_updated.emit(latency)

                # Periodic GC — less frequent = fewer pauses
                if loop_count % 300 == 0:
                    gc.collect()

                # Auto-tune
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

    def stop(self) -> None:
        self._running = False
        self.wait(3000)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _try_load_enhancer(self) -> None:
        try:
            self._enhancer = FaceEnhancer()
            self._enhancer.load()
        except Exception:
            self._enhancer = None

    def _get_processing_size(self) -> Optional[tuple]:
        if self.performance_mode == 'speed':
            return (480, 360)
        elif self.performance_mode == 'balanced':
            return (640, 480)
        return None  # quality: full resolution

    def _apply_background_blur(
        self, frame: np.ndarray, face_bbox: np.ndarray, strength: str = 'light'
    ) -> np.ndarray:
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        x1, y1, x2, y2 = face_bbox.astype(int)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        rw = int((x2 - x1) * 1.5)
        rh = int((y2 - y1) * 2.5)
        cv2.ellipse(mask, (cx, cy + rh // 4), (rw, rh), 0, 0, 360, 255, -1)
        mask = cv2.GaussianBlur(mask, (51, 51), 25)
        blur_amount = 15 if strength == 'light' else 35
        blurred     = cv2.GaussianBlur(frame, (blur_amount, blur_amount), 0)
        mask_3ch    = mask.astype(np.float32) / 255.0
        mask_3ch    = np.stack([mask_3ch] * 3, axis=-1)
        result      = (
            frame.astype(np.float32) * mask_3ch
            + blurred.astype(np.float32) * (1 - mask_3ch)
        )
        return result.astype(np.uint8)

    def _face_to_detected(self, tracked: TrackedFace) -> DetectedFace:
        return DetectedFace(
            bbox=tracked.bbox,
            landmarks=tracked.landmarks,
            embedding=tracked.embedding,
            confidence=tracked.confidence,
            age=tracked.age,
            gender=tracked.gender,
        )

