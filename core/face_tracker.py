"""
FaceTracker — optical flow tracking between detection frames.

Instead of re-detecting the face every N frames and showing raw video
when detection fails, this module:
1. Detects the face on detection frames
2. Tracks it smoothly between detections using Lucas-Kanade optical flow
3. Never shows the real face — holds the last good swapped frame if all else fails
"""
import cv2
import numpy as np
from typing import Optional
from dataclasses import dataclass
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TrackedFace:
    """Face position tracked via optical flow."""
    center: np.ndarray         # (x, y) centre of face
    bbox: np.ndarray           # [x1, y1, x2, y2]
    landmarks: np.ndarray      # 5-point landmarks
    embedding: np.ndarray      # identity embedding (from last detection)
    confidence: float
    age: int
    gender: str
    tracked_frames: int = 0    # how many frames since last full detection


class FaceTracker:
    """
    Maintains face position between full detections using optical flow.
    Falls back gracefully when tracking is lost.
    """

    LK_PARAMS = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.01),
    )

    def __init__(self, max_track_frames: int = 8):
        self._tracked: Optional[TrackedFace] = None
        self._prev_gray: Optional[np.ndarray] = None
        self._track_points: Optional[np.ndarray] = None
        self._max_track = max_track_frames
        self._lost_count = 0

    def reset(self):
        self._tracked = None
        self._prev_gray = None
        self._track_points = None
        self._lost_count = 0

    def update_from_detection(self, face, frame: np.ndarray):
        """Call this when a full face detection just ran."""
        from core.face_detector import DetectedFace
        if face is None:
            self._lost_count += 1
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        bbox = face.bbox
        cx = int((bbox[0] + bbox[2]) / 2)
        cy = int((bbox[1] + bbox[3]) / 2)

        # Use landmark points + bbox corners as tracking points
        pts = []
        for lm in face.landmarks:
            pts.append([lm[0], lm[1]])
        # Add bbox corners for robustness
        pts.append([bbox[0], bbox[1]])
        pts.append([bbox[2], bbox[3]])
        pts.append([cx, cy])

        track_pts = np.array(pts, dtype=np.float32).reshape(-1, 1, 2)

        self._tracked = TrackedFace(
            center=np.array([cx, cy], dtype=np.float32),
            bbox=bbox.copy(),
            landmarks=face.landmarks.copy(),
            embedding=face.embedding.copy(),
            confidence=face.confidence,
            age=face.age,
            gender=face.gender,
            tracked_frames=0,
        )
        self._prev_gray = gray
        self._track_points = track_pts
        self._lost_count = 0

    def track(self, frame: np.ndarray) -> Optional[TrackedFace]:
        """
        Advance tracking by one frame using optical flow.
        Returns the tracked face, or None if tracking is lost.
        """
        if self._tracked is None or self._prev_gray is None or self._track_points is None:
            return None

        if self._tracked.tracked_frames >= self._max_track:
            # Been tracking too long without a detection — signal for re-detect
            return None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        try:
            new_pts, status, _ = cv2.calcOpticalFlowPyrLK(
                self._prev_gray, gray, self._track_points, None, **self.LK_PARAMS
            )
        except Exception:
            return None

        good_new = new_pts[status.ravel() == 1]
        good_old = self._track_points[status.ravel() == 1]

        if len(good_new) < 3:
            # Too many points lost — tracking failed
            self._lost_count += 1
            return None

        # Estimate translation from tracked points
        delta = good_new.reshape(-1, 2) - good_old.reshape(-1, 2)
        dx = float(np.median(delta[:, 0]))
        dy = float(np.median(delta[:, 1]))

        # Apply translation to bbox and landmarks
        new_bbox = self._tracked.bbox.copy()
        new_bbox[0] += dx; new_bbox[1] += dy
        new_bbox[2] += dx; new_bbox[3] += dy

        new_landmarks = self._tracked.landmarks.copy()
        new_landmarks[:, 0] += dx
        new_landmarks[:, 1] += dy

        new_cx = float(self._tracked.center[0] + dx)
        new_cy = float(self._tracked.center[1] + dy)

        # Update state
        self._tracked = TrackedFace(
            center=np.array([new_cx, new_cy], dtype=np.float32),
            bbox=new_bbox,
            landmarks=new_landmarks,
            embedding=self._tracked.embedding,  # identity stays the same
            confidence=self._tracked.confidence * 0.99,  # decay confidence slightly
            age=self._tracked.age,
            gender=self._tracked.gender,
            tracked_frames=self._tracked.tracked_frames + 1,
        )
        self._prev_gray = gray
        self._track_points = good_new.reshape(-1, 1, 2)
        self._lost_count = 0

        return self._tracked

    def get_last(self) -> Optional[TrackedFace]:
        """Return last known tracked face (used to avoid showing real face)."""
        return self._tracked

    @property
    def is_tracking(self) -> bool:
        return self._tracked is not None and self._lost_count < 3
