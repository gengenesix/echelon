"""
FaceEnhancer — tiered face restoration pipeline.

Priority order:
  1. CodeFormer ONNX  — best quality, no PyTorch needed, ~80ms/frame on CPU
  2. OpenCV bilateral + unsharp mask — always available, ~3ms/frame, still good
"""
import os
import cv2
import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)

# CodeFormer expects 512×512 input
_CF_SIZE = 512


class FaceEnhancer:
    def __init__(self, models_dir: str = ""):
        self._loaded     = False
        self._mode       = None        # 'codeformer' | 'opencv'
        self._session    = None
        self._models_dir = models_dir

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self) -> bool:
        # 1. Try CodeFormer ONNX (no PyTorch, pure ONNX Runtime)
        if self._models_dir:
            cf_path = os.path.join(self._models_dir, "codeformer.onnx")
            if os.path.exists(cf_path):
                try:
                    import onnxruntime as ort
                    opts = ort.SessionOptions()
                    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                    opts.intra_op_num_threads = 2
                    opts.inter_op_num_threads = 1
                    self._session = ort.InferenceSession(
                        cf_path, sess_options=opts,
                        providers=["CPUExecutionProvider"],
                    )
                    self._mode   = 'codeformer'
                    self._loaded = True
                    logger.info("CodeFormer ONNX enhancer loaded from %s", cf_path)
                    return True
                except Exception as e:
                    logger.info("CodeFormer ONNX load failed (%s), falling back to OpenCV", e)

        # 2. OpenCV bilateral + unsharp mask — zero extra dependencies
        self._mode   = 'opencv'
        self._loaded = True
        logger.info("Face enhancer: OpenCV bilateral+sharpen (no model required)")
        return True

    def enhance(self, frame: np.ndarray) -> np.ndarray:
        if not self._loaded:
            return frame
        try:
            if self._mode == 'codeformer' and self._session is not None:
                return self._enhance_codeformer(frame)
            return self._enhance_opencv(frame)
        except Exception:
            return frame

    def enhance_region(self, frame: np.ndarray, face_bbox: np.ndarray) -> np.ndarray:
        """
        Apply enhancement only to the face bounding-box region.
        Typically 5-10× faster than enhancing the full frame, making it
        viable even in speed/CPU mode.
        """
        if not self._loaded:
            return frame
        try:
            x1, y1, x2, y2 = face_bbox.astype(int)
            h, w = frame.shape[:2]
            pad  = max(10, int((x2 - x1) * 0.15))
            rx1  = max(0, x1 - pad)
            ry1  = max(0, y1 - pad)
            rx2  = min(w, x2 + pad)
            ry2  = min(h, y2 + pad)
            if rx2 <= rx1 + 10 or ry2 <= ry1 + 10:
                return frame
            region          = frame[ry1:ry2, rx1:rx2]
            enhanced_region = self._enhance_opencv(region)
            result          = frame.copy()
            result[ry1:ry2, rx1:rx2] = enhanced_region
            return result
        except Exception:
            return frame

    def is_loaded(self) -> bool:
        return self._loaded

    # ── Enhancement methods ────────────────────────────────────────────────────

    def _enhance_codeformer(self, frame: np.ndarray) -> np.ndarray:
        h0, w0 = frame.shape[:2]
        inp = cv2.resize(frame, (_CF_SIZE, _CF_SIZE), interpolation=cv2.INTER_LANCZOS4)
        # BGR → RGB, [0,1], then [-1,1]
        inp = inp[:, :, ::-1].astype(np.float32) / 255.0
        inp = (inp - 0.5) / 0.5
        inp = inp.transpose(2, 0, 1)[np.newaxis]

        in_name = self._session.get_inputs()[0].name
        out = self._session.run(None, {in_name: inp})[0][0]

        # [-1,1] → [0,255] BGR
        out = out.transpose(1, 2, 0)
        out = ((out * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
        out = out[:, :, ::-1]
        return cv2.resize(out, (w0, h0), interpolation=cv2.INTER_LANCZOS4)

    def _enhance_opencv(self, frame: np.ndarray) -> np.ndarray:
        """
        Bilateral filter  — smooths skin noise, preserves edges.
        Unsharp mask      — recovers detail lost by the 128×128 swap model.
        Both run ~3ms on a CPU-only i5. Safe for every frame in balanced mode.
        """
        smooth = cv2.bilateralFilter(frame, d=5, sigmaColor=45, sigmaSpace=45)
        blur   = cv2.GaussianBlur(smooth, (0, 0), 2.5)
        return cv2.addWeighted(smooth, 1.6, blur, -0.6, 0)
