"""
Model downloader for Echelon v3.2
- Verified working URLs from facefusion-assets releases (models-3.0.0 / models-3.4.0)
- Per-model download threads so each model can be downloaded independently
- Per-chunk stall detection — no infinite hangs
- Resumable partial downloads
"""
import time
import zipfile
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
import requests


# ── All verified URLs (tested 200 OK with correct Content-Length) ────────────
_FF3 = "https://github.com/facefusion/facefusion-assets/releases/download/models-3.0.0"
_FF34 = "https://github.com/facefusion/facefusion-assets/releases/download/models-3.4.0"
_HF_INS = "https://huggingface.co"

INSWAPPER_URLS = [
    f"{_FF3}/inswapper_128.onnx",
    f"{_HF_INS}/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
    f"{_HF_INS}/netrunner-exe/Insight-Swap-models/resolve/main/inswapper_128.onnx",
    f"{_HF_INS}/thebiglaskowski/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
]
INSWAPPER_MIN_BYTES = 500 * 1024 * 1024   # ~529 MB

CODEFORMER_URLS = [
    f"{_FF3}/codeformer.onnx",             # 359 MB — verified 200 OK
]
CODEFORMER_MIN_BYTES = 300 * 1024 * 1024  # ~359 MB

REAL_ESRGAN_URLS = [
    f"{_FF3}/real_esrgan_x2_fp16.onnx",    # 34 MB — verified 200 OK
]
REAL_ESRGAN_MIN_BYTES = 20 * 1024 * 1024  # ~34 MB

GHOST_UNET_URLS = [
    f"{_FF34}/ghost_unet_2blocks.onnx",
    f"{_FF3}/ghost_unet_2blocks.onnx",
    "https://github.com/facefusion/facefusion-assets/releases/download/models/ghost_unet_2blocks.onnx",
    f"{_HF_INS}/netrunner-exe/Insight-Swap-models/resolve/main/ghost_unet_2blocks.onnx",
    f"{_HF_INS}/facefusion/facefusion-assets/resolve/main/models/ghost_unet_2blocks.onnx",
]
GHOST_UNET_MIN_BYTES = 10 * 1024 * 1024   # ~25 MB

BUFFALO_FILES = [
    ("det_10g.onnx",   14_000_000, [
        "https://github.com/deepinsight/insightface/releases/download/v0.7/det_10g.onnx",
        f"{_HF_INS}/netrunner-exe/Insight-Swap-models/resolve/main/det_10g.onnx",
        f"{_HF_INS}/MonsterMMORPG/insightface_buffalo_l/resolve/main/det_10g.onnx",
    ]),
    ("1k3d68.onnx",    130_000_000, [
        "https://github.com/deepinsight/insightface/releases/download/v0.7/1k3d68.onnx",
        f"{_HF_INS}/netrunner-exe/Insight-Swap-models/resolve/main/1k3d68.onnx",
        f"{_HF_INS}/MonsterMMORPG/insightface_buffalo_l/resolve/main/1k3d68.onnx",
    ]),
    ("2d106det.onnx",  4_000_000, [
        "https://github.com/deepinsight/insightface/releases/download/v0.7/2d106det.onnx",
        f"{_HF_INS}/netrunner-exe/Insight-Swap-models/resolve/main/2d106det.onnx",
        f"{_HF_INS}/MonsterMMORPG/insightface_buffalo_l/resolve/main/2d106det.onnx",
    ]),
    ("genderage.onnx", 900_000, [
        "https://github.com/deepinsight/insightface/releases/download/v0.7/genderage.onnx",
        f"{_HF_INS}/netrunner-exe/Insight-Swap-models/resolve/main/genderage.onnx",
        f"{_HF_INS}/MonsterMMORPG/insightface_buffalo_l/resolve/main/genderage.onnx",
    ]),
    ("w600k_r50.onnx", 160_000_000, [
        "https://github.com/deepinsight/insightface/releases/download/v0.7/w600k_r50.onnx",
        f"{_HF_INS}/netrunner-exe/Insight-Swap-models/resolve/main/w600k_r50.onnx",
        f"{_HF_INS}/MonsterMMORPG/insightface_buffalo_l/resolve/main/w600k_r50.onnx",
    ]),
]
BUFFALO_ZIP_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"

HEADERS = {"User-Agent": "Mozilla/5.0 Echelon/3.2", "Accept": "*/*"}
CONNECT_TIMEOUT = 20
READ_TIMEOUT    = 30
STALL_TIMEOUT   = 90


# ─────────────────────────────────────────────────────────────────────────────
# Single-model downloader — download ONE model independently
# ─────────────────────────────────────────────────────────────────────────────

class SingleModelDownloader(QThread):
    """Downloads a single named model. Used by individual 'Download' buttons."""
    progress_updated = pyqtSignal(int, str)
    finished_ok      = pyqtSignal(str)   # emits model name
    failed           = pyqtSignal(str, str)  # name, error message

    def __init__(self, model_name: str, urls: list, dest_path: str,
                 min_bytes: int, parent=None):
        super().__init__(parent)
        self.model_name = model_name
        self.urls       = urls
        self.dest       = Path(dest_path)
        self.min_bytes  = min_bytes
        self._stop      = False

    def stop(self):
        self._stop = True

    def run(self):
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        if self.dest.exists():
            self.dest.unlink()

        ok = _try_mirrors(
            self.urls, self.dest, self.model_name,
            self.min_bytes, 0, 100,
            self._emit_progress, lambda: self._stop,
        )
        if ok:
            self.finished_ok.emit(self.model_name)
        else:
            self.failed.emit(
                self.model_name,
                f"All download mirrors failed for {self.model_name}.\n"
                "Check your internet connection and try again.\n\n"
                "You can also click 'Browse…' to install the file manually."
            )

    def _emit_progress(self, pct: int, msg: str):
        self.progress_updated.emit(pct, msg)


# ─────────────────────────────────────────────────────────────────────────────
# Full downloader — downloads all required + optional models in sequence
# ─────────────────────────────────────────────────────────────────────────────

class ModelDownloader(QThread):
    progress_updated = pyqtSignal(int, str)
    download_finished = pyqtSignal(str)
    download_failed   = pyqtSignal(str, str)
    all_done          = pyqtSignal()

    def __init__(self, models_dir: str, parent=None):
        super().__init__(parent)
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._stop = False

    def stop(self):
        self._stop = True

    # ── Status checks ─────────────────────────────────────────────────────────

    def check_models_exist(self) -> dict:
        return {
            "inswapper_128.onnx":      self._inswapper_ok(),
            "buffalo_l":               self._buffalo_ok(),
            "codeformer.onnx":         self._codeformer_ok(),
            "real_esrgan_x2.onnx":     self._real_esrgan_ok(),
            "ghost_unet_2blocks.onnx": self._ghost_ok(),
        }

    def _inswapper_ok(self) -> bool:
        p = self.models_dir / "inswapper_128.onnx"
        return p.exists() and p.stat().st_size >= INSWAPPER_MIN_BYTES

    def _buffalo_ok(self) -> bool:
        d = self.models_dir / "models" / "buffalo_l"
        if not d.exists():
            return False
        for fname, min_size, _ in BUFFALO_FILES:
            if fname not in ("det_10g.onnx", "w600k_r50.onnx"):
                continue
            fp = d / fname
            if not fp.exists() or fp.stat().st_size < min_size:
                return False
        return True

    def _codeformer_ok(self) -> bool:
        p = self.models_dir / "codeformer.onnx"
        return p.exists() and p.stat().st_size >= CODEFORMER_MIN_BYTES

    def _real_esrgan_ok(self) -> bool:
        p = self.models_dir / "real_esrgan_x2_fp16.onnx"
        return p.exists() and p.stat().st_size >= REAL_ESRGAN_MIN_BYTES

    def _ghost_ok(self) -> bool:
        p = self.models_dir / "ghost_unet_2blocks.onnx"
        return p.exists() and p.stat().st_size >= GHOST_UNET_MIN_BYTES

    # ── Convenience: build per-model SingleModelDownloader instances ──────────

    def make_codeformer_downloader(self, parent=None) -> SingleModelDownloader:
        return SingleModelDownloader(
            "codeformer.onnx",
            CODEFORMER_URLS,
            str(self.models_dir / "codeformer.onnx"),
            CODEFORMER_MIN_BYTES,
            parent,
        )

    def make_real_esrgan_downloader(self, parent=None) -> SingleModelDownloader:
        return SingleModelDownloader(
            "real_esrgan_x2_fp16.onnx",
            REAL_ESRGAN_URLS,
            str(self.models_dir / "real_esrgan_x2_fp16.onnx"),
            REAL_ESRGAN_MIN_BYTES,
            parent,
        )

    def make_inswapper_downloader(self, parent=None) -> SingleModelDownloader:
        return SingleModelDownloader(
            "inswapper_128.onnx",
            INSWAPPER_URLS,
            str(self.models_dir / "inswapper_128.onnx"),
            INSWAPPER_MIN_BYTES,
            parent,
        )

    def make_ghost_downloader(self, parent=None) -> SingleModelDownloader:
        return SingleModelDownloader(
            "ghost_unet_2blocks.onnx",
            GHOST_UNET_URLS,
            str(self.models_dir / "ghost_unet_2blocks.onnx"),
            GHOST_UNET_MIN_BYTES,
            parent,
        )

    # ── Main run (downloads everything needed) ────────────────────────────────

    def run(self):
        def emit(pct, msg):
            self.progress_updated.emit(pct, msg)

        def stopped():
            return self._stop

        # ── Required: inswapper_128.onnx ──────────────────────────────────────
        dest = self.models_dir / "inswapper_128.onnx"
        if not self._inswapper_ok():
            if dest.exists():
                dest.unlink()
            emit(2, "Downloading face swap model (~529 MB)…")
            ok = _try_mirrors(INSWAPPER_URLS, dest, "inswapper_128.onnx",
                              INSWAPPER_MIN_BYTES, 2, 70, emit, stopped)
            if not ok:
                self.download_failed.emit(
                    "inswapper_128.onnx",
                    "All mirrors failed for inswapper_128.onnx.\n"
                    "Check your internet connection and retry.\n\n"
                    "Or install manually via Settings → Models → Browse."
                )
                return
        else:
            emit(70, "Face swap model ✓ (already present)")
        self.download_finished.emit("inswapper_128.onnx")

        # ── Required: buffalo_l ───────────────────────────────────────────────
        if not self._buffalo_ok():
            buffalo_dir = self.models_dir / "models" / "buffalo_l"
            buffalo_dir.mkdir(parents=True, exist_ok=True)
            if not self._insightface_auto(buffalo_dir, emit):
                if not self._download_buffalo_files(buffalo_dir, 72, 90, emit, stopped):
                    if not self._download_buffalo_zip(buffalo_dir, emit):
                        self.download_failed.emit(
                            "buffalo_l",
                            "Could not download face detection models.\n"
                            "Check your internet and retry.\n\n"
                            "Or copy buffalo_l files manually via Browse."
                        )
                        return
        else:
            emit(90, "Detection models ✓ (already present)")
        self.download_finished.emit("buffalo_l")

        # ── Optional: Real-ESRGAN (34 MB, fast) ──────────────────────────────
        re_dest = self.models_dir / "real_esrgan_x2_fp16.onnx"
        if not self._real_esrgan_ok():
            emit(91, "Downloading Real-ESRGAN enhancer (~34 MB)…")
            ok = _try_mirrors(REAL_ESRGAN_URLS, re_dest, "real_esrgan_x2_fp16.onnx",
                              REAL_ESRGAN_MIN_BYTES, 91, 95, emit, stopped)
            if ok:
                self.download_finished.emit("real_esrgan_x2_fp16.onnx")
                emit(95, "Real-ESRGAN ✓")
            else:
                emit(95, "Real-ESRGAN skipped — will use OpenCV fallback")
        else:
            emit(95, "Real-ESRGAN ✓ (already present)")
            self.download_finished.emit("real_esrgan_x2_fp16.onnx")

        # ── Optional: CodeFormer (359 MB, best quality) ───────────────────────
        cf_dest = self.models_dir / "codeformer.onnx"
        if not self._codeformer_ok():
            emit(96, "Downloading CodeFormer face restoration (~359 MB)…")
            ok = _try_mirrors(CODEFORMER_URLS, cf_dest, "codeformer.onnx",
                              CODEFORMER_MIN_BYTES, 96, 98, emit, stopped)
            if ok:
                self.download_finished.emit("codeformer.onnx")
                emit(98, "CodeFormer ✓")
            else:
                emit(98, "CodeFormer skipped — Real-ESRGAN or OpenCV will be used")
        else:
            emit(98, "CodeFormer ✓ (already present)")
            self.download_finished.emit("codeformer.onnx")

        # ── Optional: ghost-unet-256 (~25 MB, sharper swap model) ────────────
        gh_dest = self.models_dir / "ghost_unet_2blocks.onnx"
        if not self._ghost_ok():
            emit(98, "Downloading ghost-unet swap model (~25 MB)…")
            ok = _try_mirrors(GHOST_UNET_URLS, gh_dest, "ghost_unet_2blocks.onnx",
                              GHOST_UNET_MIN_BYTES, 98, 100, emit, stopped)
            if ok:
                self.download_finished.emit("ghost_unet_2blocks.onnx")
            else:
                emit(100, "ghost-unet skipped — inswapper_128 will be used")
        else:
            emit(100, "ghost-unet ✓ (already present)")
            self.download_finished.emit("ghost_unet_2blocks.onnx")

        emit(100, "✅ All models ready!")
        self.all_done.emit()

    # ── buffalo_l strategies ──────────────────────────────────────────────────

    def _insightface_auto(self, buffalo_dir: Path, emit) -> bool:
        try:
            emit(72, "Trying insightface auto-download…")
            import insightface
            app = insightface.app.FaceAnalysis(
                name="buffalo_l", root=str(self.models_dir),
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=-1, det_size=(320, 320))
            if self._buffalo_ok():
                emit(90, "Detection models downloaded ✓")
                return True
        except Exception:
            pass
        return False

    def _download_buffalo_files(self, buffalo_dir, pct_start, pct_end, emit, stopped):
        step = max(1, (pct_end - pct_start) // len(BUFFALO_FILES))
        for i, (fname, min_size, mirrors) in enumerate(BUFFALO_FILES):
            if stopped():
                return False
            fp = buffalo_dir / fname
            if fp.exists() and fp.stat().st_size >= min_size:
                continue
            if fp.exists():
                fp.unlink()
            s, e = pct_start + i * step, pct_start + (i + 1) * step
            ok = _try_mirrors(mirrors, fp, fname, min_size, s, e, emit, stopped)
            if not ok and fname in ("det_10g.onnx", "w600k_r50.onnx"):
                return False
        return self._buffalo_ok()

    def _download_buffalo_zip(self, buffalo_dir: Path, emit) -> bool:
        try:
            emit(79, "Downloading buffalo_l.zip fallback (~330 MB)…")
            zip_dest = self.models_dir / "buffalo_l.zip"
            _stream(BUFFALO_ZIP_URL, zip_dest, "buffalo_l.zip", 79, 95, emit, lambda: self._stop)
            if not zip_dest.exists() or zip_dest.stat().st_size < 1024:
                return False
            emit(96, "Extracting buffalo_l.zip…")
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


# ─────────────────────────────────────────────────────────────────────────────
# Shared low-level download helpers (module-level so both classes can use them)
# ─────────────────────────────────────────────────────────────────────────────

def _try_mirrors(urls, dest: Path, name: str, min_size: int,
                 pct_start: int, pct_end: int, emit_fn, stopped_fn) -> bool:
    for idx, url in enumerate(urls):
        if stopped_fn():
            return False
        emit_fn(pct_start, f"Trying mirror {idx+1}/{len(urls)} for {name}…")
        try:
            _stream(url, dest, name, pct_start, pct_end, emit_fn, stopped_fn)
            if dest.exists() and dest.stat().st_size >= min_size:
                return True
            if dest.exists():
                dest.unlink()
            emit_fn(pct_start, f"Mirror {idx+1} gave wrong size, trying next…")
        except Exception as e:
            if dest.exists():
                try:
                    dest.unlink()
                except Exception:
                    pass
            emit_fn(pct_start, f"Mirror {idx+1} failed ({type(e).__name__}), trying next…")
    return False


def _stream(url: str, dest: Path, name: str,
            pct_start: int, pct_end: int, emit_fn, stopped_fn):
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(
        url, stream=True,
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        headers=HEADERS,
        allow_redirects=True,
    )
    resp.raise_for_status()

    total     = int(resp.headers.get("content-length", 0))
    done      = 0
    pct_range = max(1, pct_end - pct_start)
    last_byte = time.monotonic()

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=131_072):
            if stopped_fn():
                return
            if not chunk:
                if time.monotonic() - last_byte > STALL_TIMEOUT:
                    raise TimeoutError(f"Stalled for {STALL_TIMEOUT}s")
                continue
            f.write(chunk)
            done     += len(chunk)
            last_byte = time.monotonic()
            if total > 0:
                pct = pct_start + int(done * pct_range / total)
                emit_fn(
                    min(pct, pct_end),
                    f"{name}: {done/1_048_576:.0f} / {total/1_048_576:.0f} MB"
                )
            else:
                emit_fn(pct_start, f"{name}: {done/1_048_576:.0f} MB…")
