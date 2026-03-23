"""
FaceGallery — persists up to 5 named face embeddings for instant re-use.
Detection is done externally (via FaceLoadThread); gallery only stores results.
"""
import shutil
from pathlib import Path
from typing import Optional, List, Dict
import cv2
import numpy as np

from core.face_detector import DetectedFace
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_GALLERY_FACES = 5


class FaceGallery:
    def __init__(self, data_dir: str):
        self.faces_dir = Path(data_dir) / "faces"
        self.faces_dir.mkdir(parents=True, exist_ok=True)

    def save_face(self, name: str, image_path: str, face: DetectedFace) -> bool:
        """Save a pre-detected face to the gallery (cropped image + embedding)."""
        if not name or not name.strip():
            logger.warning("FaceGallery.save_face: name is empty")
            return False
        name = name.strip()
        if len(self.list_faces()) >= MAX_GALLERY_FACES and not self._face_exists(name):
            logger.warning(f"FaceGallery: max {MAX_GALLERY_FACES} faces reached")
            return False
        try:
            face_dir = self.faces_dir / name
            face_dir.mkdir(parents=True, exist_ok=True)

            # Save the embedding
            emb_path = face_dir / "embedding.npy"
            np.save(str(emb_path), face.embedding)

            # Save cropped square preview image
            img = cv2.imread(image_path)
            if img is not None:
                h, w = img.shape[:2]
                size = min(h, w)
                y0 = (h - size) // 2
                x0 = (w - size) // 2
                crop = img[y0:y0 + size, x0:x0 + size]
                crop = cv2.resize(crop, (180, 180))
                cv2.imwrite(str(face_dir / "preview.jpg"), crop)

            logger.info(f"FaceGallery: saved '{name}'")
            return True
        except Exception as e:
            logger.error(f"FaceGallery.save_face error: {e}")
            return False

    def load_face(self, name: str) -> Optional[DetectedFace]:
        """Load cached embedding — instant, no detection needed."""
        emb_path = self.faces_dir / name / "embedding.npy"
        if not emb_path.exists():
            logger.warning(f"FaceGallery: no embedding for '{name}'")
            return None
        try:
            embedding = np.load(str(emb_path))
            return DetectedFace(
                bbox=np.zeros(4, dtype=np.float32),
                landmarks=np.zeros((5, 2), dtype=np.float32),
                embedding=embedding,
                confidence=1.0,
                age=0,
                gender="F",
            )
        except Exception as e:
            logger.error(f"FaceGallery.load_face error: {e}")
            return None

    def list_faces(self) -> List[Dict]:
        """Return list of {name, preview_path, has_embedding} dicts."""
        result = []
        for d in sorted(self.faces_dir.iterdir()):
            if not d.is_dir():
                continue
            emb = d / "embedding.npy"
            preview = d / "preview.jpg"
            result.append({
                "name": d.name,
                "preview_path": str(preview) if preview.exists() else "",
                "has_embedding": emb.exists(),
            })
        return result

    def delete_face(self, name: str) -> bool:
        """Remove a saved face directory."""
        face_dir = self.faces_dir / name
        if not face_dir.exists():
            return False
        try:
            shutil.rmtree(str(face_dir))
            logger.info(f"FaceGallery: deleted '{name}'")
            return True
        except Exception as e:
            logger.error(f"FaceGallery.delete_face error: {e}")
            return False

    def _face_exists(self, name: str) -> bool:
        return (self.faces_dir / name).is_dir()
