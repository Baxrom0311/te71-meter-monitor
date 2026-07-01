"""Render quick UI previews without opening a real serial connection."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from ui.connect_dialog import ConnectDialog
from ui.main_window import MainWindow
from ui.styles import APP_STYLE


class DummyConn:
    connected = True
    client_addr = 1

    def set_callbacks(self, **_kwargs):
        pass

    def close(self):
        pass

    def disconnect(self):
        pass

    def connect_reader(self):
        return True


class DummyMeter:
    def set_log_callback(self, _callback):
        pass

    def read_info(self):
        class Info:
            serial = "12345678"
            manufacturer = "TEA"
            device_name = "TE71"
            firmware = "1.0"
            meter_type = "TE71"

        return Info()

    def read_scalers(self):
        pass

    def read_dashboard(self):
        return {
            "voltage_l1": ("220.4 V", 220.4),
            "current_l1": ("1.26 A", 1.26),
            "power_active_plus": ("278 W", 278),
            "frequency": ("50.0 Hz", 50.0),
            "power_factor": ("0.98", 0.98),
            "energy_total": ("1534.2 kWh", 1534.2),
            "energy_t1": ("1020.1 kWh", 1020.1),
            "energy_t2": ("514.1 kWh", 514.1),
        }

    def read_relay_status(self):
        class Status:
            output_state = True
            control_text = "connected"
            mode_text = "remote disconnect/reconnect"

        return Status()


def main():
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)

    dialog = ConnectDialog()
    dialog.grab().save("preview_connect.png")

    window = MainWindow(DummyConn(), DummyMeter(), {"port": "COM18"})
    window.lbl_meter_type.setText("TE71  |  S/N: 12345678")
    window.lbl_serial.setText("S/N: 12345678")
    window.header_serial_value.setText("12345678")
    window.dashboard.update_values(DummyMeter().read_dashboard())
    window.relay_panel.update_status(True, "connected", "remote disconnect/reconnect")
    window.grab().save("preview_main.png")
    window._nav_to(1)
    window.grab().save("preview_relay.png")
    window._nav_to(2)
    window.registers_panel.populate([
        {"obis": "0.0.96.1.0.255", "name_uz": "Seriya raqami", "name": "Serial", "value": "12345678", "unit": "", "category": "info"},
        {"obis": "1.0.32.7.0.255", "name_uz": "Kuchlanish L1", "name": "Voltage L1", "value": "220.4 V", "unit": "V", "category": "instant"},
        {"obis": "1.0.15.8.0.255", "name_uz": "Umumiy energiya", "name": "Energy", "value": "1534.2 kWh", "unit": "kWh", "category": "energy"},
    ])
    window.grab().save("preview_registers.png")

    QTimer.singleShot(0, app.quit)
    app.exec()


if __name__ == "__main__":
    main()
