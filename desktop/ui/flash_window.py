"""ESP32 Flash Window — firmware yuklash va serial monitor.

Faqat UI layout va user interactions boshqaradi.
PlatformIO bilan barcha aloqalar FlashController va FlashService orqali amalga oshiriladi.
"""
import sys
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QTextEdit, QProgressBar,
    QFrame, QMessageBox, QRadioButton, QButtonGroup, QTabWidget,
    QCheckBox, QScrollArea, QSpinBox,
)
from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtGui import QFont, QColor, QTextCursor

from controllers.flash_controller import FlashController

# Firmware turlari
FIRMWARE_TYPES = [
    ("electricity", "⚡  Elektr",        "TE71/TE73 RS-485 DLMS hisoblagich"),
    ("soil",        "🌱  Tuproq namligi", "Kapasitiv tuproq namligi sensori (ADC)"),
    ("sound",       "🔊  Ovoz",          "Mikrofon ADC ovoz darajasi sensori"),
    ("water",       "💧  Suv",           "2x analog bosim sensori"),
    ("gas",         "🔥  Gaz",           "1x analog bosim sensori"),
]

DEFAULT_SERVER  = "https://ss.boos.uz"
DEFAULT_TOKEN   = "T30gwzZJ6YTvQeLRMCZyTi-GBAYogsQV"
DEFAULT_WIFI_SSID = "12"
DEFAULT_WIFI_PASS = "12345678"


class FlashWindow(QMainWindow):
    """Firmware yuklash va serial monitor oynasi (Faqat UI)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ESP32 Dasturchi — Firmware Yuklash")
        self.setMinimumSize(720, 500)
        self.resize(1020, 720)

        # Initialize controller
        self.controller = FlashController()

        # Load settings storage
        self.settings_storage = QSettings("Toshelectroapparat", "MeterTool")

        self._fw_radios = {}
        self._setup_ui()
        self._check_pio()
        self._connect_signals()

    def _setup_ui(self):
        from .styles import DARK_THEME
        self.setStyleSheet(DARK_THEME)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sol panel (boshqaruv) ──
        left_content = QWidget()
        left_content.setObjectName("sidebar")
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(20, 24, 20, 20)
        left_layout.setSpacing(14)

        brand = QLabel("ESP32 Dasturchi")
        brand.setObjectName("brand")
        left_layout.addWidget(brand)

        sub = QLabel("Firmware yuklash va serial monitor")
        sub.setStyleSheet("color:#94a3b8; font-size:12px;")
        left_layout.addWidget(sub)

        self.lbl_pio = QLabel()
        self.lbl_pio.setStyleSheet("font-size:12px; font-weight:700;")
        left_layout.addWidget(self.lbl_pio)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#1e3a5f;")
        left_layout.addWidget(sep)

        # USB Port
        left_layout.addWidget(self._section("USB Port (ESP32)"))
        port_row = QHBoxLayout()
        self.combo_port = QComboBox()
        self.combo_port.setMinimumHeight(36)
        port_row.addWidget(self.combo_port, 1)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedSize(36, 36)
        btn_refresh.setToolTip("Portlarni yangilash")
        btn_refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(btn_refresh)
        left_layout.addLayout(port_row)

        # Firmware turi
        left_layout.addWidget(self._section("Firmware turi"))
        self._fw_group = QButtonGroup(self)
        for env, label, desc in FIRMWARE_TYPES:
            rb = QRadioButton(label)
            rb.setToolTip(desc)
            self._fw_group.addButton(rb)
            self._fw_radios[env] = rb
            left_layout.addWidget(rb)
        self._fw_radios["electricity"].setChecked(True)

        # Connect radio buttons to show/hide soil options
        for env, rb in self._fw_radios.items():
            rb.toggled.connect(self._on_fw_type_changed)

        # Soil sensor options widget (only visible when soil is selected)
        self.soil_opts_widget = QWidget()
        soil_opts_layout = QVBoxLayout(self.soil_opts_widget)
        soil_opts_layout.setContentsMargins(0, 0, 0, 0)
        soil_opts_layout.setSpacing(6)

        soil_opts_layout.addWidget(self._section("Sensor opsiyalari"))

        self.chk_lcd = QCheckBox("LCD 16x2 I2C ekran bor")
        self.chk_lcd.setToolTip("Yoqilsa: soil_wifi_lcd, o'chirilsa: soil_wifi")
        soil_opts_layout.addWidget(self.chk_lcd)

        soil_opts_layout.addWidget(self._small_label("ADC GPIO pini (sensor AOUT)"))
        self.spin_adc_pin = QSpinBox()
        self.spin_adc_pin.setRange(0, 39)
        self.spin_adc_pin.setValue(32)
        self.spin_adc_pin.setSuffix(" (GPIO)")
        self.spin_adc_pin.setMinimumHeight(32)
        soil_opts_layout.addWidget(self.spin_adc_pin)

        soil_opts_layout.addWidget(self._small_label("Quruq qiymat (havoda o'lchang)"))
        self.spin_dry = QSpinBox()
        self.spin_dry.setRange(1000, 4095)
        self.spin_dry.setValue(3300)
        self.spin_dry.setMinimumHeight(32)
        soil_opts_layout.addWidget(self.spin_dry)

        soil_opts_layout.addWidget(self._small_label("Nam qiymat (suvda o'lchang)"))
        self.spin_wet = QSpinBox()
        self.spin_wet.setRange(500, 3000)
        self.spin_wet.setValue(1400)
        self.spin_wet.setMinimumHeight(32)
        soil_opts_layout.addWidget(self.spin_wet)

        left_layout.addWidget(self.soil_opts_widget)
        self.soil_opts_widget.setVisible(False)

        # Sound sensor options widget (only visible when sound is selected)
        self.sound_opts_widget = QWidget()
        sound_opts_layout = QVBoxLayout(self.sound_opts_widget)
        sound_opts_layout.setContentsMargins(0, 0, 0, 0)
        sound_opts_layout.setSpacing(6)

        sound_opts_layout.addWidget(self._section("Sensor opsiyalari"))

        self.chk_sound_lcd = QCheckBox("LCD 16x2 I2C ekran bor")
        self.chk_sound_lcd.setToolTip("Yoqilsa: sound_wifi_lcd, o'chirilsa: sound_wifi")
        sound_opts_layout.addWidget(self.chk_sound_lcd)

        sound_opts_layout.addWidget(self._small_label("ADC GPIO pini (mikrofon AOUT)"))
        self.spin_sound_pin = QSpinBox()
        self.spin_sound_pin.setRange(0, 39)
        self.spin_sound_pin.setValue(34)
        self.spin_sound_pin.setSuffix(" (GPIO)")
        self.spin_sound_pin.setMinimumHeight(32)
        sound_opts_layout.addWidget(self.spin_sound_pin)

        sound_opts_layout.addWidget(self._small_label("O'qish intervali (ms)"))
        self.spin_sound_interval = QSpinBox()
        self.spin_sound_interval.setRange(1000, 60000)
        self.spin_sound_interval.setSingleStep(1000)
        self.spin_sound_interval.setValue(10000)
        self.spin_sound_interval.setSuffix(" ms")
        self.spin_sound_interval.setMinimumHeight(32)
        sound_opts_layout.addWidget(self.spin_sound_interval)

        left_layout.addWidget(self.sound_opts_widget)
        self.sound_opts_widget.setVisible(False)

        # Load saved settings values
        saved_server = self.settings_storage.value("flash_server", DEFAULT_SERVER)
        saved_prod_token = self.settings_storage.value("flash_prod_token", DEFAULT_TOKEN)
        saved_test_token = self.settings_storage.value("flash_test_token", DEFAULT_TOKEN)
        saved_test_mode = self.settings_storage.value("flash_test_mode", False, type=bool)
        saved_ssid = self.settings_storage.value("flash_wifi_ssid", DEFAULT_WIFI_SSID)
        saved_wifi_pass = self.settings_storage.value("flash_wifi_pass", DEFAULT_WIFI_PASS)

        # Load soil settings and apply to widgets
        saved_lcd = self.settings_storage.value("soil_lcd", False, type=bool)
        saved_adc_pin = self.settings_storage.value("soil_adc_pin", 32, type=int)
        saved_dry = self.settings_storage.value("soil_dry", 3300, type=int)
        saved_wet = self.settings_storage.value("soil_wet", 1400, type=int)

        self.chk_lcd.setChecked(saved_lcd)
        self.spin_adc_pin.setValue(saved_adc_pin)
        self.spin_dry.setValue(saved_dry)
        self.spin_wet.setValue(saved_wet)

        # Connect soil widgets to save settings
        self.chk_lcd.toggled.connect(lambda v: self.settings_storage.setValue("soil_lcd", v))
        self.spin_adc_pin.valueChanged.connect(lambda v: self.settings_storage.setValue("soil_adc_pin", v))
        self.spin_dry.valueChanged.connect(lambda v: self.settings_storage.setValue("soil_dry", v))
        self.spin_wet.valueChanged.connect(lambda v: self.settings_storage.setValue("soil_wet", v))

        # Load sound settings and apply to widgets
        saved_sound_lcd = self.settings_storage.value("sound_lcd", False, type=bool)
        saved_sound_pin = self.settings_storage.value("sound_adc_pin", 34, type=int)
        saved_sound_interval = self.settings_storage.value("sound_interval", 10000, type=int)

        self.chk_sound_lcd.setChecked(saved_sound_lcd)
        self.spin_sound_pin.setValue(saved_sound_pin)
        self.spin_sound_interval.setValue(saved_sound_interval)

        # Connect sound widgets to save settings
        self.chk_sound_lcd.toggled.connect(lambda v: self.settings_storage.setValue("sound_lcd", v))
        self.spin_sound_pin.valueChanged.connect(lambda v: self.settings_storage.setValue("sound_adc_pin", v))
        self.spin_sound_interval.valueChanged.connect(lambda v: self.settings_storage.setValue("sound_interval", v))

        # Server
        left_layout.addWidget(self._section("Server sozlamalari"))
        left_layout.addWidget(self._small_label("Server URL"))
        self.txt_server = QLineEdit(saved_server)
        self.txt_server.setMinimumHeight(34)
        self.txt_server.textEdited.connect(lambda v: self.settings_storage.setValue("flash_server", v.strip()))
        left_layout.addWidget(self.txt_server)

        self.lbl_token_title = self._small_label("Test Device Token" if saved_test_mode else "Production Device Token")
        left_layout.addWidget(self.lbl_token_title)
        
        self.txt_token = QLineEdit(saved_test_token if saved_test_mode else saved_prod_token)
        self.txt_token.setMinimumHeight(34)
        self.txt_token.textEdited.connect(self._on_token_edited)
        left_layout.addWidget(self.txt_token)

        self.chk_test_mode = QCheckBox("Test mode (productionga aralashmaydi)")
        self.chk_test_mode.setToolTip("Yoqilsa firmware register paytida is_test_device=true yuboradi.")
        self.chk_test_mode.setChecked(saved_test_mode)
        self.chk_test_mode.toggled.connect(self._on_test_mode_toggled)
        left_layout.addWidget(self.chk_test_mode)

        # WiFi
        left_layout.addWidget(self._section("WiFi sozlamalari"))
        left_layout.addWidget(self._small_label("WiFi SSID"))
        self.txt_ssid = QLineEdit(saved_ssid)
        self.txt_ssid.setMinimumHeight(34)
        self.txt_ssid.textEdited.connect(lambda v: self.settings_storage.setValue("flash_wifi_ssid", v.strip()))
        left_layout.addWidget(self.txt_ssid)

        left_layout.addWidget(self._small_label("WiFi Parol"))
        self.txt_wifi_pass = QLineEdit(saved_wifi_pass)
        self.txt_wifi_pass.setMinimumHeight(34)
        self.txt_wifi_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_wifi_pass.textEdited.connect(lambda v: self.settings_storage.setValue("flash_wifi_pass", v))
        left_layout.addWidget(self.txt_wifi_pass)

        chk_show = QCheckBox("Parolni ko'rsatish")
        chk_show.toggled.connect(
            lambda v: self.txt_wifi_pass.setEchoMode(
                QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password
            )
        )
        left_layout.addWidget(chk_show)

        left_layout.addSpacing(8)

        # Action Buttons
        self.btn_flash = QPushButton("⚡  FLASH QILISH")
        self.btn_flash.setObjectName("primary")
        self.btn_flash.setMinimumHeight(44)
        self.btn_flash.clicked.connect(self._start_flash)
        left_layout.addWidget(self.btn_flash)

        self.btn_build = QPushButton("🔨  Faqat build")
        self.btn_build.setMinimumHeight(36)
        self.btn_build.clicked.connect(self._start_build_only)
        left_layout.addWidget(self.btn_build)

        self.btn_cancel = QPushButton("■  Bekor qilish")
        self.btn_cancel.setObjectName("sidebarDanger")
        self.btn_cancel.setMinimumHeight(36)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        left_layout.addWidget(self.btn_cancel)

        left_layout.addStretch()

        # Scroll Wrapper
        from PyQt6.QtWidgets import QScrollArea as _SA
        left_scroll = _SA()
        left_scroll.setWidget(left_content)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(300)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setStyleSheet("QScrollArea { background: #03050a; border-right: 1px solid #161e2e; }")

        root.addWidget(left_scroll)

        # ── O'ng panel ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 20, 20, 16)
        right_layout.setSpacing(10)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar{background:#1e3a5f;border:none;border-radius:4px;}"
            "QProgressBar::chunk{background:#3b82f6;border-radius:4px;}"
        )
        right_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Tayyor")
        self.lbl_status.setStyleSheet("color:#94a3b8; font-size:12px; font-weight:600;")
        right_layout.addWidget(self.lbl_status)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane{border:1px solid #1e3a5f;border-radius:6px;}"
            "QTabBar::tab{background:#0f2035;color:#94a3b8;padding:8px 18px;border-radius:6px 6px 0 0;}"
            "QTabBar::tab:selected{background:#1e3a5f;color:#e2e8f0;}"
        )
        right_layout.addWidget(self.tabs)

        # Flash log
        self.flash_log = QTextEdit()
        self.flash_log.setReadOnly(True)
        self.flash_log.setFont(QFont("Consolas" if sys.platform == "win32" else "Menlo", 11))
        self.flash_log.setStyleSheet(
            "QTextEdit{background:#06111e;color:#cbd5e1;border:none;border-radius:6px;}"
        )
        self.tabs.addTab(self.flash_log, "📋  Flash Log")

        # Serial monitor
        monitor_widget = QWidget()
        monitor_layout = QVBoxLayout(monitor_widget)
        monitor_layout.setContentsMargins(0, 8, 0, 0)
        monitor_layout.setSpacing(6)

        mon_ctrl = QHBoxLayout()
        self.combo_mon_baud = QComboBox()
        self.combo_mon_baud.addItems(["115200", "9600", "57600", "921600"])
        self.combo_mon_baud.setFixedWidth(120)
        mon_ctrl.addWidget(QLabel("Baud:"))
        mon_ctrl.addWidget(self.combo_mon_baud)
        mon_ctrl.addStretch()

        self.btn_mon_start = QPushButton("▶  Boshlash")
        self.btn_mon_start.setFixedHeight(32)
        self.btn_mon_start.clicked.connect(self._start_monitor)
        mon_ctrl.addWidget(self.btn_mon_start)

        self.btn_mon_stop = QPushButton("■  To'xtatish")
        self.btn_mon_stop.setFixedHeight(32)
        self.btn_mon_stop.setEnabled(False)
        self.btn_mon_stop.clicked.connect(self._stop_monitor)
        mon_ctrl.addWidget(self.btn_mon_stop)

        btn_mon_clear = QPushButton("🗑")
        btn_mon_clear.setFixedSize(32, 32)
        btn_mon_clear.clicked.connect(self._clear_monitor)
        mon_ctrl.addWidget(btn_mon_clear)

        monitor_layout.addLayout(mon_ctrl)

        self.monitor_log = QTextEdit()
        self.monitor_log.setReadOnly(True)
        self.monitor_log.setFont(QFont("Consolas" if sys.platform == "win32" else "Menlo", 11))
        self.monitor_log.setStyleSheet(
            "QTextEdit{background:#06111e;color:#86efac;border:none;border-radius:6px;}"
        )
        monitor_layout.addWidget(self.monitor_log)

        self.tabs.addTab(monitor_widget, "📡  Serial Monitor")

        root.addWidget(right, 1)
        self._refresh_ports()

    # ── Signal Connections ──────────────────────────────────────────────────

    def _connect_signals(self):
        self.controller.log_line.connect(self._on_log)
        self.controller.progress.connect(self.progress_bar.setValue)
        self.controller.flash_finished.connect(self._on_flash_finished)
        self.controller.monitor_line.connect(self._on_monitor_line)
        self.controller.monitor_error.connect(self._on_monitor_error)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet("color:#3b82f6; font-size:11px; font-weight:800; letter-spacing:1px;")
        return lbl

    def _small_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#475467; font-size:12px; font-weight:700;")
        return lbl

    def _on_fw_type_changed(self):
        soil_rb = self._fw_radios.get("soil")
        sound_rb = self._fw_radios.get("sound")
        self.soil_opts_widget.setVisible(soil_rb is not None and soil_rb.isChecked())
        self.sound_opts_widget.setVisible(sound_rb is not None and sound_rb.isChecked())

    def _check_pio(self):
        if self.controller.pio_path:
            self.lbl_pio.setText("✓ PlatformIO topildi")
            self.lbl_pio.setStyleSheet("font-size:12px; font-weight:700; color:#86efac;")
        else:
            self.lbl_pio.setText("✗ PlatformIO topilmadi!")
            self.lbl_pio.setStyleSheet("font-size:12px; font-weight:700; color:#f87171;")
            self.btn_flash.setEnabled(False)
            self.btn_build.setEnabled(False)
            self._log("PlatformIO topilmadi. O'rnatish uchun:\n  pip install platformio\n  yoki  https://platformio.org/install/cli", "#f87171")

        if self.controller.project_root:
            self._log(f"Loyiha: {self.controller.project_root}", "#64748b")
        else:
            self._log("platformio.ini topilmadi. Loyiha papkasidan ishga tushiring.", "#fbbf24")

    def _refresh_ports(self):
        self.combo_port.clear()
        ports = sorted(serial.tools.list_ports.comports(), key=lambda p: p.device)
        for p in ports:
            desc = p.description if p.description != p.device else ""
            vid_pid = f" [{p.vid:04X}:{p.pid:04X}]" if p.vid else ""
            label = f"{p.device}  {desc}{vid_pid}".strip()
            self.combo_port.addItem(label, p.device)
        if not ports:
            self.combo_port.addItem("Port topilmadi", "")

    def _selected_firmware(self) -> tuple[str, str]:
        """Returns (sensor_name, pio_env)"""
        for sensor, rb in self._fw_radios.items():
            if rb.isChecked():
                if sensor == "soil":
                    env = "soil_wifi_lcd" if self.chk_lcd.isChecked() else "soil_wifi"
                    return sensor, env
                if sensor == "sound":
                    env = "sound_wifi_lcd" if self.chk_sound_lcd.isChecked() else "sound_wifi"
                    return sensor, env
                return sensor, sensor  # electricity, water, gas
        return "electricity", "electricity"

    def _log(self, text: str, color: str = "#cbd5e1"):
        self.flash_log.moveCursor(QTextCursor.MoveOperation.End)
        self.flash_log.setTextColor(QColor(color))
        self.flash_log.insertPlainText(text + "\n")
        self.flash_log.moveCursor(QTextCursor.MoveOperation.End)

    def _set_busy(self, busy: bool):
        self.btn_flash.setEnabled(not busy and bool(self.controller.pio_path))
        self.btn_build.setEnabled(not busy and bool(self.controller.pio_path))
        self.btn_cancel.setEnabled(busy)
        self.combo_port.setEnabled(not busy)
        for rb in self._fw_radios.values():
            rb.setEnabled(not busy)

    # ── Flash Actions ────────────────────────────────────────────────────────

    def _start_flash(self):
        port = self.combo_port.currentData()
        if not port:
            QMessageBox.warning(self, "Xato", "USB port tanlanmagan!")
            return
        self._run_pio(port=port, build_only=False)

    def _start_build_only(self):
        self._run_pio(port="", build_only=True)

    def _get_sensor_opts(self, sensor: str) -> dict:
        if sensor == "soil":
            return {
                "lcd":     self.chk_lcd.isChecked(),
                "adc_pin": self.spin_adc_pin.value(),
                "dry":     self.spin_dry.value(),
                "wet":     self.spin_wet.value(),
            }
        if sensor == "sound":
            return {
                "lcd":      self.chk_sound_lcd.isChecked(),
                "adc_pin":  self.spin_sound_pin.value(),
                "interval": self.spin_sound_interval.value(),
            }
        return {}

    def _run_pio(self, port: str, build_only: bool):
        if self.controller.is_flashing():
            return

        self.flash_log.clear()
        self.progress_bar.setValue(0)

        sensor, fw_env = self._selected_firmware()
        self.lbl_status.setText(f"{'Build' if build_only else 'Flash'}: {fw_env}...")
        self.lbl_status.setStyleSheet("color:#60a5fa; font-size:12px; font-weight:600;")

        self._set_busy(True)
        self.controller.start_flash(
            sensor=sensor,
            env=fw_env,
            port=port,
            build_only=build_only,
            server=self.txt_server.text().strip() or DEFAULT_SERVER,
            token=self.txt_token.text().strip() or DEFAULT_TOKEN,
            ssid=self.txt_ssid.text().strip() or DEFAULT_WIFI_SSID,
            wifi_pass=self.txt_wifi_pass.text() or DEFAULT_WIFI_PASS,
            test_mode=self.chk_test_mode.isChecked(),
            sensor_opts=self._get_sensor_opts(sensor),
        )

    def _cancel(self):
        self.controller.cancel_flash()
        self.lbl_status.setText("Bekor qilinmoqda...")

    def _on_log(self, text: str, color: str):
        self._log(text, color)

    def _on_flash_finished(self, success: bool, message: str):
        self._set_busy(False)
        self.progress_bar.setValue(100 if success else self.progress_bar.value())

        if success:
            self.lbl_status.setText(f"✓  {message}")
            self.lbl_status.setStyleSheet("color:#86efac; font-size:12px; font-weight:700;")
            self._log(f"\n✓  {message}", "#86efac")

            # Auto-switch to serial monitor
            port = self.combo_port.currentData()
            if port and not self.btn_build.isEnabled():
                reply = QMessageBox.question(
                    self, "Serial Monitor",
                    "Flash muvaffaqiyatli!\nSerial monitor ochilsinmi?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.tabs.setCurrentIndex(1)
                    QTimer.singleShot(500, self._start_monitor)
        else:
            self.lbl_status.setText(f"✗  {message}")
            self.lbl_status.setStyleSheet("color:#f87171; font-size:12px; font-weight:700;")
            self._log(f"\n✗  {message}", "#f87171")

    # ── Serial Monitor Actions ──────────────────────────────────────────────

    def _start_monitor(self):
        if self.controller.is_monitoring():
            return
        port = self.combo_port.currentData()
        if not port:
            QMessageBox.warning(self, "Xato", "USB port tanlanmagan!")
            return
        baud = int(self.combo_mon_baud.currentText())
        self.monitor_log.clear()
        self._mon_log(f"[Serial Monitor] {port} @ {baud} baud", "#94a3b8")
        self._mon_log("─" * 50, "#1e3a5f")
        self.controller.start_monitor(port, baud)
        self.btn_mon_start.setEnabled(False)
        self.btn_mon_stop.setEnabled(True)

    def _stop_monitor(self):
        self.controller.stop_monitor()
        self.btn_mon_start.setEnabled(True)
        self.btn_mon_stop.setEnabled(False)
        self._mon_log("[Monitor to'xtatildi]", "#94a3b8")

    def _clear_monitor(self):
        self.monitor_log.clear()

    def _on_monitor_line(self, line: str):
        self._mon_log(line)

    def _on_monitor_error(self, err: str):
        self._mon_log(f"[Xato] {err}", "#f87171")
        self.btn_mon_start.setEnabled(True)
        self.btn_mon_stop.setEnabled(False)

    def _mon_log(self, text: str, color: str = "#86efac"):
        self.monitor_log.moveCursor(QTextCursor.MoveOperation.End)
        self.monitor_log.setTextColor(QColor(color))
        self.monitor_log.insertPlainText(text + "\n")
        self.monitor_log.moveCursor(QTextCursor.MoveOperation.End)

    def _on_token_edited(self, text: str):
        val = text.strip()
        if self.chk_test_mode.isChecked():
            self.settings_storage.setValue("flash_test_token", val)
        else:
            self.settings_storage.setValue("flash_prod_token", val)

    def _on_test_mode_toggled(self, checked: bool):
        self.settings_storage.setValue("flash_test_mode", checked)
        if checked:
            self.lbl_token_title.setText("Test Device Token")
            test_tok = self.settings_storage.value("flash_test_token", DEFAULT_TOKEN)
            self.txt_token.setText(test_tok)
        else:
            self.lbl_token_title.setText("Production Device Token")
            prod_tok = self.settings_storage.value("flash_prod_token", DEFAULT_TOKEN)
            self.txt_token.setText(prod_tok)

    # ── Close Event ──────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self.controller.cancel_flash()
        self.controller.stop_monitor()
        event.accept()
