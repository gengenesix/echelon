import os
import sys
import hashlib
import requests
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

# Lazy import insightface — don't crash at startup if onnxruntime DLL fails
# This is the top-level import that triggers the DLL load
def _try_import_insightface():
    try:
        import insightface
        return insightface
    except (ImportError, OSError) as e:
        return None

class ModelDownloader(QThread):
    progress_updated = pyqtSignal(int, str)
    download_finished = pyqtSignal(str)
    download_failed = pyqtSignal(str, str)
    all_done = pyqtSignal()

    MODELS = {
        "inswapper_128.onnx": {
            "urls": [
                "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
                "https://huggingface.co/deepinsight/inswapper/resolve/main/inswapper_128.onnx",
            ],
            "size_mb": 554,
        }
    }

    def __init__(self, models_dir: str, parent=None):
        super().__init__(parent)
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._stop = False

    def run(self):
        for name, info in self.MODELS.items():
            dest = self.models_dir / name
            if dest.exists():
                self.download_finished.emit(name)
                continue
            success = False
            for url in info["urls"]:
                try:
                    self.progress_updated.emit(0, f"Downloading {name}...")
                    self._download_with_progress(url, dest, name)
                    self.download_finished.emit(name)
                    success = True
                    break
                except Exception as e:
                    continue
            if not success:
                self.download_failed.emit(name, "All download URLs failed")
                return
        # Download buffalo_l via insightface
        try:
            self.progress_updated.emit(95, "Downloading InsightFace buffalo_l model...")
            app = insightface.app.FaceAnalysis(name='buffalo_l', root=str(self.models_dir))
            app.prepare(ctx_id=-1, det_size=(640, 640))
            self.progress_updated.emit(100, "All models ready")
        except Exception as e:
            pass
        self.all_done.emit()

    def _download_with_progress(self, url: str, dest: Path, name: str):
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        total = int(response.headers.get('content-length', 0))
        downloaded = 0
        with open(dest, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if self._stop:
                    return
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = int(downloaded * 100 / total)
                    mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    self.progress_updated.emit(pct, f"Downloading {name}: {mb:.1f}/{total_mb:.1f} MB")

    def check_models_exist(self) -> dict:
        result = {}
        for name in self.MODELS:
            result[name] = (self.models_dir / name).exists()
        buffalo_path = self.models_dir / "buffalo_l"
        result["buffalo_l"] = buffalo_path.exists() and any(buffalo_path.iterdir()) if buffalo_path.exists() else False
        return result

    def verify_checksum(self, path: Path, expected_sha256: str) -> bool:
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest() == expected_sha256

    def stop(self):
        self._stop = True
