import os
import sys
import hashlib
import requests
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal


class ModelDownloader(QThread):
    progress_updated = pyqtSignal(int, str)
    download_finished = pyqtSignal(str)
    download_failed = pyqtSignal(str, str)
    all_done = pyqtSignal()

    # Working public mirrors for inswapper_128.onnx
    INSWAPPER_URLS = [
        # HuggingFace direct (may need no auth)
        "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
        # Alternative HF space mirror
        "https://huggingface.co/thebiglaskowski/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
        # civitai proxy (public)
        "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/inswapper_128.onnx",
        # Another mirror
        "https://github.com/facefusion/facefusion-assets/releases/download/models/inswapper_128.onnx",
        "https://github.com/facefusion/facefusion-assets/releases/download/models-3.0.0/inswapper_128_fp16.onnx",
    ]

    # buffalo_l individual files (InsightFace detection model)
    BUFFALO_L_FILES = {
        "1k3d68.onnx": "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
        # We'll download the zip and extract
    }

    # Direct buffalo_l file URLs (from insightface releases)
    BUFFALO_L_DIRECT = [
        ("det_10g.onnx",    "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/det_10g.onnx"),
        ("1k3d68.onnx",     "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/1k3d68.onnx"),
        ("2d106det.onnx",   "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/2d106det.onnx"),
        ("genderage.onnx",  "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/genderage.onnx"),
        ("w600k_r50.onnx",  "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/w600k_r50.onnx"),
    ]

    def __init__(self, models_dir: str, parent=None):
        super().__init__(parent)
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._stop = False

    def run(self):
        # Step 1: Download inswapper_128.onnx
        inswapper_dest = self.models_dir / "inswapper_128.onnx"
        if not inswapper_dest.exists():
            self.progress_updated.emit(0, "Downloading face swap model...")
            success = False
            last_error = "Unknown error"
            for url in self.INSWAPPER_URLS:
                if self._stop:
                    return
                try:
                    self.progress_updated.emit(0, f"Trying mirror...")
                    self._download_with_progress(url, inswapper_dest, "inswapper_128.onnx", 0, 85)
                    success = True
                    break
                except Exception as e:
                    last_error = str(e)
                    if inswapper_dest.exists():
                        inswapper_dest.unlink()
                    continue

            if not success:
                self.download_failed.emit("inswapper_128.onnx",
                    f"Download failed. Please download manually from:\n"
                    f"https://github.com/facefusion/facefusion-assets/releases\n"
                    f"and place in: {self.models_dir}")
                return

        self.download_finished.emit("inswapper_128.onnx")
        self.progress_updated.emit(88, "Downloading face detection models...")

        # Step 2: Download buffalo_l models
        buffalo_dir = self.models_dir / "models" / "buffalo_l"
        buffalo_dir.mkdir(parents=True, exist_ok=True)

        # Try downloading via insightface auto-download first
        try:
            import insightface
            app = insightface.app.FaceAnalysis(name='buffalo_l', root=str(self.models_dir))
            app.prepare(ctx_id=-1, det_size=(640, 640))
            self.progress_updated.emit(100, "All models ready!")
            self.all_done.emit()
            return
        except Exception:
            pass

        # Fall back to direct downloads
        needed = ["det_10g.onnx", "1k3d68.onnx", "2d106det.onnx", "genderage.onnx", "w600k_r50.onnx"]
        existing = [f for f in needed if (buffalo_dir / f).exists()]
        missing = [f for f in needed if f not in existing]

        if missing:
            for i, (fname, url) in enumerate(self.BUFFALO_L_DIRECT):
                if fname not in missing or self._stop:
                    continue
                dest = buffalo_dir / fname
                try:
                    pct = 88 + int(i * 10 / len(self.BUFFALO_L_DIRECT))
                    self.progress_updated.emit(pct, f"Downloading {fname}...")
                    self._download_with_progress(url, dest, fname, pct, pct + 2)
                except Exception:
                    pass  # Non-fatal — app will download on first launch

        self.progress_updated.emit(100, "Models ready!")
        self.all_done.emit()

    def _download_with_progress(self, url: str, dest: Path, name: str,
                                 pct_start: int = 0, pct_end: int = 100):
        headers = {"User-Agent": "Mozilla/5.0 EchelonApp/2.0"}
        response = requests.get(url, stream=True, timeout=60, headers=headers,
                                allow_redirects=True)
        response.raise_for_status()

        total = int(response.headers.get('content-length', 0))
        downloaded = 0
        pct_range = pct_end - pct_start

        with open(dest, 'wb') as f:
            for chunk in response.iter_content(chunk_size=65536):
                if self._stop:
                    return
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = pct_start + int(downloaded * pct_range / total)
                    mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    self.progress_updated.emit(
                        min(pct, pct_end),
                        f"Downloading {name}: {mb:.0f} / {total_mb:.0f} MB"
                    )

    def check_models_exist(self) -> dict:
        result = {
            "inswapper_128.onnx": (self.models_dir / "inswapper_128.onnx").exists()
        }
        buffalo_path = self.models_dir / "models" / "buffalo_l"
        result["buffalo_l"] = (buffalo_path.exists() and
                               any(buffalo_path.glob("*.onnx")))
        return result

    def stop(self):
        self._stop = True
