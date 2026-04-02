import collections
import cv2
import numpy as np
import time
from dataclasses import dataclass
from typing import List, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DetectedFace:
    bbox: np.ndarray
    landmarks: np.ndarray
    embedding: np.ndarray
    confidence: float
    age: int
    gender: str


# ── Module-level singleton — loaded once, reused everywhere ──────────────────
_global_detector: "FaceDetector | None" = None
_global_models_dir: str = ""
_global_providers: list = []


def get_global_detector(models_dir: str, providers: list) -> "FaceDetector":
    """Return the cached global detector, loading it only on first call."""
    global _global_detector, _global_models_dir, _global_providers
    if (
        _global_detector is not None
        and _global_detector.is_loaded
        and _global_models_dir == models_dir
        and _global_providers == providers
    ):
        return _global_detector
    det = FaceDetector(models_dir, providers)
    if det.load():
        _global_detector = det
        _global_models_dir = models_dir
        _global_providers = list(providers)
    return det


class FaceDetector:
    def __init__(self, models_dir: str, providers: list):
        self.app = None
        self.models_dir = models_dir
        self.providers = providers
        self.is_loaded = False
        self._last_face = None
        self._detect_interval = 5
        self._frame_count_tracked = 0
        self._landmark_buffer = collections.deque(maxlen=3)
        self._last_faces = None
        self._frame_count_tracked_multi = 0

    def load(self) -> bool:
        try:
            import insightface
            t0 = time.time()
            self.app = insightface.app.FaceAnalysis(
                name='buffalo_l',
                root=self.models_dir,
                providers=self.providers,
                # detection + recognition is all we need for face swap
                # (skips 3D landmark & genderage — 2× faster to load)
                allowed_modules=['detection', 'recognition']
            )
            ctx_id = 0 if any("CUDA" in p for p in self.providers) else -1
            # 320×320 det_size = ~3× faster than 640×640 on CPU with same quality
            self.app.prepare(ctx_id=ctx_id, det_size=(320, 320))
            # Verify detection model actually loaded
            if not hasattr(self.app, 'det_model') or self.app.det_model is None:
                # Fallback: load without module restriction
                self.app = insightface.app.FaceAnalysis(
                    name='buffalo_l',
                    root=self.models_dir,
                    providers=self.providers,
                )
                self.app.prepare(ctx_id=ctx_id, det_size=(320, 320))
            self.is_loaded = True
            logger.info(f"FaceDetector loaded in {time.time()-t0:.2f}s")
            return True
        except Exception as e:
            logger.error(f"FaceDetector load failed: {e}")
            return False

    def detect_faces(self, frame: np.ndarray) -> List[DetectedFace]:
        if not self.is_loaded or frame is None:
            return []
        try:
            faces = self.app.get(frame)
            result = []
            for f in faces:
                embedding = (f.embedding if hasattr(f, 'embedding') and f.embedding is not None
                             else np.zeros(512))
                det_score = float(f.det_score) if hasattr(f, 'det_score') else 0.0
                age = int(f.age) if hasattr(f, 'age') and f.age is not None else 0
                gender = "M" if hasattr(f, 'gender') and f.gender == 1 else "F"
                landmarks = (f.kps if hasattr(f, 'kps') and f.kps is not None
                             else np.zeros((5, 2)))
                result.append(DetectedFace(
                    bbox=f.bbox,
                    landmarks=landmarks,
                    embedding=embedding,
                    confidence=det_score,
                    age=age,
                    gender=gender,
                ))
            return sorted(result, key=lambda x: x.confidence, reverse=True)
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return []

    def get_primary_face(self, frame: np.ndarray) -> Optional[DetectedFace]:
        faces = self.detect_faces(frame)
        if not faces:
            return None
        def area(f):
            b = f.bbox
            return (b[2] - b[0]) * (b[3] - b[1])
        return max(faces, key=area)

    def get_tracked_face(self, frame: np.ndarray) -> Optional[DetectedFace]:
        """Cached detection with landmark smoothing to reduce jitter."""
        self._frame_count_tracked += 1
        if self._frame_count_tracked % self._detect_interval == 0 or self._last_face is None:
            face = self.get_primary_face(frame)
            if face is not None:
                self._landmark_buffer.append(face.landmarks.copy())
                if len(self._landmark_buffer) > 1:
                    smoothed = np.mean(list(self._landmark_buffer), axis=0)
                    face = DetectedFace(
                        bbox=face.bbox,
                        landmarks=smoothed,
                        embedding=face.embedding,
                        confidence=face.confidence,
                        age=face.age,
                        gender=face.gender,
                    )
            self._last_face = face
        return self._last_face

    def get_tracked_faces(self, frame: np.ndarray) -> List[DetectedFace]:
        self._frame_count_tracked_multi += 1
        if (self._frame_count_tracked_multi % self._detect_interval == 0
                or self._last_faces is None):
            self._last_faces = self.detect_faces(frame)
        return self._last_faces

    def reset_tracking(self):
        self._last_face = None
        self._frame_count_tracked = 0
        self._landmark_buffer.clear()
        self._last_faces = None
        self._frame_count_tracked_multi = 0

    def extract_face_from_image(self, image_path: str) -> Optional[DetectedFace]:
        """Extract face from a still image. Resizes large images for speed."""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
            h, w = img.shape[:2]
            max_side = 800
            if max(h, w) > max_side:
                scale = max_side / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)),
                                 interpolation=cv2.INTER_AREA)
            return self.get_primary_face(img)
        except Exception as e:
            logger.error(f"extract_face_from_image error: {e}")
            return None
