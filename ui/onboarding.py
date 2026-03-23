import os
import subprocess
import cv2
from pathlib import Path
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QProgressBar, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from config.manager import AppConfig
from models.downloader import ModelDownloader

class OnboardingDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Welcome to Echelon")
        self.setFixedSize(520, 500)
        self.setModal(True)
        self._downloader = None
        self._setup_ui()
        self.run_all_checks()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Welcome to Echelon")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Let's verify your setup before we begin.")
        subtitle.setStyleSheet("color: #8888A0; font-size: 13px;")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Row 1: Virtual camera
        self._vcam_row = self._make_check_row(
            "Virtual Camera Driver",
            "Check for /dev/video10"
        )
        layout.addWidget(self._vcam_row["widget"])

        # Row 2: Model
        self._model_row = self._make_check_row(
            "Face Swap Model",
            "inswapper_128.onnx (554 MB)"
        )
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setFixedHeight(6)
        layout.addWidget(self._model_row["widget"])
        layout.addWidget(self._progress)

        # Row 3: Webcam
        self._cam_row = self._make_check_row(
            "Webcam",
            "Check for connected camera"
        )
        layout.addWidget(self._cam_row["widget"])

        layout.addStretch()

        self._continue_btn = QPushButton("Continue")
        self._continue_btn.setObjectName("primaryBtn")
        self._continue_btn.setEnabled(False)
        self._continue_btn.clicked.connect(self._on_continue)
        layout.addWidget(self._continue_btn)

    def _make_check_row(self, title: str, desc: str) -> dict:
        widget = QWidget()
        widget.setStyleSheet("background-color: #141418; border: 1px solid #2A2A35; border-radius: 8px;")
        row = QHBoxLayout(widget)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        icon = QLabel("○")
        icon.setFixedWidth(20)
        icon.setStyleSheet("font-size: 14px; color: #44445A;")

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_lbl = QLabel(title)
        name_lbl.setStyleSheet("font-weight: 600; color: #EAEAF0;")
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("color: #8888A0; font-size: 12px;")
        text_col.addWidget(name_lbl)
        text_col.addWidget(desc_lbl)

        btn = QPushButton("Check")
        btn.setFixedWidth(120)

        row.addWidget(icon)
        row.addLayout(text_col)
        row.addStretch()
        row.addWidget(btn)

        return {"widget": widget, "icon": icon, "desc": desc_lbl, "btn": btn}

    def run_all_checks(self):
        self._check_vcam()
        self._check_model()
        self._check_camera()

    def _check_vcam(self):
        ok = os.path.exists('/dev/video10')
        row = self._vcam_row
        if ok:
            row["icon"].setText("✅")
            row["icon"].setStyleSheet("font-size: 14px;")
            row["desc"].setText("Echelon Camera device ready")
            row["btn"].setText("OK")
            row["btn"].setEnabled(False)
        else:
            row["icon"].setText("❌")
            row["icon"].setStyleSheet("font-size: 14px;")
            row["desc"].setText("Virtual camera not found")
            row["btn"].setText("Fix Now")
            row["btn"].clicked.disconnect() if row["btn"].receivers(row["btn"].clicked) > 0 else None
            row["btn"].clicked.connect(self._fix_vcam)
        self._update_continue()

    def _fix_vcam(self):
        try:
            subprocess.run(
                ['sudo', 'modprobe', 'v4l2loopback', 'devices=1',
                 'video_nr=10', 'card_label=Echelon Camera', 'exclusive_caps=1'],
                check=True, timeout=10
            )
        except Exception as e:
            self._vcam_row["desc"].setText(f"Error: {e}")
        self._check_vcam()

    def _check_model(self):
        path = Path(self.config.models_dir) / "inswapper_128.onnx"
        row = self._model_row
        if path.exists():
            row["icon"].setText("✅")
            row["icon"].setStyleSheet("font-size: 14px;")
            row["desc"].setText("inswapper_128.onnx ready")
            row["btn"].setText("OK")
            row["btn"].setEnabled(False)
        else:
            row["icon"].setText("❌")
            row["icon"].setStyleSheet("font-size: 14px;")
            row["desc"].setText("Model not downloaded")
            row["btn"].setText("Download (554MB)")
            try:
                row["btn"].clicked.disconnect()
            except Exception:
                pass
            row["btn"].clicked.connect(self._download_model)
        self._update_continue()

    def _download_model(self):
        self._model_row["btn"].setEnabled(False)
        self._model_row["btn"].setText("Downloading...")
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._downloader = ModelDownloader(self.config.models_dir)
        self._downloader.progress_updated.connect(self._on_dl_progress)
        self._downloader.all_done.connect(self._on_dl_done)
        self._downloader.download_failed.connect(self._on_dl_failed)
        self._downloader.start()

    def _on_dl_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._model_row["desc"].setText(msg)

    def _on_dl_done(self):
        self._progress.setVisible(False)
        self._check_model()

    def _on_dl_failed(self, name: str, error: str):
        self._progress.setVisible(False)
        self._model_row["desc"].setText(f"Download failed: {error}")
        self._model_row["btn"].setEnabled(True)
        self._model_row["btn"].setText("Retry")

    def _check_camera(self):
        row = self._cam_row
        cap = cv2.VideoCapture(0)
        ok = cap.isOpened()
        cap.release()
        if ok:
            row["icon"].setText("✅")
            row["icon"].setStyleSheet("font-size: 14px;")
            row["desc"].setText("Camera detected")
            row["btn"].setText("OK")
            row["btn"].setEnabled(False)
        else:
            row["icon"].setText("❌")
            row["icon"].setStyleSheet("font-size: 14px;")
            row["desc"].setText("No camera found — connect a webcam")
            row["btn"].setText("Retry")
            try:
                row["btn"].clicked.disconnect()
            except Exception:
                pass
            row["btn"].clicked.connect(self._check_camera)
        self._update_continue()

    def _update_continue(self):
        vcam_ok = os.path.exists('/dev/video10')
        model_ok = (Path(self.config.models_dir) / "inswapper_128.onnx").exists()
        cap = cv2.VideoCapture(0)
        cam_ok = cap.isOpened()
        cap.release()
        self._continue_btn.setEnabled(vcam_ok and model_ok and cam_ok)

    def _on_continue(self):
        self.config.first_launch = False
        from config.manager import ConfigManager
        ConfigManager().save(self.config)
        self.accept()
