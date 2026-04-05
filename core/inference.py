"""
Face swap inference engine using inswapper_128.onnx
Based on FaceFusion's actual inference pipeline.

v2.5 improvements:
 - warmup(): one dummy inference to JIT-compile ONNX graph before real use
 - prepare_source(): pre-compute the 512×512 matrix multiply ONCE per source
   face instead of every single frame — eliminates a ~0.5ms per-frame cost
 - _cached_source_embedding: reused across all frames while source is unchanged
"""
import cv2
import numpy as np
import gc
import time
import collections
import onnx
import onnx.numpy_helper
from typing import Optional, Tuple
from utils.logger import get_logger
from core.face_detector import DetectedFace

logger = get_logger(__name__)

# arcface_128 alignment template (from FaceFusion)
ARCFACE_128_TEMPLATE = np.array([
    [0.36167656, 0.40387734],
    [0.63696719, 0.40235469],
    [0.50019687, 0.56044219],
    [0.38710391, 0.72160547],
    [0.61507734, 0.72034453]
], dtype=np.float32)


class FaceSwapEngine:
    def __init__(self, model_path: str, providers: list):
        self.session              = None
        self.model_path           = model_path
        self.providers            = providers
        self.is_loaded            = False
        self.input_size           = (128, 128)
        self._input_name          = None
        self._output_name         = None
        self._source_name         = None
        self._model_initializer   = None
        self._transform_buffer    = collections.deque(maxlen=3)
        # Pre-computed source embedding — updated once per source face change
        self._cached_source_embedding: Optional[np.ndarray] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self) -> bool:
        import onnxruntime as ort
        try:
            t0 = time.time()
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            # ORT_PARALLEL lets each ONNX op run across multiple threads.
            # intra=6 uses 6 of the 8 i5 logical cores for tensor ops.
            # inter=1 — we run one model at a time, no benefit from >1 here.
            # ORT_SEQUENTIAL is faster for small models like inswapper_128
            # (128×128 input). ORT_PARALLEL's thread-pool overhead > savings.
            opts.execution_mode       = ort.ExecutionMode.ORT_SEQUENTIAL
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 6   # use 6 of 8 i5 logical cores
            opts.enable_mem_pattern   = True
            opts.enable_cpu_mem_arena = True
            self.session = ort.InferenceSession(
                self.model_path, sess_options=opts, providers=self.providers
            )
            inputs = self.session.get_inputs()
            self._input_name  = inputs[0].name   # 'target' — [1,3,128,128]
            self._source_name = inputs[1].name   # 'source' — [1,512]
            self._output_name = self.session.get_outputs()[0].name

            # Load model initializer for inswapper embedding transformation
            try:
                model = onnx.load(self.model_path)
                self._model_initializer = onnx.numpy_helper.to_array(
                    model.graph.initializer[-1]
                )
                logger.info(f"Model initializer shape: {self._model_initializer.shape}")
            except Exception as e:
                logger.warning(f"Could not load model initializer: {e}")
                self._model_initializer = None

            self.is_loaded = True
            logger.info(
                f"FaceSwapEngine loaded in {time.time()-t0:.2f}s — "
                f"inputs: {[(i.name, i.shape) for i in inputs]}"
            )
            return True
        except Exception as e:
            logger.error(f"FaceSwapEngine load failed: {e}")
            return False

    def warmup(self) -> None:
        """
        Run one dummy inference to JIT-compile the ONNX graph.
        Call this once after load() and BEFORE the first real swap_face() call.
        Eliminates the 3-10× latency spike on the very first real frame.
        """
        if not self.is_loaded or self.session is None:
            return
        try:
            t0 = time.time()
            dummy_target = np.zeros((1, 3, 128, 128), dtype=np.float32)
            dummy_source = np.zeros((1, 512),          dtype=np.float32)
            self.session.run(
                [self._output_name],
                {self._input_name: dummy_target, self._source_name: dummy_source},
            )
            logger.info(f"Swap engine warmup complete in {time.time()-t0:.2f}s")
        except Exception as e:
            logger.warning(f"Warmup failed (non-critical): {e}")

    def prepare_source(self, source_face: DetectedFace) -> None:
        """
        Pre-compute and cache the transformed source embedding.
        Call this ONCE whenever the source face changes instead of repeating
        the 512×512 matrix multiply on every single frame.
        """
        try:
            embedding = source_face.embedding.reshape((1, -1)).astype(np.float32)
            if self._model_initializer is not None:
                embedding = np.dot(embedding, self._model_initializer)
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
            self._cached_source_embedding = embedding
            logger.debug("Source embedding cached")
        except Exception as e:
            logger.warning(f"prepare_source failed: {e}")
            self._cached_source_embedding = None

    def unload(self) -> None:
        self.session                  = None
        self._model_initializer       = None
        self._cached_source_embedding = None
        self.is_loaded                = False
        self._transform_buffer.clear()
        gc.collect()

    # ── Inference ─────────────────────────────────────────────────────────────

    def swap_face(
        self,
        target_frame: np.ndarray,
        source_face: DetectedFace,
        target_face: DetectedFace,
    ) -> np.ndarray:
        if not self.is_loaded or self.session is None:
            return target_frame
        try:
            # Step 1: Warp target face to arcface_128 template
            crop_frame, affine_matrix = self._warp_face(
                target_frame, target_face.landmarks
            )

            # Temporal smoothing: buffer affine matrices, use mean
            self._transform_buffer.append(affine_matrix)
            smoothed_matrix = np.mean(list(self._transform_buffer), axis=0)

            # Step 2: Prepare crop for inference
            crop_input = self._prepare_crop_frame(crop_frame)

            # Step 3: Use cached source embedding (pre-computed once per face change)
            if self._cached_source_embedding is not None:
                source_embedding = self._cached_source_embedding
            else:
                # Fallback: compute on the fly (slower path, only if prepare_source
                # was never called, e.g. pipeline restarted mid-session)
                source_embedding = self._prepare_source_embedding(source_face.embedding)

            # Step 4: ONNX inference
            feed = {
                self._input_name:  crop_input,
                self._source_name: source_embedding,
            }
            output = self.session.run([self._output_name], feed)[0][0]

            # Step 5: Normalise output back to image
            swapped_crop = self._normalize_crop_frame(output)

            # Step 6: Soft elliptical blend mask
            crop_mask = self._create_box_mask(swapped_crop)

            # Step 6b: Colour-correct swapped face to match target skin tone
            swapped_crop = self._color_transfer(swapped_crop, crop_frame, crop_mask)

            # Step 6c: Unsharp mask — recovers detail lost by the 128×128 model
            swapped_crop = self._sharpen_crop(swapped_crop)

            # Step 7: Paste back using smoothed affine
            result = self._paste_back(
                target_frame, swapped_crop, crop_mask, smoothed_matrix
            )
            return result

        except Exception as e:
            logger.error(f"swap_face error: {e}", exc_info=True)
            return target_frame

    # ── Private helpers ───────────────────────────────────────────────────────

    def _warp_face(
        self, frame: np.ndarray, landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        src_pts = landmarks.astype(np.float32)
        dst_pts = ARCFACE_128_TEMPLATE * np.array(
            [self.input_size[0], self.input_size[1]], dtype=np.float32
        )
        affine_matrix = cv2.estimateAffinePartial2D(
            src_pts, dst_pts, method=cv2.LMEDS
        )[0]
        if affine_matrix is None:
            affine_matrix = np.eye(2, 3, dtype=np.float32)
        crop_frame = cv2.warpAffine(
            frame, affine_matrix, self.input_size,
            borderMode=cv2.BORDER_REPLICATE,
            flags=cv2.INTER_AREA,
        )
        return crop_frame, affine_matrix

    def _prepare_crop_frame(self, crop_frame: np.ndarray) -> np.ndarray:
        frame = crop_frame[:, :, ::-1].astype(np.float32) / 255.0
        frame = frame.transpose(2, 0, 1)
        return np.expand_dims(frame, axis=0)

    def _prepare_source_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """Fallback: compute embedding transform on the fly (used when
        prepare_source() was never called)."""
        source_embedding = embedding.reshape((1, -1)).astype(np.float32)
        if self._model_initializer is not None:
            source_embedding = np.dot(source_embedding, self._model_initializer)
            norm = np.linalg.norm(source_embedding)
            if norm > 0:
                source_embedding = source_embedding / norm
        return source_embedding

    def _normalize_crop_frame(self, output: np.ndarray) -> np.ndarray:
        frame = output.transpose(1, 2, 0)
        frame = np.clip(frame, 0, 1)
        frame = frame[:, :, ::-1] * 255
        return frame.astype(np.uint8)

    def _create_box_mask(
        self, crop_frame: np.ndarray, blur: float = 0.3, padding: tuple = (0, 0, 0, 0)
    ) -> np.ndarray:
        h, w = crop_frame.shape[:2]
        mask   = np.zeros((h, w), dtype=np.float32)
        center = (w // 2, h // 2)
        # Shrink axes ~12% vs previous "fill almost everything".
        # This excludes the outer edge of the warp where border-replicate
        # introduces colour bleed and smearing artifacts.
        axes = (max(1, int(w * 0.42)), max(1, int(h * 0.44)))
        cv2.ellipse(mask, center, axes, 0, 0, 360, 1.0, -1)
        # Stronger edge blur → smoother blend seam at face boundary.
        blur_amount = max(51, int(blur * min(h, w) * 0.7) * 2 + 1)
        if blur_amount % 2 == 0:
            blur_amount += 1
        return cv2.GaussianBlur(mask, (blur_amount, blur_amount), 0)

    def _sharpen_crop(self, img: np.ndarray) -> np.ndarray:
        """
        Unsharp mask: compensates for the inherent 128×128 blur of the swap
        model.  Strength 1.7/-0.7 is a well-tested ratio for skin texture.
        Cost: ~0.3ms on a CPU-only i5 for a 128×128 image.
        """
        blur = cv2.GaussianBlur(img, (0, 0), 3.0)
        return cv2.addWeighted(img, 1.7, blur, -0.7, 0)

    def _color_transfer(
        self, source: np.ndarray, target: np.ndarray, mask: np.ndarray
    ) -> np.ndarray:
        source_lab = cv2.cvtColor(source, cv2.COLOR_BGR2LAB).astype(np.float32)
        target_lab = cv2.cvtColor(target, cv2.COLOR_BGR2LAB).astype(np.float32)
        mask_bool  = mask > 0.5
        if not mask_bool.any():
            return source
        for i in range(3):
            s_mean = source_lab[:, :, i][mask_bool].mean()
            s_std  = source_lab[:, :, i][mask_bool].std() + 1e-6
            t_mean = target_lab[:, :, i][mask_bool].mean()
            t_std  = target_lab[:, :, i][mask_bool].std() + 1e-6
            source_lab[:, :, i] = np.clip(
                (source_lab[:, :, i] - s_mean) * (t_std / s_std) + t_mean,
                0, 255,
            )
        return cv2.cvtColor(source_lab.astype(np.uint8), cv2.COLOR_LAB2BGR)

    def _paste_back(
        self,
        temp_frame: np.ndarray,
        crop_frame: np.ndarray,
        crop_mask:  np.ndarray,
        affine_matrix: np.ndarray,
    ) -> np.ndarray:
        temp_h, temp_w = temp_frame.shape[:2]
        crop_h, crop_w = crop_frame.shape[:2]

        inverse_matrix = cv2.invertAffineTransform(affine_matrix)

        crop_points  = np.array(
            [[0, 0], [crop_w, 0], [crop_w, crop_h], [0, crop_h]], dtype=np.float32
        )
        paste_points = cv2.transform(
            crop_points.reshape(1, -1, 2), inverse_matrix
        ).reshape(-1, 2)

        x1 = max(0,      int(np.floor(paste_points[:, 0].min())))
        y1 = max(0,      int(np.floor(paste_points[:, 1].min())))
        x2 = min(temp_w, int(np.ceil( paste_points[:, 0].max())))
        y2 = min(temp_h, int(np.ceil( paste_points[:, 1].max())))

        paste_w = x2 - x1
        paste_h = y2 - y1
        if paste_w <= 0 or paste_h <= 0:
            return temp_frame

        paste_matrix = inverse_matrix.copy()
        paste_matrix[0, 2] -= x1
        paste_matrix[1, 2] -= y1

        inverse_frame = cv2.warpAffine(
            crop_frame, paste_matrix, (paste_w, paste_h),
            borderMode=cv2.BORDER_REPLICATE,
        )
        inverse_mask = cv2.warpAffine(crop_mask, paste_matrix, (paste_w, paste_h))
        inverse_mask = np.clip(inverse_mask, 0, 1)[:, :, np.newaxis]

        result = temp_frame.copy()
        roi    = result[y1:y2, x1:x2].astype(np.float32)
        blended = roi * (1 - inverse_mask) + inverse_frame.astype(np.float32) * inverse_mask
        result[y1:y2, x1:x2] = blended.astype(np.uint8)
        return result
