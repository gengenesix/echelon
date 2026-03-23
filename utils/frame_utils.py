import numpy as np
import cv2
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt

def bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

def rgb_to_bgr(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

def resize_frame(frame: np.ndarray, width: int, height: int, keep_aspect: bool = True) -> np.ndarray:
    if not keep_aspect:
        return cv2.resize(frame, (width, height))
    h, w = frame.shape[:2]
    scale = min(width / w, height / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(frame, (new_w, new_h))

def frame_to_qpixmap(frame: np.ndarray) -> QPixmap:
    rgb = bgr_to_rgb(frame)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w
    qimage = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimage)

def center_crop_square(frame: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    size = min(h, w)
    y = (h - size) // 2
    x = (w - size) // 2
    return frame[y:y+size, x:x+size]

def normalize_frame(frame: np.ndarray) -> np.ndarray:
    return (frame.astype(np.float32) / 127.5) - 1.0

def denormalize_frame(frame: np.ndarray) -> np.ndarray:
    return np.clip((frame + 1.0) * 127.5, 0, 255).astype(np.uint8)
