import sys
import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QCheckBox, QComboBox, QLineEdit,
                              QGroupBox, QFormLayout, QSlider, QMessageBox,
                              QScrollArea, QWidget, QSizePolicy, QFrame,
                              QProgressBar, QFileDialog)
from PyQt6.QtCore import Qt
from config.manager import AppConfig, BASE_DIR

IS_LINUX   = sys.platform.startswith("linux")
IS_WINDOWS = sys.platform == "win32"
IS_MAC     = sys.platform == "darwin"


def _grp_style():
    return (
        "QGroupBox { color: #8888A0; font-weight: 600; border: 1px solid #2A2A35; "
        "border-radius: 8px; margin-top: 8px; padding-top: 8px; } "
        "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
    )


def _make_slider_row(mn, mx, default):
    row = QHBoxLayout()
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(mn, mx)
    slider.setValue(default)
    slider.setFixedWidth(120)
    val_lbl = QLabel(str(default))
    slider.valueChanged.connect(lambda v: val_lbl.setText(str(v)))
    row.addWidget(slider)
    row.addWidget(val_lbl)
    row.addStretch()
    return row, slider, val_lbl


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._downloader = None
        self.setWindowTitle("Settings")
        self.setMinimumSize(520, 640)
        self.resize(520, 800)
        self._setup_ui()
        self.load_from_config(config)

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        scroll_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(scroll_widget)
        layout.setContentsMargins(24, 24, 24, 12)
        layout.setSpacing(16)
        scroll.setWidget(scroll_widget)
        outer.addWidget(scroll, 1)

        # ── General ──────────────────────────────────────────────────────────
        gen = QGroupBox("General")
        gen.setStyleSheet(_grp_style())
        gen_layout = QFormLayout(gen)
        gen_layout.setSpacing(10)
        self._login_cb    = QCheckBox()
        self._minimized_cb = QCheckBox()
        self._perf_combo  = QComboBox()
        self._perf_combo.addItems(["quality", "balanced", "speed"])
        gen_layout.addRow("Launch on login:", self._login_cb)
        gen_layout.addRow("Start minimized:", self._minimized_cb)
        gen_layout.addRow("Default mode:",    self._perf_combo)
        layout.addWidget(gen)

        # ── Camera ───────────────────────────────────────────────────────────
        cam = QGroupBox("Camera")
        cam.setStyleSheet(_grp_style())
        cam_layout = QFormLayout(cam)
        cam_layout.setSpacing(10)
        self._res_combo = QComboBox()
        self._res_combo.addItems(["1280x720", "1920x1080", "640x480"])
        self._fps_combo = QComboBox()
        self._fps_combo.addItems(["30", "25", "20", "15"])
        cam_layout.addRow("Output resolution:", self._res_combo)
        cam_layout.addRow("Output FPS:",        self._fps_combo)
        layout.addWidget(cam)

        # ── Performance ──────────────────────────────────────────────────────
        perf = QGroupBox("Performance")
        perf.setStyleSheet(_grp_style())
        perf_layout = QFormLayout(perf)
        perf_layout.setSpacing(10)
        self._auto_tune_cb = QCheckBox()
        skip_row, self._skip_slider, self._skip_lbl = _make_slider_row(0, 4, 1)
        det_row,  self._det_slider,  self._det_lbl  = _make_slider_row(1, 10, 5)
        perf_layout.addRow("Auto-tune performance:", self._auto_tune_cb)
        perf_layout.addRow("Frame skip:",            skip_row)
        perf_layout.addRow("Face detect interval:",  det_row)
        layout.addWidget(perf)

        # ── AI Models ────────────────────────────────────────────────────────
        mdl = QGroupBox("AI Models")
        mdl.setStyleSheet(_grp_style())
        mdl_layout = QVBoxLayout(mdl)
        mdl_layout.setSpacing(10)

        # Status row
        self._model_status_lbl = QLabel("Checking models…")
        self._model_status_lbl.setStyleSheet("color: #8888A0; font-size: 12px;")
        self._model_status_lbl.setWordWrap(True)
        mdl_layout.addWidget(self._model_status_lbl)

        # Progress bar (hidden unless downloading)
        self._dl_progress = QProgressBar()
        self._dl_progress.setFixedHeight(6)
        self._dl_progress.setVisible(False)
        mdl_layout.addWidget(self._dl_progress)

        self._dl_msg_lbl = QLabel("")
        self._dl_msg_lbl.setStyleSheet("color: #6B7094; font-size: 11px;")
        self._dl_msg_lbl.setWordWrap(True)
        self._dl_msg_lbl.setVisible(False)
        mdl_layout.addWidget(self._dl_msg_lbl)

        # Buttons row
        btn_row = QHBoxLayout()
        self._dl_btn = QPushButton("Download Models")
        self._dl_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self._dl_btn)

        self._stop_dl_btn = QPushButton("Stop")
        self._stop_dl_btn.setVisible(False)
        self._stop_dl_btn.clicked.connect(self._stop_download)
        btn_row.addWidget(self._stop_dl_btn)

        btn_row.addStretch()
        mdl_layout.addLayout(btn_row)

        # ── Manual install section ────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2A2A35;")
        mdl_layout.addWidget(sep)

        manual_title = QLabel("Manual Install")
        manual_title.setStyleSheet("color: #E8E9F0; font-weight: 600; font-size: 12px;")
        mdl_layout.addWidget(manual_title)

        manual_desc = QLabel(
            "If automatic download fails, you can place the model files manually.\n"
            "Click a button below to browse for the file on your computer."
        )
        manual_desc.setStyleSheet("color: #6B7094; font-size: 11px;")
        manual_desc.setWordWrap(True)
        mdl_layout.addWidget(manual_desc)

        # inswapper browse
        inswapper_row = QHBoxLayout()
        inswapper_lbl = QLabel("inswapper_128.onnx  (~554 MB):")
        inswapper_lbl.setStyleSheet("color: #C0C0D0; font-size: 11px;")
        self._inswapper_status = QLabel("❓")
        self._inswapper_status.setFixedWidth(20)
        browse_inswapper = QPushButton("Browse…")
        browse_inswapper.setFixedWidth(90)
        browse_inswapper.clicked.connect(self._browse_inswapper)
        inswapper_row.addWidget(self._inswapper_status)
        inswapper_row.addWidget(inswapper_lbl, 1)
        inswapper_row.addWidget(browse_inswapper)
        mdl_layout.addLayout(inswapper_row)

        # buffalo_l browse
        buffalo_row = QHBoxLayout()
        buffalo_lbl = QLabel("buffalo_l folder  (5 .onnx files, ~330 MB):")
        buffalo_lbl.setStyleSheet("color: #C0C0D0; font-size: 11px;")
        self._buffalo_status = QLabel("❓")
        self._buffalo_status.setFixedWidth(20)
        browse_buffalo = QPushButton("Browse…")
        browse_buffalo.setFixedWidth(90)
        browse_buffalo.clicked.connect(self._browse_buffalo_folder)
        buffalo_row.addWidget(self._buffalo_status)
        buffalo_row.addWidget(buffalo_lbl, 1)
        buffalo_row.addWidget(browse_buffalo)
        mdl_layout.addLayout(buffalo_row)

        # Models folder label
        self._models_dir_lbl = QLabel("")
        self._models_dir_lbl.setStyleSheet("color: #50516A; font-size: 10px;")
        self._models_dir_lbl.setWordWrap(True)
        mdl_layout.addWidget(self._models_dir_lbl)

        layout.addWidget(mdl)

        # ── Virtual Camera ───────────────────────────────────────────────────
        if IS_LINUX:
            vcam = QGroupBox("Virtual Camera (Linux)")
            vcam.setStyleSheet(_grp_style())
            vcam_layout = QVBoxLayout(vcam)
            self._vcam_status_lbl = QLabel("Checking…")
            self._vcam_status_lbl.setStyleSheet("color: #8888A0; font-size: 12px;")
            vcam_layout.addWidget(self._vcam_status_lbl)
            vcam_btn = QPushButton("Load v4l2loopback")
            vcam_btn.clicked.connect(self._load_v4l2)
            vcam_layout.addWidget(vcam_btn)
            layout.addWidget(vcam)

        layout.addStretch()

        # ── Save / Close ──────────────────────────────────────────────────────
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(24, 12, 24, 16)
        save_btn = QPushButton("Save & Close")
        save_btn.setObjectName("primaryBtn")
        save_btn.setFixedHeight(40)
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(40)
        cancel_btn.clicked.connect(self.reject)
        btn_bar.addStretch()
        btn_bar.addWidget(cancel_btn)
        btn_bar.addWidget(save_btn)
        outer.addLayout(btn_bar)

        self._refresh_model_status()

    # ── Model status helpers ──────────────────────────────────────────────────

    def _refresh_model_status(self):
        from models.downloader import ModelDownloader
        dl = ModelDownloader(self.config.models_dir)
        inswapper_ok = dl._inswapper_ok()
        buffalo_ok   = dl._buffalo_ok()

        if inswapper_ok and buffalo_ok:
            self._model_status_lbl.setText("✅ All models present and valid.")
            self._model_status_lbl.setStyleSheet("color: #22D98F; font-size: 12px;")
            self._dl_btn.setText("Re-download Models")
        else:
            missing = []
            if not inswapper_ok:
                missing.append("inswapper_128.onnx")
            if not buffalo_ok:
                missing.append("buffalo_l detection files")
            self._model_status_lbl.setText(
                f"⚠️  Missing: {', '.join(missing)}\n"
                "Click 'Download Models' or install manually below."
            )
            self._model_status_lbl.setStyleSheet("color: #FFB547; font-size: 12px;")
            self._dl_btn.setText("Download Models")

        self._inswapper_status.setText("✅" if inswapper_ok else "❌")
        self._buffalo_status.setText("✅"   if buffalo_ok   else "❌")
        self._models_dir_lbl.setText(f"Models folder: {self.config.models_dir}")

    # ── Auto download ─────────────────────────────────────────────────────────

    def _start_download(self):
        from models.downloader import ModelDownloader
        self._dl_btn.setEnabled(False)
        self._stop_dl_btn.setVisible(True)
        self._dl_progress.setValue(0)
        self._dl_progress.setVisible(True)
        self._dl_msg_lbl.setVisible(True)
        self._dl_msg_lbl.setText("Starting download…")

        self._downloader = ModelDownloader(self.config.models_dir)
        self._downloader.progress_updated.connect(self._on_dl_progress)
        self._downloader.all_done.connect(self._on_dl_done)
        self._downloader.download_failed.connect(self._on_dl_failed)
        self._downloader.start()

    def _stop_download(self):
        if self._downloader:
            self._downloader.stop()
        self._stop_dl_btn.setVisible(False)
        self._dl_btn.setEnabled(True)
        self._dl_progress.setVisible(False)
        self._dl_msg_lbl.setText("Download stopped.")

    def _on_dl_progress(self, pct: int, msg: str):
        self._dl_progress.setValue(pct)
        self._dl_msg_lbl.setText(msg)

    def _on_dl_done(self):
        self._stop_dl_btn.setVisible(False)
        self._dl_progress.setVisible(False)
        self._dl_msg_lbl.setVisible(False)
        self._dl_btn.setEnabled(True)
        self._refresh_model_status()
        QMessageBox.information(self, "Download Complete",
                                "✅ All models downloaded and ready!")

    def _on_dl_failed(self, name: str, error: str):
        self._stop_dl_btn.setVisible(False)
        self._dl_progress.setVisible(False)
        self._dl_btn.setEnabled(True)
        self._dl_msg_lbl.setText(f"❌ {error.splitlines()[0]}")
        self._refresh_model_status()
        QMessageBox.warning(self, "Download Failed",
                            f"{error}\n\nYou can also install models manually using the Browse buttons below.")

    # ── Manual browse ─────────────────────────────────────────────────────────

    def _browse_inswapper(self):
        """Let user pick inswapper_128.onnx from their computer and copy it in."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select inswapper_128.onnx", "",
            "ONNX Model (*.onnx)"
        )
        if not path:
            return
        src = Path(path)
        if src.stat().st_size < 100 * 1024 * 1024:
            QMessageBox.warning(self, "File Too Small",
                "This file seems too small to be inswapper_128.onnx.\n"
                "The real file is ~554 MB. Please check you selected the right file.")
            return
        dest = Path(self.config.models_dir) / "inswapper_128.onnx"
        try:
            import shutil
            self._model_status_lbl.setText("Copying inswapper_128.onnx…")
            shutil.copy2(str(src), str(dest))
            self._refresh_model_status()
            QMessageBox.information(self, "Done", "✅ inswapper_128.onnx installed!")
        except Exception as e:
            QMessageBox.critical(self, "Copy Failed", str(e))

    def _browse_buffalo_folder(self):
        """Let user pick the buffalo_l folder containing the 5 .onnx files."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select the buffalo_l folder (containing .onnx files)"
        )
        if not folder:
            return
        src_dir = Path(folder)
        onnx_files = list(src_dir.glob("*.onnx"))
        if len(onnx_files) < 2:
            QMessageBox.warning(self, "Wrong Folder",
                "This folder doesn't look right — expected at least 5 .onnx files.\n"
                "Select the folder named 'buffalo_l' that contains det_10g.onnx, w600k_r50.onnx, etc.")
            return
        dest_dir = Path(self.config.models_dir) / "models" / "buffalo_l"
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            import shutil
            copied = 0
            for f in onnx_files:
                shutil.copy2(str(f), str(dest_dir / f.name))
                copied += 1
            self._refresh_model_status()
            QMessageBox.information(self, "Done",
                f"✅ Copied {copied} model files to buffalo_l folder!")
        except Exception as e:
            QMessageBox.critical(self, "Copy Failed", str(e))

    # ── Virtual camera (Linux) ────────────────────────────────────────────────

    def _load_v4l2(self):
        ok = os.path.exists('/dev/video10')
        if ok:
            self._vcam_status_lbl.setText("✅ Virtual camera already active (/dev/video10)")
            return
        try:
            subprocess.run(
                ['sudo', 'modprobe', 'v4l2loopback',
                 'devices=1', 'video_nr=10',
                 'card_label=Echelon Camera', 'exclusive_caps=1'],
                check=True, timeout=15
            )
            self._vcam_status_lbl.setText("✅ Virtual camera loaded!")
        except Exception as e:
            self._vcam_status_lbl.setText(f"❌ Failed: {e}\nRun manually: sudo modprobe v4l2loopback")

    # ── Load / Save ───────────────────────────────────────────────────────────

    def load_from_config(self, config: AppConfig):
        self._login_cb.setChecked(config.launch_on_login)
        self._minimized_cb.setChecked(config.start_minimized)
        idx = self._perf_combo.findText(config.performance_mode)
        if idx >= 0:
            self._perf_combo.setCurrentIndex(idx)
        res = f"{config.output_width}x{config.output_height}"
        res_idx = self._res_combo.findText(res)
        if res_idx >= 0:
            self._res_combo.setCurrentIndex(res_idx)
        fps_idx = self._fps_combo.findText(str(config.output_fps))
        if fps_idx >= 0:
            self._fps_combo.setCurrentIndex(fps_idx)
        self._auto_tune_cb.setChecked(config.auto_tune)
        self._skip_slider.setValue(config.frame_skip)
        self._det_slider.setValue(config.face_detect_interval)
        if IS_LINUX and hasattr(self, '_vcam_status_lbl'):
            ok = os.path.exists('/dev/video10')
            self._vcam_status_lbl.setText(
                "✅ Virtual camera active (/dev/video10)" if ok
                else "❌ Virtual camera not loaded — click button to load"
            )

    def _save_and_close(self):
        self.config.launch_on_login   = self._login_cb.isChecked()
        self.config.start_minimized   = self._minimized_cb.isChecked()
        self.config.performance_mode  = self._perf_combo.currentText()
        res = self._res_combo.currentText().split("x")
        if len(res) == 2:
            self.config.output_width  = int(res[0])
            self.config.output_height = int(res[1])
        self.config.output_fps            = int(self._fps_combo.currentText())
        self.config.auto_tune             = self._auto_tune_cb.isChecked()
        self.config.frame_skip            = self._skip_slider.value()
        self.config.face_detect_interval  = self._det_slider.value()
        from config.manager import ConfigManager
        ConfigManager().save(self.config)
        self.accept()
