from PyQt6.QtWidgets import QFrame, QLabel, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QByteArray
from PyQt6.QtGui import QColor

class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        from PyQt6.QtWidgets import QVBoxLayout
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(12, 12, 12, 12)

class SectionLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text.upper(), parent)
        self.setObjectName("sectionLabel")

class StatusDot(QLabel):
    def __init__(self, color: str = "#00E5A0", parent=None):
        super().__init__("●", parent)
        self._color = color
        self._opacity = 1.0
        self.setStyleSheet(f"color: {color}; font-size: 10px;")
        self._anim = None

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, val):
        self._opacity = val
        alpha = int(val * 255)
        c = QColor(self._color)
        c.setAlpha(alpha)
        self.setStyleSheet(f"color: rgba({c.red()},{c.green()},{c.blue()},{alpha}); font-size: 10px;")

    opacity = pyqtProperty(float, get_opacity, set_opacity)

    def set_active(self, active: bool):
        if active:
            self._anim = QPropertyAnimation(self, QByteArray(b"opacity"))
            self._anim.setDuration(1000)
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.3)
            self._anim.setEasingCurve(QEasingCurve.Type.SineCurve)
            self._anim.setLoopCount(-1)
            self._anim.start()
        else:
            if self._anim:
                self._anim.stop()
            self.set_opacity(1.0)

class LiveBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)
        self._dot = StatusDot()
        self._label = QLabel("LIVE")
        self._label.setObjectName("statusLive")
        layout.addWidget(self._dot)
        layout.addWidget(self._label)
        self.setVisible(False)

    def set_visible(self, visible: bool):
        self.setVisible(visible)
        self._dot.set_active(visible)

class FPSDisplay(QLabel):
    def __init__(self, parent=None):
        super().__init__("FPS: 0.0", parent)
        self.setObjectName("statusValue")

    def update_fps(self, fps: float):
        self.setText(f"FPS: {fps:.1f}")

class Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setFixedHeight(1)
        self.setStyleSheet("background-color: #2A2A35; border: none;")
