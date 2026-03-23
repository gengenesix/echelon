"""
PerformanceTuner — auto-tunes pipeline settings based on measured FPS.
Wire into EchelonPipeline via enable_auto_tune(True).
"""
from utils.logger import get_logger

logger = get_logger(__name__)


class PerformanceTuner:
    """Auto-tunes settings based on measured FPS to hit target_fps."""

    def __init__(self, target_fps: float = 15.0):
        self.target_fps = target_fps
        self._fps_history: list = []

    def record_fps(self, fps: float):
        self._fps_history.append(fps)
        if len(self._fps_history) > 30:
            self._fps_history.pop(0)

    def get_recommendations(self) -> dict:
        if not self._fps_history:
            return {'frame_skip': 1, 'detect_interval': 5, 'resolution': 'balanced'}
        avg_fps = sum(self._fps_history) / len(self._fps_history)
        if avg_fps < 8:
            return {'frame_skip': 3, 'detect_interval': 10, 'resolution': 'speed'}
        elif avg_fps < 15:
            return {'frame_skip': 2, 'detect_interval': 5, 'resolution': 'speed'}
        elif avg_fps < 20:
            return {'frame_skip': 1, 'detect_interval': 3, 'resolution': 'balanced'}
        return {'frame_skip': 0, 'detect_interval': 1, 'resolution': 'quality'}

    def auto_tune(self, pipeline) -> str:
        """Apply recommended settings to pipeline. Returns a description string."""
        recs = self.get_recommendations()
        pipeline.frame_skip = recs['frame_skip']
        pipeline.face_detector._detect_interval = recs['detect_interval']
        pipeline.set_performance_mode(recs['resolution'])
        desc = (
            f"skip={recs['frame_skip']}, "
            f"detect_every={recs['detect_interval']}, "
            f"res={recs['resolution']}"
        )
        logger.info(f"PerformanceTuner auto-tune: {desc}")
        return desc
