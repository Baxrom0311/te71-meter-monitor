"""ESP32 Studio — Desktop Application Entrypoint.

Cross-platform (macOS, Windows, Linux) ESP32 Firmware Flasher and Dual Serial Monitor IDE.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont, QIcon
except ImportError:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont, QIcon

from ui.styles import DARK_THEME
from ui.main_window import ESP32StudioWindow


def main():
    # Fix taskbar icon on Windows
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toshelectroapparat.esp32studio.1.0")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("ESP32 Studio")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_THEME)
    app.setFont(QFont("Inter", 10))

    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = ESP32StudioWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
