"""ESP32 Studio — Main Window UI.

Cross-platform PySide6 / PyQt6 main interface for ESP32 Firmware Flashing, Dual Serial Monitoring,
LoRa Packet Inspecting, and ESP32 NVS Configuration.
"""
import os
import sys
from datetime import datetime

try:
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QComboBox, QLineEdit, QTextEdit, QProgressBar,
        QFrame, QMessageBox, QTabWidget, QCheckBox, QFileDialog, QSplitter,
        QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox
    )
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont, QColor, QTextCursor, QIcon
except ImportError:
    from PyQt6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QComboBox, QLineEdit, QTextEdit, QProgressBar,
        QFrame, QMessageBox, QTabWidget, QCheckBox, QFileDialog, QSplitter,
        QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont, QColor, QTextCursor, QIcon

from controllers.flash_controller import FlashController
from services.esptool_service import EsptoolService
from services.flash_service import FlashService
from services.lora_decoder import LoRaPacketDecoder
from .styles import DARK_THEME


class ESP32StudioWindow(QMainWindow):
    """ESP32 Dasturchi, Serial Monitor va LoRa Paket Inspector oynasi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ ESP32 Studio — Flasher & LoRa Inspector")
        self.setMinimumSize(1080, 720)
        self.resize(1240, 820)

        self.controller = FlashController()
        self._serial_workers = {}
        self._setup_ui()
        self._refresh_ports()

    def _setup_ui(self):
        self.setStyleSheet(DARK_THEME)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # ── Top Bar ──
        header = QFrame()
        header.setObjectName("card")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)

        title_box = QVBoxLayout()
        lbl_title = QLabel("⚡ ESP32 Studio")
        lbl_title.setObjectName("brandTitle")
        lbl_sub = QLabel("Multi-Board Firmware Flasher, LoRa Live Packet Inspector & Serial Monitor")
        lbl_sub.setObjectName("brandSubtitle")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        btn_refresh_ports = QPushButton("🔄 Refresh USB Ports")
        btn_refresh_ports.clicked.connect(self._refresh_ports)
        header_layout.addWidget(btn_refresh_ports)

        main_layout.addWidget(header)

        # ── Main Tabs ──
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, 1)

        # Build tabs
        self.tab_flasher = self._create_flasher_tab()
        self.tab_monitor = self._create_monitor_tab()
        self.tab_inspector = self._create_inspector_tab()
        self.tab_config = self._create_config_tab()
        self.tab_pio = self._create_pio_tab()

        self.tabs.addTab(self.tab_flasher, "⚡ ESP32 Flasher (Kod Urish)")
        self.tabs.addTab(self.tab_monitor, "📺 Dual Serial Monitor")
        self.tabs.addTab(self.tab_inspector, "📡 LoRa Live Inspector")
        self.tabs.addTab(self.tab_config, "⚙️ Quick NVS Configurator")
        self.tabs.addTab(self.tab_pio, "🛠️ PlatformIO Builder")

        # Status Bar
        self.lbl_status = QLabel("⚡ Tayyor")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-weight: 600; padding: 4px 8px;")
        self.statusBar().addWidget(self.lbl_status)

    # ── Tab 1: ESP32 Flasher ──
    def _create_flasher_tab(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Sol taraf: Konfiguratsiya kartasi
        left_card = QFrame()
        left_card.setObjectName("card")
        left_card.setMaximumWidth(440)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        left_layout.addWidget(self._section_title("🎯 Maqsadli ESP32 Qurilmasi"))

        # Port Tanlash
        left_layout.addWidget(QLabel("USB Serial Port:"))
        port_row = QHBoxLayout()
        self.combo_ports = QComboBox()
        port_row.addWidget(self.combo_ports, 1)
        btn_chip_info = QPushButton("🔍 Chip Info")
        btn_chip_info.clicked.connect(self._on_check_chip_info)
        port_row.addWidget(btn_chip_info)
        left_layout.addLayout(port_row)

        # Presetlar (Gateway / Meter / Sensor)
        left_layout.addWidget(self._section_title("📦 Firmware Manbai"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItem("📡 LoRa Gateway (WiFi + Display) [/dev/cu.usbserial-10]", "lora_gateway")
        self.combo_preset.addItem("⚡ LoRa Electric Meter Node (TE71/TE73 RS-485) [/dev/cu.usbserial-110]", "electricity_lora")
        self.combo_preset.addItem("🌱 Tuproq / Suv / Gaz Sensor Node", "soil_lora")
        self.combo_preset.addItem("📂 Fayldan tanlash (.bin)", "custom")
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        left_layout.addWidget(self.combo_preset)

        # File Chooser (Custom .bin)
        self.file_row_widget = QWidget()
        file_row = QHBoxLayout(self.file_row_widget)
        file_row.setContentsMargins(0, 0, 0, 0)
        self.edit_bin_path = QLineEdit()
        self.edit_bin_path.setPlaceholderText("Firmware .bin fayl yo'li...")
        btn_browse = QPushButton("📁 Browse")
        btn_browse.clicked.connect(self._on_browse_bin)
        file_row.addWidget(self.edit_bin_path, 1)
        file_row.addWidget(btn_browse)
        self.file_row_widget.setVisible(False)
        left_layout.addWidget(self.file_row_widget)

        # Advanced Settings
        left_layout.addWidget(self._section_title("⚙️ Flashing Sozlamalari"))

        left_layout.addWidget(QLabel("Baud Rate:"))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["460800 (Tavsiya etiladi)", "921600 (Juda tez)", "115200 (Standart)", "230400"])
        left_layout.addWidget(self.combo_baud)

        left_layout.addWidget(QLabel("Flash Address Offset:"))
        self.edit_offset = QLineEdit("0x10000")
        left_layout.addWidget(self.edit_offset)

        self.chk_erase = QCheckBox("Yuklashdan oldin xotirani to'liq tozalash (Erase Flash)")
        left_layout.addWidget(self.chk_erase)

        left_layout.addStretch()

        # Action Buttons
        self.btn_flash = QPushButton("⚡ FLASH FIRMWARE TO ESP32")
        self.btn_flash.setObjectName("btnPrimary")
        self.btn_flash.setMinimumHeight(44)
        self.btn_flash.clicked.connect(self._on_start_flash)
        left_layout.addWidget(self.btn_flash)

        self.btn_erase_only = QPushButton("🗑️ Erase Flash Only")
        self.btn_erase_only.setObjectName("btnDanger")
        self.btn_erase_only.clicked.connect(self._on_erase_flash_only)
        left_layout.addWidget(self.btn_erase_only)

        layout.addWidget(left_card)

        # O'ng taraf: Terminal & Progress Bar
        right_card = QFrame()
        right_card.setObjectName("card")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)

        right_layout.addWidget(self._section_title("🖥️ Flashing Terminal Log"))

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        right_layout.addWidget(self.progress_bar)

        self.term_flash = QTextEdit()
        self.term_flash.setObjectName("terminalOutput")
        self.term_flash.setReadOnly(True)
        right_layout.addWidget(self.term_flash, 1)

        layout.addWidget(right_card, 1)

        return widget

    # ── Tab 2: Dual Serial Monitor ──
    def _create_monitor_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Port 1 Monitor Card (Gateway)
        self.mon1_widget = self._create_single_monitor_box("📡 Gateway Port (/dev/cu.usbserial-10)", 0)
        splitter.addWidget(self.mon1_widget)

        # Port 2 Monitor Card (Meter Node)
        self.mon2_widget = self._create_single_monitor_box("⚡ Meter Node Port (/dev/cu.usbserial-110)", 1)
        splitter.addWidget(self.mon2_widget)

        layout.addWidget(splitter, 1)
        return widget

    def _create_single_monitor_box(self, default_title: str, idx: int) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        lbl_title = QLabel(default_title)
        lbl_title.setObjectName("sectionTitle")
        layout.addWidget(lbl_title)

        # Control row
        ctrl_row = QHBoxLayout()
        combo_port = QComboBox()

        combo_baud = QComboBox()
        combo_baud.addItems(["115200", "9600", "57600", "230400", "460800"])

        btn_conn = QPushButton("🔌 Start")
        btn_conn.setObjectName("btnSuccess")

        btn_clear = QPushButton("🧹 Clear")
        btn_save = QPushButton("💾 Save")

        ctrl_row.addWidget(combo_port, 1)
        ctrl_row.addWidget(combo_baud)
        ctrl_row.addWidget(btn_conn)
        ctrl_row.addWidget(btn_clear)
        ctrl_row.addWidget(btn_save)
        layout.addLayout(ctrl_row)

        # Terminal
        term = QTextEdit()
        term.setObjectName("terminalOutput")
        term.setReadOnly(True)
        layout.addWidget(term, 1)

        # Command input row
        cmd_row = QHBoxLayout()
        edit_cmd = QLineEdit()
        edit_cmd.setPlaceholderText("Send command (e.g. AT, reset, STATUS)...")
        btn_send = QPushButton("Send")

        cmd_row.addWidget(edit_cmd, 1)
        cmd_row.addWidget(btn_send)
        layout.addLayout(cmd_row)

        # Store references
        setattr(self, f"mon_port_combo_{idx}", combo_port)
        setattr(self, f"mon_baud_combo_{idx}", combo_baud)
        setattr(self, f"mon_btn_conn_{idx}", btn_conn)
        setattr(self, f"mon_term_{idx}", term)
        setattr(self, f"mon_cmd_{idx}", edit_cmd)
        setattr(self, f"mon_btn_send_{idx}", btn_send)

        btn_conn.clicked.connect(lambda: self._toggle_monitor(idx))
        btn_clear.clicked.connect(term.clear)
        btn_save.clicked.connect(lambda: self._save_log_file(term))
        btn_send.clicked.connect(lambda: self._send_monitor_cmd(idx))
        edit_cmd.returnPressed.connect(lambda: self._send_monitor_cmd(idx))

        return card

    # ── Tab 3: LoRa Live Inspector ──
    def _create_inspector_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Live Metric Cards Row
        cards_row = QHBoxLayout()

        self.lbl_card_meter = self._create_metric_card("📌 METER SERIAL", "N/A", cards_row)
        self.lbl_card_v = self._create_metric_card("⚡ VOLTAGE L1", "0.0 V", cards_row)
        self.lbl_card_i = self._create_metric_card("🔌 CURRENT L1", "0.0 A", cards_row)
        self.lbl_card_p = self._create_metric_card("💡 POWER", "0.0 kW", cards_row)
        self.lbl_card_e = self._create_metric_card("📊 ENERGY", "0.00 kWh", cards_row)
        self.lbl_card_rssi = self._create_metric_card("📡 LORA RSSI / SNR", "N/A", cards_row)

        layout.addLayout(cards_row)

        # History Table
        lbl_tbl = QLabel("📋 Recevied LoRa Packet Log History")
        lbl_tbl.setObjectName("sectionTitle")
        layout.addWidget(lbl_tbl)

        self.table_lora = QTableWidget(0, 9)
        self.table_lora.setHorizontalHeaderLabels([
            "Time", "Type", "Meter Serial", "Voltage (V)", "Current (A)", "Power (kW)", "Energy (kWh)", "RSSI / SNR", "CRC Status"
        ])
        self.table_lora.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_lora, 1)

        return widget

    def _create_metric_card(self, title: str, default_val: str, parent_layout: QHBoxLayout) -> QLabel:
        card = QFrame()
        card.setObjectName("card")
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 10, 12, 10)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #64748b; font-weight: 700; font-size: 11px;")
        lbl_v = QLabel(default_val)
        lbl_v.setStyleSheet("color: #38bdf8; font-weight: 900; font-size: 18px;")
        l.addWidget(lbl_t)
        l.addWidget(lbl_v)
        parent_layout.addWidget(card, 1)
        return lbl_v

    # ── Tab 4: Quick NVS Configurator ──
    def _create_config_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(14)

        card_layout.addWidget(self._section_title("⚙️ ESP32 EEPROM / NVS WiFi & Server Konfiguratori"))
        lbl_info = QLabel("ESP32 ga qayta firmware urmasdan, serial port orqali WiFi va Server sozlamalarini yozish va yangilash.")
        lbl_info.setStyleSheet("color: #94a3b8;")
        card_layout.addWidget(lbl_info)

        grid = QVBoxLayout()

        grid.addWidget(QLabel("Target Serial Port:"))
        self.combo_cfg_port = QComboBox()
        grid.addWidget(self.combo_cfg_port)

        grid.addWidget(QLabel("WiFi SSID:"))
        self.edit_cfg_ssid = QLineEdit("12")
        grid.addWidget(self.edit_cfg_ssid)

        grid.addWidget(QLabel("WiFi Password:"))
        self.edit_cfg_pass = QLineEdit("12345678")
        grid.addWidget(self.edit_cfg_pass)

        grid.addWidget(QLabel("Backend Server URL:"))
        self.edit_cfg_url = QLineEdit("https://ss.boos.uz")
        grid.addWidget(self.edit_cfg_url)

        grid.addWidget(QLabel("Device Token:"))
        self.edit_cfg_token = QLineEdit("T30gwzZJ6YTvQeLRMCZyTi-GBAYogsQV")
        grid.addWidget(self.edit_cfg_token)

        card_layout.addLayout(grid)

        row_btn = QHBoxLayout()
        btn_write = QPushButton("💾 Write Config to ESP32 Serial")
        btn_write.setObjectName("btnPrimary")
        btn_write.clicked.connect(self._on_write_nvs_config)

        btn_reboot = QPushButton("🔄 Soft Reboot ESP32")
        btn_reboot.clicked.connect(self._on_reboot_esp32)

        row_btn.addWidget(btn_write)
        row_btn.addWidget(btn_reboot)
        card_layout.addLayout(row_btn)

        card_layout.addStretch()
        layout.addWidget(card)
        return widget

    # ── Tab 5: PlatformIO Builder ──
    def _create_pio_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)

        card_layout.addWidget(self._section_title("🛠️ PlatformIO Environment Builder"))

        lbl_pio = QLabel(f"PlatformIO CLI Path: {self.controller.pio_path or 'Topilmadi (Install PlatformIO)'}")
        lbl_pio.setStyleSheet("color: #38bdf8; font-weight: 600;")
        card_layout.addWidget(lbl_pio)

        row_envs = QHBoxLayout()
        row_envs.addWidget(QLabel("Environment:"))
        self.combo_pio_env = QComboBox()
        self.combo_pio_env.addItems([
            "lora_gateway", "lora_gateway_debug",
            "electricity", "electricity_debug", "electricity_test",
            "soil_lora", "soil_wifi_lcd", "sound_wifi"
        ])
        row_envs.addWidget(self.combo_pio_env, 1)

        btn_build = QPushButton("🔨 Build Only")
        btn_build.clicked.connect(self._on_pio_build)
        row_envs.addWidget(btn_build)

        card_layout.addLayout(row_envs)

        self.term_pio = QTextEdit()
        self.term_pio.setObjectName("terminalOutput")
        self.term_pio.setReadOnly(True)
        card_layout.addWidget(self.term_pio, 1)

        layout.addWidget(card)
        return widget

    # ── Helpers & Event Handlers ──
    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionTitle")
        return lbl

    def _refresh_ports(self):
        ports = EsptoolService.list_serial_ports()
        self.combo_ports.clear()
        self.mon_port_combo_0.clear()
        self.mon_port_combo_1.clear()
        self.combo_cfg_port.clear()

        if not ports:
            for combo in [self.combo_ports, self.mon_port_combo_0, self.mon_port_combo_1, self.combo_cfg_port]:
                combo.addItem("Port topilmadi", "")
            return

        for p in ports:
            display = p["display_name"]
            dev = p["device"]
            for combo in [self.combo_ports, self.mon_port_combo_0, self.mon_port_combo_1, self.combo_cfg_port]:
                combo.addItem(display, dev)

        # Auto-select user requested ports
        for i in range(self.combo_ports.count()):
            val = self.combo_ports.itemData(i)
            if "usbserial-10" in val or "COM10" in val:
                self.mon_port_combo_0.setCurrentIndex(i)
            elif "usbserial-110" in val or "COM110" in val:
                self.mon_port_combo_1.setCurrentIndex(i)

        self.lbl_status.setText(f"Ports refresh qilindi: {len(ports)} ta port topildi.")

    def _on_preset_changed(self, idx: int):
        data = self.combo_preset.itemData(idx)
        self.file_row_widget.setVisible(data == "custom")

    def _on_browse_bin(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Firmware Binary Tanlang", "", "Binary Files (*.bin);;All Files (*)")
        if file_path:
            self.edit_bin_path.setText(file_path)

    def _on_check_chip_info(self):
        port = self.combo_ports.currentData()
        if not port:
            QMessageBox.warning(self, "Xato", "Iltimos, USB portni tanlang!")
            return

        self.term_flash.append(f"\n🔍 Chip diagnostikasi tekshirilmoqda ({port})...\n")
        self.controller.fetch_chip_info(port, 115200, self._on_chip_info_received)

    def _on_chip_info_received(self, info: dict):
        if info.get("success"):
            self.term_flash.append(f"✅ Chip Aniqlandi: {info.get('chip_type')}")
            self.term_flash.append(f"📌 MAC Manzil: {info.get('mac')}")
            if "flash_size" in info:
                self.term_flash.append(f"💾 Flash Hajmi: {info.get('flash_size')}")
        else:
            self.term_flash.append(f"⚠️ Chip diagnostika ma'lumoti:\n{info.get('raw')}")

    def _on_start_flash(self):
        port = self.combo_ports.currentData()
        if not port:
            QMessageBox.warning(self, "Xato", "Iltimos, USB Serial portni tanlang!")
            return

        preset = self.combo_preset.currentData()
        bin_path = ""

        if preset == "custom":
            bin_path = self.edit_bin_path.text().strip()
        else:
            root = self.controller.project_root
            if root:
                bin_path = FlashService.find_compiled_bin(root, preset)

        if not bin_path or not os.path.exists(bin_path):
            QMessageBox.warning(
                self, "Firmware Topilmadi",
                f"Tanlangan preset firmware.bin fayli topilmadi.\n"
                f"Iltimos, avval PlatformIO tabida build qiling yoki 'Custom .bin' orqali faylni ko'rsating.\n\nYo'l: {bin_path}"
            )
            return

        baud_raw = self.combo_baud.currentText().split()[0]
        baud = int(baud_raw)
        offset = self.edit_offset.text().strip() or "0x10000"
        erase_first = self.chk_erase.isChecked()

        self.term_flash.clear()
        self.progress_bar.setValue(0)
        self.btn_flash.setEnabled(False)

        ok, msg = self.controller.start_direct_flash(
            port=port,
            bin_path=bin_path,
            offset=offset,
            baud=baud,
            erase_first=erase_first,
            log_cb=self._on_flash_log,
            prog_cb=self.progress_bar.setValue,
            finish_cb=self._on_flash_finished
        )

        if not ok:
            QMessageBox.warning(self, "Xato", msg)
            self.btn_flash.setEnabled(True)

    def _on_flash_log(self, text: str, color: str):
        self.term_flash.append(f'<span style="color:{color};">{text}</span>')
        self.term_flash.moveCursor(QTextCursor.MoveOperation.End)

    def _on_flash_finished(self, success: bool, msg: str):
        self.btn_flash.setEnabled(True)
        if success:
            QMessageBox.information(self, "Muvaffaqiyat", msg)
        else:
            QMessageBox.critical(self, "Flashing Xatosi", msg)

    def _on_erase_flash_only(self):
        port = self.combo_ports.currentData()
        if not port:
            return
        reply = QMessageBox.question(
            self, "Tasdiqlang",
            f"{port} mikrokontrollerining flash xotirasi tozalanadi. Davom etasizmi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.term_flash.append(f"🗑️ Flash tozalash boshlandi ({port})...")
            proc = EsptoolService.erase_flash(port)
            out, err = proc.communicate()
            self.term_flash.append(out)

    # ── Serial Monitor & LoRa Inspector Integration ──
    def _toggle_monitor(self, idx: int):
        combo_p = getattr(self, f"mon_port_combo_{idx}")
        combo_b = getattr(self, f"mon_baud_combo_{idx}")
        btn_c = getattr(self, f"mon_btn_conn_{idx}")
        term = getattr(self, f"mon_term_{idx}")

        port = combo_p.currentData()
        if not port:
            return

        if idx in self._serial_workers and self._serial_workers[idx].isRunning():
            self.controller.stop_serial_monitor(port)
            self._serial_workers.pop(idx, None)
            btn_c.setText("🔌 Start")
            btn_c.setObjectName("btnSuccess")
            btn_c.setStyleSheet("")
            term.append(f"\n[SYSTEM] Serial Monitor to'xtatildi ({port})\n")
        else:
            baud = int(combo_b.currentText())
            term.append(f"\n[SYSTEM] Ulanmoqda: {port} @ {baud} baud...\n")

            def _on_data(p, line):
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                term.append(f'<span style="color:#64748b;">[{ts}]</span> {line}')
                term.moveCursor(QTextCursor.MoveOperation.End)

                # Live LoRa Packet Inspector parsing
                decoded_info = LoRaPacketDecoder.parse_serial_log_line(line)
                if decoded_info:
                    self._update_inspector_ui(decoded_info)

            def _on_status(p, connected, status_msg):
                term.append(f'<span style="color:#38bdf8;">[STATUS] {status_msg}</span>')

            worker = self.controller.start_serial_monitor(port, baud, _on_data, _on_status)
            self._serial_workers[idx] = worker
            btn_c.setText("⏹ Stop")
            btn_c.setObjectName("btnDanger")

    def _update_inspector_ui(self, info: dict):
        rssi_text = f"{info.get('rssi', 'N/A')} dBm / {info.get('snr', 'N/A')} dB" if "rssi" in info else "N/A"
        if "rssi" in info:
            self.lbl_card_rssi.setText(rssi_text)

        pkt = info.get("packet")
        if not pkt:
            return

        if pkt.get("type") == "ELECTRICITY_UPLINK":
            serial_no = pkt.get("meter_serial", "N/A")
            v_l1 = pkt["voltage_v"]["l1"]
            i_l1 = pkt["current_a"]["l1"]
            power_kw = pkt.get("power_kw", 0.0)
            energy_kwh = pkt.get("energy_kwh", 0.0)

            self.lbl_card_meter.setText(serial_no)
            self.lbl_card_v.setText(f"{v_l1:.1f} V")
            self.lbl_card_i.setText(f"{i_l1:.2f} A")
            self.lbl_card_p.setText(f"{power_kw:.3f} kW")
            self.lbl_card_e.setText(f"{energy_kwh:.2f} kWh")

            row_idx = self.table_lora.rowCount()
            self.table_lora.insertRow(row_idx)
            ts = datetime.now().strftime("%H:%M:%S")

            self.table_lora.setItem(row_idx, 0, QTableWidgetItem(ts))
            self.table_lora.setItem(row_idx, 1, QTableWidgetItem("ELECTRICITY"))
            self.table_lora.setItem(row_idx, 2, QTableWidgetItem(serial_no))
            self.table_lora.setItem(row_idx, 3, QTableWidgetItem(f"{v_l1:.1f} V"))
            self.table_lora.setItem(row_idx, 4, QTableWidgetItem(f"{i_l1:.2f} A"))
            self.table_lora.setItem(row_idx, 5, QTableWidgetItem(f"{power_kw:.3f} kW"))
            self.table_lora.setItem(row_idx, 6, QTableWidgetItem(f"{energy_kwh:.2f} kWh"))
            self.table_lora.setItem(row_idx, 7, QTableWidgetItem(rssi_text))
            self.table_lora.setItem(row_idx, 8, QTableWidgetItem("✅ OK" if pkt.get("valid_crc") else "❌ CRC ERROR"))

    def _send_monitor_cmd(self, idx: int):
        edit = getattr(self, f"mon_cmd_{idx}")
        cmd = edit.text().strip()
        if cmd and idx in self._serial_workers:
            self._serial_workers[idx].send_command(cmd)
            term = getattr(self, f"mon_term_{idx}")
            term.append(f'<span style="color:#f59e0b;">&gt;&gt;&gt; {cmd}</span>')
            edit.clear()

    def _save_log_file(self, term_widget: QTextEdit):
        text = term_widget.toPlainText()
        if not text:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Log Faylini Saqlash", "serial_log.txt", "Text Files (*.txt);;Log Files (*.log)")
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, "Saqlandi", f"Log saqlandi: {file_path}")

    # ── NVS Config Handler ──
    def _on_write_nvs_config(self):
        port = self.combo_cfg_port.currentData()
        if not port:
            return
        ssid = self.edit_cfg_ssid.text().strip()
        pwd = self.edit_cfg_pass.text().strip()
        url = self.edit_cfg_url.text().strip()
        tok = self.edit_cfg_token.text().strip()

        cmd = f"SET_CONFIG {ssid} {pwd} {url} {tok}"
        if port in self._serial_workers:
            self._serial_workers[port].send_command(cmd)
            QMessageBox.information(self, "Yuborildi", f"Konfiguratsiya serial portga yuborildi: {cmd}")

    def _on_reboot_esp32(self):
        port = self.combo_cfg_port.currentData()
        if port in self._serial_workers:
            self._serial_workers[port].send_command("REBOOT")
            QMessageBox.information(self, "Yuborildi", "ESP32 ga REBOOT buyrug'i yuborildi.")

    # ── PlatformIO Builder ──
    def _on_pio_build(self):
        env_name = self.combo_pio_env.currentText()
        if not self.controller.pio_path or not self.controller.project_root:
            QMessageBox.warning(self, "Xato", "PlatformIO CLI yoki platformio.ini topilmadi!")
            return

        self.term_pio.clear()
        self.term_pio.append(f"🔨 Building PlatformIO environment: {env_name}...\n")

        cmd = [self.controller.pio_path, "run", "-e", env_name]
        self.term_pio.append(f"▶ {' '.join(cmd)}\n")

        import subprocess
        proc = subprocess.Popen(
            cmd, cwd=self.controller.project_root,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in iter(proc.stdout.readline, ''):
            self.term_pio.append(line.strip())
            self.term_pio.moveCursor(QTextCursor.MoveOperation.End)
        proc.stdout.close()
        proc.wait()
        self.term_pio.append("\n✅ Build tugatildi!")
