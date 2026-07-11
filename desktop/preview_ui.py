"""Render quick UI previews without opening a real serial connection.

Updated to use the new Controller-based architecture.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from ui.connect_dialog import ConnectDialog
from ui.main_window import MainWindow
from ui.styles import APP_STYLE
from services.meter_service import MeterService, MeterInfo, RelayStatus


class DummyConn:
    """Mock DLMSConnection that does nothing."""
    def __init__(self, *args, **kwargs):
        pass

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

    def get_attribute(self, *_args):
        return None

    def reconnect(self):
        return True


class DummyService(MeterService):
    """Mock MeterService that returns fake data without serial communication."""

    def __init__(self):
        # Don't call super().__init__ with real conn
        self.conn = DummyConn()
        self.info = MeterInfo(
            serial="12345678",
            manufacturer="TEA",
            device_name="TE71",
            firmware="1.0",
            meter_type="TE71",
        )
        self._scalers = {}
        self._on_log = None

    def read_info(self):
        return self.info

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
        return RelayStatus(output_state=True, control_state=1, control_mode=5)


def main():
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)

    dialog = ConnectDialog()
    dialog.grab().save(os.path.join(BASE_DIR, "preview_connect.png"))

    # Create the controller with mock objects
    from controllers.meter_controller import MeterController
    dummy_conn = DummyConn()
    dummy_service = DummyService()
    controller = MeterController(dummy_conn, dummy_service)

    window = MainWindow(controller, {"port": "COM18"})
    window.lbl_meter_type.setText("TE71  |  S/N: 12345678")
    window.lbl_serial.setText("S/N: 12345678")
    window.header_serial_value.setText("12345678")
    window.dashboard.update_values(dummy_service.read_dashboard())
    status = dummy_service.read_relay_status()
    window.relay_panel.update_status(
        status.output_state, status.control_text, status.mode_text, status.control_mode
    )
    window.resize(980, 620)
    window.grab().save(os.path.join(BASE_DIR, "preview_compact.png"))
    window._nav_to(1)
    window.relay_panel.hide_loading()
    window.relay_panel.update_status(
        status.output_state, status.control_text, status.mode_text, status.control_mode
    )
    window.grab().save(os.path.join(BASE_DIR, "preview_compact_relay.png"))
    window._nav_to(2)
    window.registers_panel.populate([
        {"obis": "0.0.96.1.0.255", "name_uz": "Seriya raqami", "name": "Serial", "value": "12345678", "unit": "", "category": "info"},
        {"obis": "1.0.32.7.0.255", "name_uz": "Kuchlanish L1", "name": "Voltage L1", "value": "220.4 V", "unit": "V", "category": "instant"},
        {"obis": "1.0.15.8.0.255", "name_uz": "Umumiy energiya", "name": "Energy", "value": "1534.2 kWh", "unit": "kWh", "category": "energy"},
    ])
    window.grab().save(os.path.join(BASE_DIR, "preview_compact_registers.png"))
    window._nav_to(3)
    window.settings_panel.update_info("12345678", "TEA", "TE71", "1.0", "TE71")
    window.grab().save(os.path.join(BASE_DIR, "preview_compact_settings.png"))
    window._nav_to(0)
    window.resize(1240, 800)
    window.grab().save(os.path.join(BASE_DIR, "preview_main.png"))
    window._nav_to(1)
    window.relay_panel.hide_loading()
    window.relay_panel.update_status(
        status.output_state, status.control_text, status.mode_text, status.control_mode
    )
    window.grab().save(os.path.join(BASE_DIR, "preview_relay.png"))
    window._nav_to(2)
    window.registers_panel.populate([
        {"obis": "0.0.96.1.0.255", "name_uz": "Seriya raqami", "name": "Serial", "value": "12345678", "unit": "", "category": "info"},
        {"obis": "1.0.32.7.0.255", "name_uz": "Kuchlanish L1", "name": "Voltage L1", "value": "220.4 V", "unit": "V", "category": "instant"},
        {"obis": "1.0.15.8.0.255", "name_uz": "Umumiy energiya", "name": "Energy", "value": "1534.2 kWh", "unit": "kWh", "category": "energy"},
    ])
    window.grab().save(os.path.join(BASE_DIR, "preview_registers.png"))
    window._nav_to(3)
    window.settings_panel.update_info("12345678", "TEA", "TE71", "1.0", "TE71")
    window.grab().save(os.path.join(BASE_DIR, "preview_settings.png"))

    QTimer.singleShot(0, app.quit)
    app.exec()


if __name__ == "__main__":
    main()
