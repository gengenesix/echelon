from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter
from PyQt6.QtCore import Qt, QSize
from pathlib import Path

def _make_tray_icon() -> QIcon:
    # Try multiple locations — works both from source and from installed/bundled app
    candidates = [
        Path(__file__).parent.parent / "assets" / "icons" / "tray_icon.png",
        Path(__file__).parent.parent / "assets" / "icons" / "icon_32.png",
        Path.home() / "xeroclaw" / "echelon" / "assets" / "icons" / "tray_icon.png",
    ]
    for icon_path in candidates:
        if icon_path.exists():
            return QIcon(str(icon_path))
    # Generate a colored square icon
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#7C5CFC"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 28, 28)
    painter.setPen(QColor("white"))
    painter.setFont(painter.font())
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "E")
    painter.end()
    return QIcon(pixmap)

class EchelonTray(QSystemTrayIcon):
    def __init__(self, main_window, app):
        super().__init__(app)
        self.main_window = main_window
        self._is_active = False
        self.setIcon(_make_tray_icon())
        self.setToolTip("Echelon")
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()
        title_action = menu.addAction("Echelon")
        title_action.setEnabled(False)
        menu.addSeparator()
        self._open_action = menu.addAction("Open / Restore")
        self._open_action.triggered.connect(self._show_window)
        self._toggle_action = menu.addAction("Start")
        self._toggle_action.triggered.connect(self._toggle_pipeline)
        menu.addSeparator()
        quit_action = menu.addAction("Quit Echelon")
        quit_action.triggered.connect(self.main_window._quit_app)
        self.setContextMenu(menu)

    def _show_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        self.main_window.showNormal()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.main_window.isVisible() and not self.main_window.isMinimized():
                self.main_window.hide()
            else:
                self._show_window()

    def _toggle_pipeline(self):
        if self._is_active:
            self.main_window.on_stop()
        else:
            self.main_window.on_start()

    def show_notification(self, title: str, message: str):
        self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)

    def set_active(self, active: bool):
        self._is_active = active
        self._toggle_action.setText("Stop" if active else "Start")
