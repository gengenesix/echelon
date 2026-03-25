import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _get_log_path() -> Path:
    """Platform-aware log path — matches config/manager.py BASE_DIR."""
    if sys.platform == "win32":
        import os
        appdata = os.environ.get("APPDATA", str(Path.home()))
        return Path(appdata) / "Echelon" / "logs" / "echelon.log"
    return Path.home() / ".echelon" / "logs" / "echelon.log"


LOG_PATH = _get_log_path()


def setup_logging(level="INFO") -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    if not root_logger.handlers:
        fh = RotatingFileHandler(str(LOG_PATH), maxBytes=5 * 1024 * 1024, backupCount=3)
        fh.setLevel(numeric_level)
        fh.setFormatter(fmt)
        root_logger.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        root_logger.addHandler(ch)
    return root_logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
