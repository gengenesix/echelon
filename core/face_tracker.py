"""
FaceTracker v2 — full affine tracking with Shi-Tomasi feature detection.

What was wrong with v1 (translation-only):
  - tracked dx/dy median shift only — head rotation/scale caused landmark drift
  - used fixed landmark+corner points — these fall on smooth skin with no texture,
    causing LK to lose them immediately when there's any motion
  - when re-detection fired after drift, position snapped visibly → glitch jump

What's fixed here:
  1. cv2.goodFeaturesToTrack() inside the face bbox — finds high-texture pixels
     (eyebrows, nostrils, mouth corners) that LK can actually track reliably
  2. cv2.estimateAffinePartial2D + RANSAC — full rotation+scale+translation,
     face stays aligned when user rotates head or moves closer/farther
  3. Smooth re-detection blend — when detection position jumps > 15px from
     tracked position, interpolate 65% toward detected, prevents snap glitch
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
    center:        np.ndarray   # (x, y) centre
    bbox:          np.ndarray   # [x1, y1, x2, y2]
    landmarks:     np.ndarray   # 5-point landmarks
    embedding:     np.ndarray   # identity embedding (from last detection)
    confidence:    float
    age:           int
    gender:        str
    tracked_frames: int = 0


class FaceTracker:

    LK_PARAMS = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.01),
    )
    # Shi-Tomasi good features — finds corners/edges with actual texture
    FEATURE_PARAMS = dict(
        maxCorners=40,    # more candidates → tracking survives partial occlusion
        qualityLevel=0.008,
        minDistance=4,
        blockSize=5,
    )

    def __init__(self, max_track_frames: int = 8):
        self._tracked:       Optional[TrackedFace] = None
        self._prev_gray:     Optional[np.ndarray]  = None
        self._track_points:  Optional[np.ndarray]  = None
        self._max_track      = max_track_frames
        self._lost_count     = 0

    def reset(self):
        self._tracked      = None
        self._prev_gray    = None
        self._track_points = None
        self._lost_count   = 0

    # ── Detection update ──────────────────────────────────────────────────────

    def update_from_detection(self, face, frame: np.ndarray):
        """Call this when a full face detection just ran."""
        if face is None:
            self._lost_count += 1
            return

        gray      = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        bbox      = face.bbox.copy()
        landmarks = face.landmarks.copy()

        # Smooth transition: if we were already tracking and the new detection
        # is far from where we tracked to, blend toward the detected position
        # rather than snapping — eliminates the 1-frame jump glitch.
        if self._tracked is not None:
            old_cx, old_cy = self._tracked.center
            new_cx = (bbox[0] + bbox[2]) / 2
            new_cy = (bbox[1] + bbox[3]) / 2
            dist   = float(np.hypot(new_cx - old_cx, new_cy - old_cy))
            if dist > 15:
                alpha     = 0.65  # lean mostly toward fresh detection
                bbox      = self._tracked.bbox      * (1 - alpha) + bbox      * alpha
                landmarks = self._tracked.landmarks * (1 - alpha) + landmarks * alpha

        cx = float((bbox[0] + bbox[2]) / 2)
        cy = float((bbox[1] + bbox[3]) / 2)

        track_pts = self._get_face_features(gray, bbox, face.landmarks)

        self._tracked = TrackedFace(
            center        = np.array([cx, cy], dtype=np.float32),
            bbox          = bbox,
            landmarks     = landmarks,
            embedding     = face.embedding.copy(),   # always use fresh embedding
            confidence    = face.confidence,
            age           = face.age,
            gender        = face.gender,
            tracked_frames= 0,
        )
        self._prev_gray    = gray
        self._track_points = track_pts
        self._lost_count   = 0

    # ── Per-frame tracking ────────────────────────────────────────────────────

    def track(self, frame: np.ndarray) -> Optional[TrackedFace]:
        """
        Advance tracking one frame via LK optical flow + affine estimation.
        Returns updated TrackedFace, or None if tracking is lost.
        """
        if (self._tracked is None
                or self._prev_gray    is None
                or self._track_points is None):
            return None

        if self._tracked.tracked_frames >= self._max_track:
            return None   # signal pipeline to re-detect

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
            self._lost_count += 1
            return None

        # Full affine estimation (rotation + uniform scale + translation).
        # RANSAC discards outlier points that slipped off the face.
        M, inliers = cv2.estimateAffinePartial2D(
            good_old.reshape(-1, 1, 2),
            good_new.reshape(-1, 1, 2),
            method=cv2.RANSAC,
            ransacReprojThreshold=3.0,
        )
        if M is None or (inliers is not None and int(inliers.sum()) < 3):
            self._lost_count += 1
            return None

        # Transform bbox corners + landmarks through the affine
        x1, y1, x2, y2 = self._tracked.bbox
        corners      = np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]], dtype=np.float32)
        new_corners  = self._apply_affine(corners, M)
        new_bbox     = np.array([
            new_corners[:,0].min(), new_corners[:,1].min(),
            new_corners[:,0].max(), new_corners[:,1].max(),
        ])
        new_lm       = self._apply_affine(self._tracked.landmarks, M)
        new_center   = np.array(
            [(new_bbox[0]+new_bbox[2])/2, (new_bbox[1]+new_bbox[3])/2],
            dtype=np.float32,
        )

        self._tracked = TrackedFace(
            center        = new_center,
            bbox          = new_bbox,
            landmarks     = new_lm,
            embedding     = self._tracked.embedding,
            confidence    = self._tracked.confidence * 0.99,
            age           = self._tracked.age,
            gender        = self._tracked.gender,
            tracked_frames= self._tracked.tracked_frames + 1,
        )
        self._prev_gray    = gray
        self._track_points = good_new.reshape(-1, 1, 2)
        self._lost_count   = 0
        return self._tracked

    def get_last(self) -> Optional[TrackedFace]:
        return self._tracked

    @property
    def is_tracking(self) -> bool:
        return self._tracked is not None and self._lost_count < 3

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_face_features(
        self, gray: np.ndarray, bbox: np.ndarray, landmarks: np.ndarray
    ) -> np.ndarray:
        """
        Find good texture features (corners, edges) within the face bbox using
        Shi-Tomasi corner detection.  These have actual gradient signal that
        Lucas-Kanade can track across frames — far better than fixed landmark
        points which land on smooth skin and drift immediately.
        Falls back to landmark points if the face region has no detectable features
        (e.g. very small face or motion blur).
        """
        h, w = gray.shape
        x1 = max(0, int(bbox[0]))
        y1 = max(0, int(bbox[1]))
        x2 = min(w, int(bbox[2]))
        y2 = min(h, int(bbox[3]))

        features = None
        if x2 > x1 + 10 and y2 > y1 + 10:
            mask = np.zeros_like(gray)
            mask[y1:y2, x1:x2] = 255
            features = cv2.goodFeaturesToTrack(gray, mask=mask, **self.FEATURE_PARAMS)

        if features is None or len(features) < 4:
            features = landmarks.reshape(-1, 1, 2).astype(np.float32)

        return features

    @staticmethod
    def _apply_affine(pts: np.ndarray, M: np.ndarray) -> np.ndarray:
        """Apply 2×3 affine matrix M to an (N, 2) array of points."""
        p    = pts.reshape(-1, 2)
        ones = np.ones((len(p), 1), dtype=np.float32)
        return (M @ np.hstack([p.astype(np.float32), ones]).T).T
