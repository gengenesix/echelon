from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QComboBox)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from ui.widgets import SectionLabel, Divider

_START_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #5C5FFF, stop:1 #7B7EFF);
        color: white;
        border: none;
        border-radius: 12px;
        font-size: 16px;
        font-weight: 800;
        letter-spacing: 1px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #7B7EFF, stop:1 #9C9FFF);
    }
    QPushButton:pressed { background: #4345CC; }
    QPushButton:disabled { background: #1A1B24; color: #50516A; }
"""

_STOP_STYLE = """
    QPushButton {
        background: #1A1B24;
        color: #FF5CA8;
        border: 1px solid #FF5CA8;
        border-radius: 12px;
        font-size: 16px;
        font-weight: 800;
        letter-spacing: 1px;
    }
    QPushButton:hover { background: #FF2D6B; color: white; border-color: #FF2D6B; }
    QPushButton:pressed { background: #CC1050; border-color: #CC1050; }
"""

_LOADING_STYLE = """
    QPushButton {
        background: #1A1B30;
        color: #8B8CA8;
        border: 1px solid #252632;
        border-radius: 12px;
        font-size: 15px;
        font-weight: 700;
    }
"""


class StartStopButton(QPushButton):
    _spinner_chars = ["◐", "◓", "◑", "◒"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(52)
        self._state = "idle"
        self._spinner_idx = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._spin)
        self.set_state("idle")

    def set_state(self, state: str):
        self._state = state
        if state == "loading":
            self.setEnabled(False)
            self.setStyleSheet(_LOADING_STYLE)
            self._timer.start(150)
        else:
            self._timer.stop()
            if state == "live":
                self.setText("⏹  STOP")
                self.setStyleSheet(_STOP_STYLE)
            else:
                self.setText("▶  START")
                self.setStyleSheet(_START_STYLE)
            self.setEnabled(True)

    def _spin(self):
        self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_chars)
        self.setText(f"  {self._spinner_chars[self._spinner_idx]} Initializing...")


class ControlsPanel(QWidget):
    mode_changed = pyqtSignal(str)
    camera_changed = pyqtSignal(int)
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    target_face_changed = pyqtSignal(str)
    bg_blur_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "balanced"
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(SectionLabel("PERFORMANCE"))

        mode_row = QHBoxLayout()
        mode_row.setSpacing(4)
        self._mode_btns = {}
        for mode in ("quality", "balanced", "speed"):
            btn = QPushButton(mode.capitalize())
            btn.setObjectName("modeBtn")
            btn.setProperty("selected", mode == "balanced")
            btn.clicked.connect(lambda checked, m=mode: self._on_mode(m))
            self._mode_btns[mode] = btn
            mode_row.addWidget(btn)
        layout.addLayout(mode_row)

        layout.addWidget(Divider())

        layout.addWidget(SectionLabel("CAMERA"))

        self._cam_combo = QComboBox()
        self._cam_combo.currentIndexChanged.connect(self._on_camera_changed)
        layout.addWidget(self._cam_combo)

        layout.addWidget(Divider())

        layout.addWidget(SectionLabel("TARGET FACE"))
        self._target_face_combo = QComboBox()
        self._target_face_combo.addItems(["Largest", "Smallest", "All", "Face 1", "Face 2", "Face 3"])
        self._target_face_combo.currentIndexChanged.connect(self._on_target_face_changed)
        layout.addWidget(self._target_face_combo)

        layout.addWidget(Divider())

        layout.addWidget(SectionLabel("BACKGROUND BLUR"))
        self._bg_blur_combo = QComboBox()
        self._bg_blur_combo.addItems(["Off", "Light", "Heavy"])
        self._bg_blur_combo.currentIndexChanged.connect(self._on_bg_blur_changed)
        layout.addWidget(self._bg_blur_combo)

        layout.addWidget(Divider())

        self.start_btn = StartStopButton()
        self.start_btn.clicked.connect(self._on_start_stop)
        layout.addWidget(self.start_btn)

    def _on_mode(self, mode: str):
        self._mode = mode
        for m, btn in self._mode_btns.items():
            btn.setProperty("selected", m == mode)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.mode_changed.emit(mode)

    def _on_camera_changed(self, idx: int):
        data = self._cam_combo.itemData(idx)
        if data is not None:
            self.camera_changed.emit(data)

    def _on_start_stop(self):
        if self.start_btn._state in ("idle",):
            self.start_clicked.emit()
        elif self.start_btn._state == "live":
            self.stop_clicked.emit()

    _TARGET_FACE_MODES = ["largest", "smallest", "all", "face_1", "face_2", "face_3"]
    _BG_BLUR_MODES = ["off", "light", "heavy"]

    def _on_target_face_changed(self, idx: int):
        mode = self._TARGET_FACE_MODES[idx] if idx < len(self._TARGET_FACE_MODES) else "largest"
        self.target_face_changed.emit(mode)

    def _on_bg_blur_changed(self, idx: int):
        mode = self._BG_BLUR_MODES[idx] if idx < len(self._BG_BLUR_MODES) else "off"
        self.bg_blur_changed.emit(mode)

    def set_target_face_mode(self, mode: str):
        if mode in self._TARGET_FACE_MODES:
            self._target_face_combo.blockSignals(True)
            self._target_face_combo.setCurrentIndex(self._TARGET_FACE_MODES.index(mode))
            self._target_face_combo.blockSignals(False)

    def set_bg_blur(self, strength: str):
        if strength in self._BG_BLUR_MODES:
            self._bg_blur_combo.blockSignals(True)
            self._bg_blur_combo.setCurrentIndex(self._BG_BLUR_MODES.index(strength))
            self._bg_blur_combo.blockSignals(False)

    def populate_cameras(self, cameras: list):
        self._cam_combo.blockSignals(True)
        self._cam_combo.clear()
        if not cameras:
            self._cam_combo.addItem("No cameras found")
        else:
            for c in cameras:
                self._cam_combo.addItem(c["name"], c["id"])
        self._cam_combo.blockSignals(False)

    def set_mode(self, mode: str):
        self._on_mode(mode)
