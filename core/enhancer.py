import os
import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)


class FaceEnhancer:
    def __init__(self):
        self._loaded = False
        self._gfpgan = None

    def load(self) -> bool:
        try:
            from gfpgan import GFPGANer
            model_path = os.path.expanduser('~/xeroclaw/echelon/models/GFPGANv1.4.pth')
            if not os.path.exists(model_path):
                logger.info("GFPGAN model not found at %s, enhancement disabled", model_path)
                return False
            self._gfpgan = GFPGANer(
                model_path=model_path,
                upscale=1,
                arch='clean',
                channel_multiplier=2,
                bg_upsampler=None
            )
            self._loaded = True
            logger.info("GFPGAN enhancer loaded")
            return True
        except Exception as e:
            logger.info("GFPGAN not available: %s", e)
            return False

    def enhance(self, frame: np.ndarray) -> np.ndarray:
        if not self._loaded:
            return frame
        try:
            _, _, output = self._gfpgan.enhance(
                frame, has_aligned=False, only_center_face=True, paste_back=True
            )
            return output
        except Exception:
            return frame

    def is_loaded(self) -> bool:
        return self._loaded
