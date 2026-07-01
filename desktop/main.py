"""TE71/TE73 Meter Tool — Desktop Application.

Toshelectroapparat elektr hisoblagichlari uchun
DLMS/COSEM protokoli orqali RS-485 dasturi.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont, QIcon
from ui.styles import DARK_THEME


def main():
    # Fix taskbar icon on Windows
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toshelectroapparat.metertool.1.0")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Meter Tool")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_THEME)
    app.setFont(QFont("Segoe UI", 11))

    # Set application window icon
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    app.setWindowIcon(QIcon(os.path.join(base_dir, "app_icon.png")))

    # Step 1: Connection dialog
    from ui.connect_dialog import ConnectDialog
    dialog = ConnectDialog()

    while True:
        if dialog.exec() != ConnectDialog.DialogCode.Accepted:
            sys.exit(0)

        settings = dialog.get_settings()

        # Step 2: Try to connect
        try:
            from dlms.connection import DLMSConnection
            from meter import Meter

            def _try_connect(baud: int):
                c = DLMSConnection(settings["port"], baud)
                c.open()
                auth = settings["auth"]
                if auth == 0:
                    ok = c.connect_reader()
                elif auth == 1:
                    ok = c.connect_manager(settings["password"])
                else:
                    ok = c.connect_public()
                if not ok:
                    c.close()
                    return None
                return c

            conn = _try_connect(settings["baud"])

            # Auto-retry with fallback baud if primary failed
            if conn is None and settings.get("fallback_baud"):
                fb = settings["fallback_baud"]
                conn = _try_connect(fb)
                if conn is not None:
                    settings["baud"] = fb  # update for display in sidebar

            if conn is None:
                QMessageBox.warning(
                    dialog, "Ulanish xatosi",
                    "Autentifikatsiya rad etildi.\n"
                    "Hisoblagich ulangan va yoqilganligini tekshiring.\n\n"
                    "COM port va baud rate to'g'riligini tekshiring."
                )
                continue

            meter = Meter(conn)

            # Step 3: Open main window
            from ui.main_window import MainWindow
            window = MainWindow(conn, meter, settings)
            window.show()
            dialog.close()

            sys.exit(app.exec())

        except Exception as e:
            QMessageBox.critical(
                dialog, "Xato",
                f"Ulanish xatosi:\n{str(e)}\n\n"
                "Portni va hisoblagichni tekshiring."
            )
            continue


if __name__ == "__main__":
    main()
