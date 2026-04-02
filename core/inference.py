"""
Face swap inference engine using inswapper_128.onnx
Based on FaceFusion's actual inference pipeline.
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
        self.session = None
        self.model_path = model_path
        self.providers = providers
        self.is_loaded = False
        self.input_size = (128, 128)
        self._input_name = None
        self._output_name = None
        self._source_name = None
        self._model_initializer = None
        self._transform_buffer = collections.deque(maxlen=3)

    def load(self) -> bool:
        import onnxruntime as ort
        try:
            t0 = time.time()
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.inter_op_num_threads = 2
            opts.intra_op_num_threads = 4
            opts.enable_mem_pattern = True
            opts.enable_cpu_mem_arena = True
            self.session = ort.InferenceSession(
                self.model_path, sess_options=opts, providers=self.providers
            )
            inputs = self.session.get_inputs()
            self._input_name = inputs[0].name   # 'target' — shape [1,3,128,128]
            self._source_name = inputs[1].name   # 'source' — shape [1,512]
            self._output_name = self.session.get_outputs()[0].name

            # Load model initializer matrix for inswapper embedding transformation
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

    def swap_face(
        self,
        target_frame: np.ndarray,
        source_face: DetectedFace,
        target_face: DetectedFace,
    ) -> np.ndarray:
        if not self.is_loaded or self.session is None:
            return target_frame
        try:
            # Step 1: Warp target face using arcface_128 template
            crop_frame, affine_matrix = self._warp_face(
                target_frame, target_face.landmarks
            )

            # Temporal smoothing: buffer affine matrices and use smoothed version
            self._transform_buffer.append(affine_matrix)
            smoothed_matrix = np.mean(list(self._transform_buffer), axis=0)

            # Step 2: Prepare crop frame for inference (BGR→RGB, /255, transpose)
            crop_input = self._prepare_crop_frame(crop_frame)

            # Step 3: Prepare source embedding (dot with model initializer)
            source_embedding = self._prepare_source_embedding(source_face.embedding)

            # Step 4: Run ONNX inference
            feed = {
                self._input_name: crop_input,
                self._source_name: source_embedding,
            }
            output = self.session.run([self._output_name], feed)[0][0]

            # Step 5: Normalize output back to image
            swapped_crop = self._normalize_crop_frame(output)

            # Step 6: Create face mask for blending
            crop_mask = self._create_box_mask(swapped_crop)

            # Step 6b: Color-correct swapped face to match original face skin tone
            swapped_crop = self._color_transfer(swapped_crop, crop_frame, crop_mask)

            # Step 7: Paste back onto original frame using smoothed affine matrix
            result = self._paste_back(
                target_frame, swapped_crop, crop_mask, smoothed_matrix
            )
            return result

        except Exception as e:
            logger.error(f"swap_face error: {e}", exc_info=True)
            return target_frame

    def _warp_face(
        self, frame: np.ndarray, landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Warp face region using arcface_128 template alignment."""
        src_pts = landmarks.astype(np.float32)
        # Scale template to crop size
        dst_pts = ARCFACE_128_TEMPLATE * np.array(
            [self.input_size[0], self.input_size[1]], dtype=np.float32
        )

        # Estimate affine transform
        affine_matrix = cv2.estimateAffinePartial2D(
            src_pts, dst_pts, method=cv2.LMEDS
        )[0]
        if affine_matrix is None:
            affine_matrix = np.eye(2, 3, dtype=np.float32)

        crop_frame = cv2.warpAffine(
            frame,
            affine_matrix,
            self.input_size,
            borderMode=cv2.BORDER_REPLICATE,
            flags=cv2.INTER_AREA,
        )
        return crop_frame, affine_matrix

    def _prepare_crop_frame(self, crop_frame: np.ndarray) -> np.ndarray:
        """Prepare crop frame for inswapper: BGR→RGB, /255, CHW, batch."""
        # inswapper uses mean=[0,0,0] std=[1,1,1]
        frame = crop_frame[:, :, ::-1].astype(np.float32) / 255.0
        frame = frame.transpose(2, 0, 1)
        frame = np.expand_dims(frame, axis=0)
        return frame

    def _prepare_source_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """Transform source embedding using model initializer matrix."""
        source_embedding = embedding.reshape((1, -1)).astype(np.float32)

        if self._model_initializer is not None:
            # This is the critical inswapper step: dot product with model initializer
            source_embedding = np.dot(source_embedding, self._model_initializer)
            norm = np.linalg.norm(source_embedding)
            if norm > 0:
                source_embedding = source_embedding / norm

        return source_embedding

    def _normalize_crop_frame(self, output: np.ndarray) -> np.ndarray:
        """Convert model output back to BGR uint8 image."""
        # output shape: (3, 128, 128)
        frame = output.transpose(1, 2, 0)
        frame = np.clip(frame, 0, 1)
        # RGB→BGR
        frame = frame[:, :, ::-1] * 255
        return frame.astype(np.uint8)

    def _create_box_mask(
        self, crop_frame: np.ndarray, blur: float = 0.3, padding: tuple = (0, 0, 0, 0)
    ) -> np.ndarray:
        """Create a soft elliptical mask for seamless blending."""
        h, w = crop_frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.float32)
        center = (w // 2, h // 2)
        # Slightly inset axes so ellipse doesn't touch the edge
        axes = (max(1, w // 2 - 2), max(1, h // 2 - 2))
        cv2.ellipse(mask, center, axes, 0, 0, 360, 1.0, -1)
        # Larger blur for feathered edges (45px minimum)
        blur_amount = max(45, int(blur * min(h, w) * 0.5) * 2 + 1)
        if blur_amount % 2 == 0:
            blur_amount += 1
        mask = cv2.GaussianBlur(mask, (blur_amount, blur_amount), 0)
        return mask

    def _color_transfer(
        self, source: np.ndarray, target: np.ndarray, mask: np.ndarray
    ) -> np.ndarray:
        """Transfer color statistics from target to source in LAB space."""
        source_lab = cv2.cvtColor(source, cv2.COLOR_BGR2LAB).astype(np.float32)
        target_lab = cv2.cvtColor(target, cv2.COLOR_BGR2LAB).astype(np.float32)
        mask_bool = mask > 0.5
        if not mask_bool.any():
            return source
        for i in range(3):
            s_mean = source_lab[:, :, i][mask_bool].mean()
            s_std = source_lab[:, :, i][mask_bool].std() + 1e-6
            t_mean = target_lab[:, :, i][mask_bool].mean()
            t_std = target_lab[:, :, i][mask_bool].std() + 1e-6
            source_lab[:, :, i] = np.clip(
                (source_lab[:, :, i] - s_mean) * (t_std / s_std) + t_mean, 0, 255
            )
        return cv2.cvtColor(source_lab.astype(np.uint8), cv2.COLOR_LAB2BGR)

    def _paste_back(
        self,
        temp_frame: np.ndarray,
        crop_frame: np.ndarray,
        crop_mask: np.ndarray,
        affine_matrix: np.ndarray,
    ) -> np.ndarray:
        """Paste swapped face back onto original frame."""
        temp_h, temp_w = temp_frame.shape[:2]
        crop_h, crop_w = crop_frame.shape[:2]

        inverse_matrix = cv2.invertAffineTransform(affine_matrix)

        # Calculate paste area
        crop_points = np.array(
            [[0, 0], [crop_w, 0], [crop_w, crop_h], [0, crop_h]], dtype=np.float32
        )
        paste_points = cv2.transform(
            crop_points.reshape(1, -1, 2), inverse_matrix
        ).reshape(-1, 2)

        x1 = max(0, int(np.floor(paste_points[:, 0].min())))
        y1 = max(0, int(np.floor(paste_points[:, 1].min())))
        x2 = min(temp_w, int(np.ceil(paste_points[:, 0].max())))
        y2 = min(temp_h, int(np.ceil(paste_points[:, 1].max())))

        paste_w = x2 - x1
        paste_h = y2 - y1

        if paste_w <= 0 or paste_h <= 0:
            return temp_frame

        # Adjust inverse matrix for paste area offset
        paste_matrix = inverse_matrix.copy()
        paste_matrix[0, 2] -= x1
        paste_matrix[1, 2] -= y1

        # Warp crop frame and mask to paste area
        inverse_frame = cv2.warpAffine(
            crop_frame, paste_matrix, (paste_w, paste_h),
            borderMode=cv2.BORDER_REPLICATE
        )
        inverse_mask = cv2.warpAffine(
            crop_mask, paste_matrix, (paste_w, paste_h)
        )
        inverse_mask = np.clip(inverse_mask, 0, 1)
        inverse_mask = np.expand_dims(inverse_mask, axis=-1)

        # Blend
        result = temp_frame.copy()
        paste_region = result[y1:y2, x1:x2].astype(np.float32)
        inverse_frame = inverse_frame.astype(np.float32)
        blended = paste_region * (1 - inverse_mask) + inverse_frame * inverse_mask
        result[y1:y2, x1:x2] = blended.astype(np.uint8)

        return result

    def unload(self):
        self.session = None
        self._model_initializer = None
        self.is_loaded = False
        self._transform_buffer.clear()
        gc.collect()
