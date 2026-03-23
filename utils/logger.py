import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_PATH = Path.home() / "xeroclaw" / "echelon" / "logs" / "echelon.log"

def setup_logging(level="INFO") -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    if not root_logger.handlers:
        fh = RotatingFileHandler(str(LOG_PATH), maxBytes=5*1024*1024, backupCount=3)
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
