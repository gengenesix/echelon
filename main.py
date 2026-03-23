import sys
import signal
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from utils.logger import setup_logging
from config.manager import AppConfig, ConfigManager
from core.hardware import HardwareDetector
from ui.main_window import MainWindow
from ui.onboarding import OnboardingDialog
from ui.tray import EchelonTray

def main():
    setup_logging()
    logger = logging.getLogger("echelon.main")
    logger.info("Echelon starting up...")

    app = QApplication(sys.argv)
    app.setApplicationName("Echelon")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("Echelon")
    # AA_UseHighDpiPixmaps removed in PyQt6 6.x — no longer needed

    qss_path = Path(__file__).parent / "assets" / "styles" / "theme.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text())
        logger.info("Stylesheet loaded")
    else:
        logger.warning("Stylesheet not found, using defaults")

    config_mgr = ConfigManager()
    config = config_mgr.load()

    hw_detector = HardwareDetector()
    hw_info = hw_detector.detect()
    hw_detector.log_system_info(hw_info)

    if config.first_launch:
        config.performance_mode = hw_info.recommended_mode

    was_first_launch = config.first_launch

    if config.first_launch:
        onboarding = OnboardingDialog(config)
        result = onboarding.exec()
        if result != OnboardingDialog.DialogCode.Accepted:
            logger.info("Onboarding cancelled, exiting")
            sys.exit(0)

    window = MainWindow(config, hw_info)
    tray = EchelonTray(window, app)
    window.tray = tray
    tray.show()

    if not config.start_minimized:
        window.show()
        if was_first_launch:
            window.show_tutorial()
    else:
        tray.show_notification("Echelon", "Started in background. Click tray icon to open.")

    signal.signal(signal.SIGINT, lambda *_: app.quit())

    logger.info("Echelon UI ready")
    exit_code = app.exec()

    config_mgr.save(config)
    logger.info(f"Echelon exiting with code {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
