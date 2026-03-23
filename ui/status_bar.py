import os
import psutil
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer


def _make_pill(text, color="#5C5FFF"):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"""
        QLabel {{
            background: {color}22;
            color: {color};
            border: 1px solid {color}44;
            border-radius: 10px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 600;
            font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', monospace;
        }}
    """)
    return lbl


class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet(
            "background-color: #0E0F16; border-top: 1px solid #1A1B24;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        # Status pill
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(
            "color: #50516A; font-size: 10px; background: transparent;"
        )
        self._status_lbl = QLabel("Idle")
        self._status_lbl.setStyleSheet(
            "color: #8B8CA8; font-size: 12px; background: transparent;"
        )
        layout.addWidget(self._status_dot)
        layout.addWidget(self._status_lbl)

        self._sep1 = QLabel("·")
        self._sep1.setStyleSheet("color: #252632; background: transparent;")
        layout.addWidget(self._sep1)

        # FPS pill
        self._fps_lbl = _make_pill("FPS: 0.0", "#22D98F")
        layout.addWidget(self._fps_lbl)

        # Latency pill
        self._latency_lbl = _make_pill("0ms", "#5C5FFF")
        layout.addWidget(self._latency_lbl)

        # GPU mode pill
        self._gpu_lbl = _make_pill("CPU", "#8B8CA8")
        layout.addWidget(self._gpu_lbl)

        # Virtual cam pill
        self._vcam_lbl = _make_pill("◉ VCam Off", "#50516A")
        layout.addWidget(self._vcam_lbl)

        # RAM pill
        self._ram_lbl = _make_pill("RAM --%", "#8B8CA8")
        layout.addWidget(self._ram_lbl)

        # CPU pill
        self._cpu_lbl = _make_pill("CPU --%", "#8B8CA8")
        layout.addWidget(self._cpu_lbl)

        # Frame skip indicator
        self._skip_lbl = QLabel("")
        self._skip_lbl.setStyleSheet(
            "color: #5C5FFF; font-size: 11px; background: transparent;"
        )
        layout.addWidget(self._skip_lbl)

        layout.addStretch()

        # System stats timer — updates RAM/CPU every 2 seconds
        self._process = psutil.Process(os.getpid())
        self._process.cpu_percent(interval=None)
        self._sys_timer = QTimer(self)
        self._sys_timer.timeout.connect(self._update_sys_stats)
        self._sys_timer.start(2000)

    def _update_sys_stats(self):
        try:
            ram = psutil.virtual_memory().percent
            cpu = self._process.cpu_percent(interval=None)
            ram_color = "#22D98F" if ram < 60 else ("#FFB547" if ram < 80 else "#FF5CA8")
            cpu_color = "#22D98F" if cpu < 50 else ("#FFB547" if cpu < 80 else "#FF5CA8")
            self._ram_lbl.setText(f"RAM {ram:.0f}%")
            self._ram_lbl.setStyleSheet(f"""
                QLabel {{
                    background: {ram_color}22;
                    color: {ram_color};
                    border: 1px solid {ram_color}44;
                    border-radius: 10px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 600;
                    font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', monospace;
                }}
            """)
            self._cpu_lbl.setText(f"CPU {cpu:.0f}%")
            self._cpu_lbl.setStyleSheet(f"""
                QLabel {{
                    background: {cpu_color}22;
                    color: {cpu_color};
                    border: 1px solid {cpu_color}44;
                    border-radius: 10px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 600;
                    font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', monospace;
                }}
            """)
        except Exception:
            pass

    def update_status(self, text: str):
        self._status_lbl.setText(text)
        if text == "Live":
            self._status_dot.setStyleSheet(
                "color: #22D98F; font-size: 10px; background: transparent;"
            )
            self._status_lbl.setStyleSheet(
                "color: #22D98F; font-size: 12px; font-weight: 600; background: transparent;"
            )
        elif text in ("Stopped", "Idle"):
            self._status_dot.setStyleSheet(
                "color: #50516A; font-size: 10px; background: transparent;"
            )
            self._status_lbl.setStyleSheet(
                "color: #8B8CA8; font-size: 12px; background: transparent;"
            )
        else:
            self._status_dot.setStyleSheet(
                "color: #FFB547; font-size: 10px; background: transparent;"
            )
            self._status_lbl.setStyleSheet(
                "color: #FFB547; font-size: 12px; background: transparent;"
            )

    def update_fps(self, fps: float):
        if fps > 20:
            color = "#22D98F"
        elif fps >= 10:
            color = "#FFB547"
        else:
            color = "#FF5CA8"
        self._fps_lbl.setText(f"FPS: {fps:.1f}")
        self._fps_lbl.setStyleSheet(f"""
            QLabel {{
                background: {color}22;
                color: {color};
                border: 1px solid {color}44;
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
                font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', monospace;
            }}
        """)

    def update_latency(self, ms: float):
        self._latency_lbl.setText(f"{ms:.0f}ms")

    def update_gpu_mode(self, mode: str):
        color = "#5C5FFF" if mode == "CUDA" else "#8B8CA8"
        self._gpu_lbl.setText(mode)
        self._gpu_lbl.setStyleSheet(f"""
            QLabel {{
                background: {color}22;
                color: {color};
                border: 1px solid {color}44;
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
                font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', monospace;
            }}
        """)

    def update_vcam(self, active: bool):
        if active:
            color = "#22D98F"
            text = "◉ VCam On"
        else:
            color = "#50516A"
            text = "◉ VCam Off"
        self._vcam_lbl.setText(text)
        self._vcam_lbl.setStyleSheet(f"""
            QLabel {{
                background: {color}22;
                color: {color};
                border: 1px solid {color}44;
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
                font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', monospace;
            }}
        """)

    def update_frame_skip(self, skip: int):
        if skip > 0:
            self._skip_lbl.setText(f"skip:{skip}")
        else:
            self._skip_lbl.setText("")
