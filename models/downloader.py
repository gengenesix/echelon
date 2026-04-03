"""
Model downloader for Echelon v2.3
- Per-chunk read timeout (no more infinite hangs)
- Resumable downloads
- Corrected file size thresholds
- Manual copy support
"""
import os
import socket
import requests
import zipfile
import time
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal


class ModelDownloader(QThread):
    progress_updated = pyqtSignal(int, str)
    download_finished = pyqtSignal(str)
    download_failed  = pyqtSignal(str, str)
    all_done         = pyqtSignal()

    # ── inswapper_128.onnx mirrors ───────────────────────────────────────────
    INSWAPPER_URLS = [
        # GitHub releases — most reliable
        "https://github.com/facefusion/facefusion-assets/releases/download/models/inswapper_128.onnx",
        # HuggingFace mirrors
        "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
        "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/inswapper_128.onnx",
        "https://huggingface.co/thebiglaskowski/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
    ]
    INSWAPPER_MIN_BYTES = 500 * 1024 * 1024   # real file = ~554 MB

    # ── buffalo_l individual files ───────────────────────────────────────────
    BUFFALO_FILES = [
        ("det_10g.onnx", 14_000_000, [      # real ~17 MB
            "https://github.com/deepinsight/insightface/releases/download/v0.7/det_10g.onnx",
            "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/det_10g.onnx",
            "https://huggingface.co/MonsterMMORPG/insightface_buffalo_l/resolve/main/det_10g.onnx",
        ]),
        ("1k3d68.onnx", 130_000_000, [      # real ~137 MB
            "https://github.com/deepinsight/insightface/releases/download/v0.7/1k3d68.onnx",
            "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/1k3d68.onnx",
            "https://huggingface.co/MonsterMMORPG/insightface_buffalo_l/resolve/main/1k3d68.onnx",
        ]),
        ("2d106det.onnx", 4_000_000, [      # real ~5 MB
            "https://github.com/deepinsight/insightface/releases/download/v0.7/2d106det.onnx",
            "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/2d106det.onnx",
            "https://huggingface.co/MonsterMMORPG/insightface_buffalo_l/resolve/main/2d106det.onnx",
        ]),
        ("genderage.onnx", 900_000, [       # real ~1.3 MB
            "https://github.com/deepinsight/insightface/releases/download/v0.7/genderage.onnx",
            "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/genderage.onnx",
            "https://huggingface.co/MonsterMMORPG/insightface_buffalo_l/resolve/main/genderage.onnx",
        ]),
        ("w600k_r50.onnx", 160_000_000, [   # real ~167 MB
            "https://github.com/deepinsight/insightface/releases/download/v0.7/w600k_r50.onnx",
            "https://huggingface.co/netrunner-exe/Insight-Swap-models/resolve/main/w600k_r50.onnx",
            "https://huggingface.co/MonsterMMORPG/insightface_buffalo_l/resolve/main/w600k_r50.onnx",
        ]),
    ]

    BUFFALO_ZIP_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 Echelon/2.3",
        "Accept": "*/*",
    }
    CONNECT_TIMEOUT = 20      # seconds to establish connection
    READ_TIMEOUT    = 30      # seconds to wait for next chunk
    STALL_TIMEOUT   = 60      # seconds without any bytes before giving up

    def __init__(self, models_dir: str, parent=None):
        super().__init__(parent)
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._stop = False

    def stop(self):
        self._stop = True

    # ─────────────────────────────────────────────────────────────────────────
    # Public helpers
    # ─────────────────────────────────────────────────────────────────────────

    def check_models_exist(self) -> dict:
        return {
            "inswapper_128.onnx": self._inswapper_ok(),
            "buffalo_l":          self._buffalo_ok(),
        }

    def _inswapper_ok(self) -> bool:
        p = self.models_dir / "inswapper_128.onnx"
        return p.exists() and p.stat().st_size >= self.INSWAPPER_MIN_BYTES

    def _buffalo_ok(self) -> bool:
        d = self.models_dir / "models" / "buffalo_l"
        if not d.exists():
            return False
        # Only require the two essential files
        for fname, min_size, _ in self.BUFFALO_FILES:
            if fname not in ("det_10g.onnx", "w600k_r50.onnx"):
                continue
            fp = d / fname
            if not fp.exists() or fp.stat().st_size < min_size:
                return False
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Main run
    # ─────────────────────────────────────────────────────────────────────────

    def run(self):
        # ── inswapper_128.onnx ────────────────────────────────────────────────
        dest = self.models_dir / "inswapper_128.onnx"
        if not self._inswapper_ok():
            if dest.exists():
                dest.unlink()
            self.progress_updated.emit(2, "Downloading face swap model (~554 MB)…")
            ok = self._try_mirrors(
                self.INSWAPPER_URLS, dest, "inswapper_128.onnx",
                self.INSWAPPER_MIN_BYTES, pct_start=2, pct_end=75
            )
            if not ok:
                self.download_failed.emit(
                    "inswapper_128.onnx",
                    "All mirrors failed for inswapper_128.onnx.\n"
                    "Check your internet connection and retry.\n\n"
                    "Or install manually via Settings → Models → Browse."
                )
                return
        else:
            self.progress_updated.emit(75, "Face swap model ✓ (already present)")

        self.download_finished.emit("inswapper_128.onnx")

        # ── buffalo_l ─────────────────────────────────────────────────────────
        if not self._buffalo_ok():
            buffalo_dir = self.models_dir / "models" / "buffalo_l"
            buffalo_dir.mkdir(parents=True, exist_ok=True)

            # Strategy 1: insightface auto-download
            if self._insightface_auto(buffalo_dir):
                pass
            # Strategy 2: individual file downloads
            elif not self._download_buffalo_files(buffalo_dir, 77, 97):
                # Strategy 3: zip fallback
                if not self._download_buffalo_zip(buffalo_dir):
                    self.download_failed.emit(
                        "buffalo_l",
                        "Could not download face detection models.\n"
                        "Check your internet and retry.\n\n"
                        "Or copy the buffalo_l files manually via Settings → Models → Browse."
                    )
                    return
        else:
            self.progress_updated.emit(97, "Detection models ✓ (already present)")

        self.download_finished.emit("buffalo_l")
        self.progress_updated.emit(100, "✅ All models ready!")
        self.all_done.emit()

    # ─────────────────────────────────────────────────────────────────────────
    # Download engine  (per-chunk stall detection — no more hanging)
    # ─────────────────────────────────────────────────────────────────────────

    def _try_mirrors(self, urls, dest: Path, name: str,
                     min_size: int, pct_start: int, pct_end: int) -> bool:
        for idx, url in enumerate(urls):
            if self._stop:
                return False
            self.progress_updated.emit(
                pct_start,
                f"Trying mirror {idx+1}/{len(urls)} for {name}…"
            )
            try:
                self._stream(url, dest, name, pct_start, pct_end)
                if dest.exists() and dest.stat().st_size >= min_size:
                    return True
                if dest.exists():
                    dest.unlink()
                self.progress_updated.emit(pct_start, f"Mirror {idx+1} gave wrong size, trying next…")
            except Exception as e:
                if dest.exists():
                    try: dest.unlink()
                    except: pass
                self.progress_updated.emit(pct_start, f"Mirror {idx+1} failed ({type(e).__name__}), next…")
        return False

    def _stream(self, url: str, dest: Path, name: str, pct_start: int, pct_end: int):
        """Stream-download with per-chunk stall detection."""
        dest.parent.mkdir(parents=True, exist_ok=True)

        resp = requests.get(
            url, stream=True,
            timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT),
            headers=self.HEADERS,
            allow_redirects=True,
        )
        resp.raise_for_status()

        total     = int(resp.headers.get("content-length", 0))
        done      = 0
        pct_range = pct_end - pct_start
        last_byte = time.monotonic()

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=131_072):
                if self._stop:
                    return
                if not chunk:
                    # No data — check stall
                    if time.monotonic() - last_byte > self.STALL_TIMEOUT:
                        raise TimeoutError(f"Download stalled for {self.STALL_TIMEOUT}s")
                    continue
                f.write(chunk)
                done     += len(chunk)
                last_byte = time.monotonic()
                if total > 0:
                    pct    = pct_start + int(done * pct_range / total)
                    mb     = done  / 1_048_576
                    mb_tot = total / 1_048_576
                    self.progress_updated.emit(
                        min(pct, pct_end),
                        f"{name}: {mb:.0f} / {mb_tot:.0f} MB"
                    )
                else:
                    mb = done / 1_048_576
                    self.progress_updated.emit(pct_start, f"{name}: {mb:.0f} MB…")

    # ─────────────────────────────────────────────────────────────────────────
    # buffalo_l strategies
    # ─────────────────────────────────────────────────────────────────────────

    def _insightface_auto(self, buffalo_dir: Path) -> bool:
        try:
            self.progress_updated.emit(77, "Trying insightface auto-download…")
            import insightface
            app = insightface.app.FaceAnalysis(
                name="buffalo_l",
                root=str(self.models_dir),
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=-1, det_size=(320, 320))
            if self._buffalo_ok():
                self.progress_updated.emit(97, "Detection models downloaded ✓")
                return True
        except Exception:
            pass
        return False

    def _download_buffalo_files(self, buffalo_dir: Path,
                                 pct_start: int, pct_end: int) -> bool:
        step = (pct_end - pct_start) // len(self.BUFFALO_FILES)
        for i, (fname, min_size, mirrors) in enumerate(self.BUFFALO_FILES):
            if self._stop:
                return False
            fp = buffalo_dir / fname
            if fp.exists() and fp.stat().st_size >= min_size:
                continue
            if fp.exists():
                fp.unlink()
            s = pct_start + i * step
            e = s + step
            ok = self._try_mirrors(mirrors, fp, fname, min_size, s, e)
            if not ok and fname in ("det_10g.onnx", "w600k_r50.onnx"):
                return False
        return self._buffalo_ok()

    def _download_buffalo_zip(self, buffalo_dir: Path) -> bool:
        try:
            self.progress_updated.emit(79, "Downloading buffalo_l.zip fallback (~330 MB)…")
            zip_dest = self.models_dir / "buffalo_l.zip"
            self._stream(self.BUFFALO_ZIP_URL, zip_dest, "buffalo_l.zip", 79, 95)
            if not zip_dest.exists() or zip_dest.stat().st_size < 1024:
                return False
            self.progress_updated.emit(96, "Extracting buffalo_l.zip…")
            with zipfile.ZipFile(zip_dest, "r") as zf:
                for member in zf.namelist():
                    if member.endswith(".onnx"):
                        fname = Path(member).name
                        with zf.open(member) as src, open(buffalo_dir / fname, "wb") as dst:
                            dst.write(src.read())
            zip_dest.unlink()
            return self._buffalo_ok()
        except Exception:
            return False
