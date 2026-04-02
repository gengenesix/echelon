"""
Model downloader for Echelon.
Downloads inswapper_128.onnx and buffalo_l detection models with
multi-mirror fallback and integrity verification.
"""
import os
import hashlib
import requests
import zipfile
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal


class ModelDownloader(QThread):
    progress_updated = pyqtSignal(int, str)
    download_finished = pyqtSignal(str)
    download_failed = pyqtSignal(str, str)
    all_done = pyqtSignal()

    # ── inswapper_128.onnx mirrors (tried in order) ──────────────────────────
    INSWAPPER_URLS = [
        "https://github.com/facefusion/facefusion-assets/releases/download/models/inswapper_128.onnx",
        "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
        "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/inswapper_128.onnx",
        "https://huggingface.co/thebiglaskowski/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
        "https://github.com/facefusion/facefusion-assets/releases/download/models-3.0.0/inswapper_128_fp16.onnx",
    ]
    INSWAPPER_MIN_SIZE = 500 * 1024 * 1024  # 500 MB minimum (real file is ~554 MB)

    # ── buffalo_l individual file mirrors ────────────────────────────────────
    # Each tuple: (filename, [url_mirrors...])
    BUFFALO_L_FILES = [
        ("det_10g.onnx", [
            "https://github.com/deepinsight/insightface/releases/download/v0.7/det_10g.onnx",
            "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/det_10g.onnx",
            "https://huggingface.co/MonsterMMORPG/insightface_buffalo_l/resolve/main/det_10g.onnx",
        ]),
        ("1k3d68.onnx", [
            "https://github.com/deepinsight/insightface/releases/download/v0.7/1k3d68.onnx",
            "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/1k3d68.onnx",
            "https://huggingface.co/MonsterMMORPG/insightface_buffalo_l/resolve/main/1k3d68.onnx",
        ]),
        ("2d106det.onnx", [
            "https://github.com/deepinsight/insightface/releases/download/v0.7/2d106det.onnx",
            "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/2d106det.onnx",
            "https://huggingface.co/MonsterMMORPG/insightface_buffalo_l/resolve/main/2d106det.onnx",
        ]),
        ("genderage.onnx", [
            "https://github.com/deepinsight/insightface/releases/download/v0.7/genderage.onnx",
            "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/genderage.onnx",
            "https://huggingface.co/MonsterMMORPG/insightface_buffalo_l/resolve/main/genderage.onnx",
        ]),
        ("w600k_r50.onnx", [
            "https://github.com/deepinsight/insightface/releases/download/v0.7/w600k_r50.onnx",
            "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/w600k_r50.onnx",
            "https://huggingface.co/MonsterMMORPG/insightface_buffalo_l/resolve/main/w600k_r50.onnx",
        ]),
    ]
    # Minimum file sizes in bytes (to detect truncated/corrupt downloads)
    BUFFALO_MIN_SIZES = {
        "det_10g.onnx":   16 * 1024 * 1024,   # ~16 MB
        "1k3d68.onnx":    140 * 1024 * 1024,  # ~140 MB (large — 3D landmark)
        "2d106det.onnx":  5 * 1024 * 1024,    # ~5 MB
        "genderage.onnx": 1 * 1024 * 1024,    # ~1 MB
        "w600k_r50.onnx": 166 * 1024 * 1024,  # ~166 MB
    }

    # buffalo_l zip fallback (insightface CDN)
    BUFFALO_ZIP_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Echelon/2.1",
        "Accept": "*/*",
    }

    def __init__(self, models_dir: str, parent=None):
        super().__init__(parent)
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._stop = False

    def stop(self):
        self._stop = True

    # ── Public helpers ────────────────────────────────────────────────────────

    def check_models_exist(self) -> dict:
        return {
            "inswapper_128.onnx": self._inswapper_ok(),
            "buffalo_l": self._buffalo_ok(),
        }

    # ── Internal checks ───────────────────────────────────────────────────────

    def _inswapper_ok(self) -> bool:
        p = self.models_dir / "inswapper_128.onnx"
        return p.exists() and p.stat().st_size >= self.INSWAPPER_MIN_SIZE

    def _buffalo_ok(self) -> bool:
        buffalo_dir = self.models_dir / "models" / "buffalo_l"
        if not buffalo_dir.exists():
            return False
        # Require at least det_10g.onnx and w600k_r50.onnx (the essential ones)
        required = ["det_10g.onnx", "w600k_r50.onnx"]
        for f in required:
            fp = buffalo_dir / f
            min_size = self.BUFFALO_MIN_SIZES.get(f, 1024)
            if not fp.exists() or fp.stat().st_size < min_size:
                return False
        return True

    def _file_valid(self, path: Path, min_size: int) -> bool:
        return path.exists() and path.stat().st_size >= min_size

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self):
        total_steps = 2
        step = 0

        # ── Step 1: inswapper_128.onnx ────────────────────────────────────────
        inswapper_dest = self.models_dir / "inswapper_128.onnx"
        if not self._inswapper_ok():
            # Remove corrupt partial file
            if inswapper_dest.exists():
                inswapper_dest.unlink()
            self.progress_updated.emit(2, "Downloading face swap model (inswapper_128.onnx ~554 MB)...")
            success = self._download_with_mirrors(
                self.INSWAPPER_URLS, inswapper_dest,
                "inswapper_128.onnx", pct_start=2, pct_end=78,
                min_size=self.INSWAPPER_MIN_SIZE
            )
            if not success:
                self.download_failed.emit(
                    "inswapper_128.onnx",
                    "All download mirrors failed.\n\n"
                    "Please download manually from:\n"
                    "https://github.com/facefusion/facefusion-assets/releases\n\n"
                    f"Save as: {inswapper_dest}"
                )
                return
        else:
            self.progress_updated.emit(78, "Face swap model: already present ✓")

        self.download_finished.emit("inswapper_128.onnx")
        step += 1

        # ── Step 2: buffalo_l detection models ────────────────────────────────
        if not self._buffalo_ok():
            self.progress_updated.emit(80, "Downloading face detection models (buffalo_l ~360 MB)...")
            buffalo_dir = self.models_dir / "models" / "buffalo_l"
            buffalo_dir.mkdir(parents=True, exist_ok=True)

            # First: try insightface auto-download (fastest if it works)
            auto_ok = self._try_insightface_auto_download(buffalo_dir)

            if not auto_ok:
                # Second: try downloading individual files
                files_ok = self._download_buffalo_files(buffalo_dir, pct_start=80, pct_end=98)

                if not files_ok:
                    # Third: try downloading the zip
                    zip_ok = self._download_buffalo_zip(buffalo_dir)
                    if not zip_ok:
                        self.download_failed.emit(
                            "buffalo_l",
                            "Could not download face detection models.\n\n"
                            "Please check your internet connection and retry.\n"
                            "If the problem persists, try running:\n"
                            "  python -c \"import insightface; "
                            "insightface.app.FaceAnalysis(name='buffalo_l').prepare(ctx_id=-1)\""
                        )
                        return
        else:
            self.progress_updated.emit(98, "Detection models: already present ✓")

        self.download_finished.emit("buffalo_l")
        self.progress_updated.emit(100, "✅ All models ready!")
        self.all_done.emit()

    # ── Download helpers ──────────────────────────────────────────────────────

    def _download_with_mirrors(self, urls: list, dest: Path, name: str,
                                pct_start: int, pct_end: int, min_size: int = 0) -> bool:
        for i, url in enumerate(urls):
            if self._stop:
                return False
            mirror_num = i + 1
            self.progress_updated.emit(
                pct_start,
                f"Downloading {name} (mirror {mirror_num}/{len(urls)})..."
            )
            try:
                self._stream_download(url, dest, name, pct_start, pct_end)
                if self._file_valid(dest, min_size):
                    return True
                else:
                    if dest.exists():
                        dest.unlink()
            except Exception as e:
                if dest.exists():
                    try:
                        dest.unlink()
                    except Exception:
                        pass
                self.progress_updated.emit(
                    pct_start,
                    f"Mirror {mirror_num} failed ({type(e).__name__}), trying next..."
                )
                continue
        return False

    def _stream_download(self, url: str, dest: Path, name: str,
                          pct_start: int, pct_end: int):
        response = requests.get(
            url, stream=True, timeout=120,
            headers=self.HEADERS, allow_redirects=True
        )
        response.raise_for_status()

        total = int(response.headers.get('content-length', 0))
        downloaded = 0
        pct_range = pct_end - pct_start

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, 'wb') as f:
            for chunk in response.iter_content(chunk_size=131072):  # 128 KB chunks
                if self._stop:
                    return
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = pct_start + int(downloaded * pct_range / total)
                    mb_done = downloaded / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    self.progress_updated.emit(
                        min(pct, pct_end),
                        f"Downloading {name}: {mb_done:.0f} / {mb_total:.0f} MB"
                    )

    def _try_insightface_auto_download(self, buffalo_dir: Path) -> bool:
        """Let insightface download buffalo_l automatically."""
        try:
            self.progress_updated.emit(81, "Trying insightface auto-download...")
            import insightface
            app = insightface.app.FaceAnalysis(
                name='buffalo_l',
                root=str(self.models_dir),
                providers=['CPUExecutionProvider']
            )
            app.prepare(ctx_id=-1, det_size=(320, 320))
            if self._buffalo_ok():
                self.progress_updated.emit(98, "Detection models downloaded ✓")
                return True
        except Exception:
            pass
        return False

    def _download_buffalo_files(self, buffalo_dir: Path,
                                 pct_start: int, pct_end: int) -> bool:
        """Download individual buffalo_l files with mirror fallback."""
        pct_per_file = (pct_end - pct_start) // len(self.BUFFALO_L_FILES)
        any_downloaded = False

        for i, (fname, mirrors) in enumerate(self.BUFFALO_L_FILES):
            if self._stop:
                return False
            dest = buffalo_dir / fname
            min_size = self.BUFFALO_MIN_SIZES.get(fname, 1024)

            if self._file_valid(dest, min_size):
                continue  # Already have it

            # Remove corrupt partial
            if dest.exists():
                dest.unlink()

            file_pct_start = pct_start + i * pct_per_file
            file_pct_end = file_pct_start + pct_per_file

            ok = self._download_with_mirrors(
                mirrors, dest, fname,
                file_pct_start, file_pct_end, min_size
            )
            if ok:
                any_downloaded = True
            # Non-fatal for optional files, but fatal for required ones
            elif fname in ("det_10g.onnx", "w600k_r50.onnx"):
                return False

        return self._buffalo_ok()

    def _download_buffalo_zip(self, buffalo_dir: Path) -> bool:
        """Download buffalo_l.zip and extract it."""
        try:
            self.progress_updated.emit(82, "Downloading buffalo_l.zip (fallback)...")
            zip_dest = self.models_dir / "buffalo_l.zip"
            self._stream_download(
                self.BUFFALO_ZIP_URL, zip_dest, "buffalo_l.zip", 82, 95
            )
            if not zip_dest.exists() or zip_dest.stat().st_size < 1024:
                return False

            self.progress_updated.emit(96, "Extracting buffalo_l.zip...")
            with zipfile.ZipFile(zip_dest, 'r') as zf:
                for member in zf.namelist():
                    if member.endswith('.onnx'):
                        fname = Path(member).name
                        dest = buffalo_dir / fname
                        with zf.open(member) as src, open(dest, 'wb') as dst:
                            dst.write(src.read())

            zip_dest.unlink()  # Clean up zip
            return self._buffalo_ok()
        except Exception:
            return False
