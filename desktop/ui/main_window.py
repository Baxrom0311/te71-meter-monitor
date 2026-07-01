"""Main window — sidebar navigation + content panels."""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QStackedWidget, QFrame,
                              QMessageBox, QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from .dashboard import DashboardPanel
from .relay_panel import RelayPanel
from .registers_panel import RegistersPanel
from .settings_panel import SettingsPanel
from .log_panel import LogPanel


class MeterWorker(QThread):
    """Background thread for serial communication."""
    finished = pyqtSignal(str, object)
    error = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.meter = None
        self._action = None
        self._args = ()

    def run_action(self, action: str, *args):
        self._action = action
        self._args = args
        self.start()

    def run(self):
        if not self.meter:
            self.error.emit(self._action, "Meter not initialized")
            return
        try:
            if self._action == "read_info":
                info = self.meter.read_info()
                self.meter.read_scalers()
                self.finished.emit("read_info", info)
            elif self._action == "read_dashboard":
                data = self.meter.read_dashboard()
                self.finished.emit("read_dashboard", data)
            elif self._action == "read_all_registers":
                data = self.meter.read_all_registers()
                self.finished.emit("read_all_registers", data)
            elif self._action == "read_relay":
                status = self.meter.read_relay_status()
                self.finished.emit("read_relay", status)
            elif self._action == "relay_reconnect":
                ok = self.meter.relay_reconnect()
                if ok:
                    self.msleep(1500)
                status = self.meter.read_relay_status()
                self.finished.emit("relay_reconnect", (ok, status))
            elif self._action == "relay_disconnect":
                ok = self.meter.relay_disconnect()
                if ok:
                    self.msleep(1500)
                status = self.meter.read_relay_status()
                self.finished.emit("relay_disconnect", (ok, status))
            elif self._action == "read_time":
                dt = self.meter.read_datetime()
                self.finished.emit("read_time", dt)
            elif self._action == "sync_time":
                ok = self.meter.set_datetime()
                dt = self.meter.read_datetime() if ok else None
                self.finished.emit("sync_time", (ok, dt))
            elif self._action == "change_password":
                new_pwd = self._args[0]
                ok = self.meter.change_password(new_pwd)
                self.finished.emit("change_password", ok)
            elif self._action == "set_relay_mode":
                mode = self._args[0]
                ok = self.meter.set_relay_mode(mode)
                if ok:
                    self.msleep(1000)
                status = self.meter.read_relay_status()
                self.finished.emit("set_relay_mode", (ok, status))
            elif self._action == "read_custom":
                class_id, obis_tuple = self._args
                from dlms.parser import parse_dlms_data, format_value
                raw = self.meter.conn.get_attribute(class_id, obis_tuple, 2)
                if raw:
                    val, _, _ = parse_dlms_data(raw)
                    self.finished.emit("read_custom", format_value(val))
                else:
                    self.finished.emit("read_custom", "N/A")
        except Exception as e:
            self.error.emit(self._action, str(e))


class NavButton(QPushButton):
    """Sidebar navigation button."""

    def __init__(self, icon: str, text: str, index: int):
        display_text = f"{icon}  {text}" if icon else text
        super().__init__(display_text)
        self.index = index
        self.setObjectName("navButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class MainWindow(QMainWindow):
    """Main application window with sidebar navigation."""

    def __init__(self, conn, meter, settings: dict):
        super().__init__()
        self.conn = conn
        self.meter = meter
        self.settings = settings

        self.setWindowTitle("Elektr nazorat — TE71/TE73")
        self.setMinimumSize(1040, 680)
        self.resize(1180, 760)

        self.worker = MeterWorker()
        self.worker.meter = meter
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)

        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self._auto_refresh)

        self.nav_buttons: list[NavButton] = []
        self._pending_actions: list[tuple[str, tuple]] = []

        self._setup_ui()

        # Auto-read info on start
        QTimer.singleShot(200, lambda: self._run_worker("read_info"))

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== SIDEBAR =====
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(235)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        # Logo area
        logo_frame = QWidget()
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(20, 20, 20, 16)
        logo_layout.setSpacing(4)

        logo = QLabel("Elektr nazorat")
        logo.setObjectName("brand")
        logo_layout.addWidget(logo)

        subtitle = QLabel("TE71 / TE73")
        subtitle.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 700;")
        logo_layout.addWidget(subtitle)

        self.lbl_meter_type = QLabel("Hisoblagich aniqlanmoqda")
        self.lbl_meter_type.setStyleSheet("font-size: 12px; color: #94a3b8;")
        logo_layout.addWidget(self.lbl_meter_type)

        sb_layout.addWidget(logo_frame)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #24364f;")
        sb_layout.addWidget(sep)

        # Nav buttons
        nav_items = [
            ("📊", "Ko'rsatkichlar"),
            ("🔌", "Rele"),
            ("📋", "Registrlar"),
            ("⚙️", "Sozlamalar"),
            ("📝", "Log"),
        ]
        for i, (icon, text) in enumerate(nav_items):
            btn = NavButton(icon, text, i)
            btn.clicked.connect(lambda checked, idx=i: self._nav_to(idx))
            self.nav_buttons.append(btn)
            sb_layout.addWidget(btn)

        sb_layout.addStretch()

        # Connection info
        conn_frame = QWidget()
        conn_layout = QVBoxLayout(conn_frame)
        conn_layout.setContentsMargins(20, 12, 20, 12)
        conn_layout.setSpacing(2)

        self.lbl_port = QLabel(f"Port: {self.settings.get('port', '')}")
        self.lbl_port.setStyleSheet("font-size: 12px; color: #94a3b8;")
        conn_layout.addWidget(self.lbl_port)

        self.lbl_serial = QLabel("")
        self.lbl_serial.setStyleSheet("font-size: 12px; color: #94a3b8;")
        conn_layout.addWidget(self.lbl_serial)

        # Status dot
        self.lbl_status = QLabel("Status: ulangan")
        self.lbl_status.setStyleSheet("font-size: 12px; color: #86efac; font-weight: 700;")
        conn_layout.addWidget(self.lbl_status)

        sb_layout.addWidget(conn_frame)

        # Disconnect button
        btn_disc = QPushButton("Uzish")
        btn_disc.setObjectName("sidebarDanger")
        btn_disc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_disc.clicked.connect(self._disconnect)
        btn_wrap = QWidget()
        btn_wrap_layout = QVBoxLayout(btn_wrap)
        btn_wrap_layout.setContentsMargins(16, 8, 16, 16)
        btn_wrap_layout.addWidget(btn_disc)
        sb_layout.addWidget(btn_wrap)

        main_layout.addWidget(sidebar)

        # ===== CONTENT AREA =====
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(26, 22, 26, 14)
        content_layout.setSpacing(12)

        # Page header
        header = QFrame()
        header.setObjectName("headerCard")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(18)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        self.lbl_page_title = QLabel("Ko'rsatkichlar")
        self.lbl_page_title.setObjectName("page_title")
        title_box.addWidget(self.lbl_page_title)

        self.lbl_page_subtitle = QLabel("Hozirgi ko'rsatkichlar")
        self.lbl_page_subtitle.setObjectName("page_subtitle")
        title_box.addWidget(self.lbl_page_subtitle)
        header_layout.addLayout(title_box, 1)

        self.header_port_value = self._header_info(header_layout, "PORT", self.settings.get("port", ""))
        self.header_serial_value = self._header_info(header_layout, "SERIAL", "---")
        self.header_status = QLabel("Ulangan")
        self.header_status.setObjectName("statusChipOk")
        header_layout.addWidget(self.header_status)

        self.btn_header_refresh = QPushButton("Yangilash")
        self.btn_header_refresh.setObjectName("primary")
        self.btn_header_refresh.clicked.connect(self._refresh_current_page)
        header_layout.addWidget(self.btn_header_refresh)

        # Auto-refresh controls
        from PyQt6.QtWidgets import QCheckBox, QComboBox
        self.chk_auto_refresh = QCheckBox("Avtomatik")
        self.chk_auto_refresh.setChecked(True)
        self.chk_auto_refresh.toggled.connect(self._on_auto_refresh_toggled)
        header_layout.addWidget(self.chk_auto_refresh)

        self.combo_refresh_interval = QComboBox()
        self.combo_refresh_interval.addItems(["3s", "5s", "10s", "30s"])
        self.combo_refresh_interval.setCurrentIndex(0)
        self.combo_refresh_interval.currentIndexChanged.connect(self._on_refresh_interval_changed)
        header_layout.addWidget(self.combo_refresh_interval)

        content_layout.addWidget(header)

        # Stacked pages
        self.pages = QStackedWidget()

        self.dashboard = DashboardPanel()
        self.pages.addWidget(self._scroll_page(self.dashboard))

        self.relay_panel = RelayPanel()
        self.pages.addWidget(self._scroll_page(self.relay_panel))

        self.registers_panel = RegistersPanel()
        self.pages.addWidget(self.registers_panel)

        self.settings_panel = SettingsPanel()
        self.pages.addWidget(self._scroll_page(self.settings_panel))

        self.log_panel = LogPanel()
        self.pages.addWidget(self.log_panel)

        content_layout.addWidget(self.pages)

        # Bottom status bar
        self.lbl_bottom_status = QLabel("Tayyor")
        self.lbl_bottom_status.setStyleSheet("font-size: 12px; color: #667085; padding-top: 4px;")
        content_layout.addWidget(self.lbl_bottom_status)

        main_layout.addWidget(content, 1)

        # Set initial nav
        self._nav_to(0)

        # Connect signals
        self.relay_panel.btn_reconnect.clicked.connect(self._relay_reconnect)
        self.relay_panel.btn_disconnect.clicked.connect(self._relay_disconnect)
        self.relay_panel.btn_refresh.clicked.connect(self._read_relay)
        self.relay_panel.btn_set_mode.clicked.connect(self._set_relay_mode)
        self.registers_panel.btn_read_all.clicked.connect(self._read_all_registers)
        self.registers_panel.btn_read_custom.clicked.connect(self._read_custom)
        self.settings_panel.btn_read_info.clicked.connect(self._read_info)
        self.settings_panel.btn_read_time.clicked.connect(self._read_time)
        self.settings_panel.btn_sync_time.clicked.connect(self._sync_time)
        self.settings_panel.btn_set_pwd.clicked.connect(self._change_password)

        # Enable panels
        self.relay_panel.set_enabled(True)
        self.registers_panel.set_enabled(True)
        self.settings_panel.set_enabled(True)

        # Set log callbacks
        self.conn.set_callbacks(
            on_tx=self.log_panel.add_tx,
            on_rx=self.log_panel.add_rx,
            on_log=self.log_panel.add_app_log,
        )
        self.meter.set_log_callback(self.log_panel.add_app_log)

    def _scroll_page(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(widget)
        return scroll

    def _header_info(self, parent_layout: QHBoxLayout, label: str, value: str) -> QLabel:
        box = QVBoxLayout()
        box.setSpacing(2)
        lbl = QLabel(label)
        lbl.setObjectName("smallLabel")
        box.addWidget(lbl)
        val = QLabel(value or "---")
        val.setObjectName("smallValue")
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(val)
        parent_layout.addLayout(box)
        return val

    def _nav_to(self, index: int):
        self.pages.setCurrentIndex(index)

        for btn in self.nav_buttons:
            btn.setChecked(btn.index == index)

        titles = [
            ("Ko'rsatkichlar", "Asosiy elektr ko'rsatkichlari va energiya sarfi"),
            ("Rele", "Yuklama relesi holati va boshqaruvi"),
            ("Registrlar", "Barcha OBIS kod registrlari"),
            ("Sozlamalar", "Hisoblagich ma'lumotlari va vaqt sinxronizatsiya"),
            ("Kommunikatsiya Log", "HDLC TX/RX freymlar va dastur xabarlari"),
        ]
        title, subtitle = titles[index]
        self.lbl_page_title.setText(title)
        self.lbl_page_subtitle.setText(subtitle)

        refresh_labels = ["Ko'rsatkichlarni yangilash", "Holatni yangilash", "Registrlarni o'qish", "Ma'lumotlarni yangilash", "Log"]
        self.btn_header_refresh.setText(refresh_labels[index])
        self.btn_header_refresh.setEnabled(index != 4)

        # Show auto-refresh controls only on Dashboard page
        self.chk_auto_refresh.setVisible(index == 0)
        self.combo_refresh_interval.setVisible(index == 0)

    def _run_worker(self, action: str, *args):
        if self.worker.isRunning():
            if not any(item[0] == action for item in self._pending_actions):
                self._pending_actions.append((action, args))
                self.lbl_bottom_status.setText(f"Navbatda: {action}")
                self.lbl_bottom_status.setStyleSheet("font-size: 12px; color: #667085; padding-top: 4px;")
            return
        self.lbl_bottom_status.setText(f"Ishlayapti: {action}...")
        self.lbl_bottom_status.setStyleSheet("font-size: 12px; color: #1663d8; padding-top: 4px;")
        self.worker.run_action(action, *args)

    def _drain_worker_queue(self):
        if self.worker.isRunning() or not self._pending_actions:
            return
        action, args = self._pending_actions.pop(0)
        self._run_worker(action, *args)

    def _on_worker_finished(self, action: str, result):
        self.lbl_bottom_status.setText("Tayyor")
        self.lbl_bottom_status.setStyleSheet("font-size: 12px; color: #667085; padding-top: 4px;")

        if action == "read_info":
            info = result
            self.lbl_meter_type.setText(f"{info.meter_type}  |  S/N: {info.serial}")
            self.lbl_serial.setText(f"S/N: {info.serial}")
            self.header_serial_value.setText(info.serial or "---")
            self.settings_panel.update_info(
                info.serial, info.manufacturer, info.device_name,
                info.firmware, info.meter_type,
            )
            self.dashboard.set_3phase(info.meter_type == "TE73")
            self._pending_actions.append(("read_dashboard", ()))
            self._pending_actions.append(("read_relay", ()))

        elif action == "read_dashboard":
            self.dashboard.update_values(result)
            if self.conn and self.conn.connected and self.chk_auto_refresh.isChecked():
                self.auto_refresh_timer.start(self._get_refresh_interval_ms())

        elif action == "read_all_registers":
            self.registers_panel.populate(result)

        elif action == "read_relay":
            self.relay_panel.hide_loading()
            self.relay_panel.update_status(
                result.output_state, result.control_text, result.mode_text, result.control_mode
            )

        elif action in ("relay_reconnect", "relay_disconnect"):
            ok, status = result
            self.relay_panel.hide_loading()
            self.relay_panel.update_status(
                status.output_state, status.control_text, status.mode_text, status.control_mode
            )
            if ok:
                msg = "yoqildi" if action == "relay_reconnect" else "o'chirildi"
                self.log_panel.add_app_log(f"Rele {msg}!")
            else:
                QMessageBox.warning(self, "Xato", "Rele buyrug'i rad etildi!")

        elif action == "set_relay_mode":
            ok, status = result
            self.relay_panel.hide_loading()
            self.relay_panel.update_status(
                status.output_state, status.control_text, status.mode_text, status.control_mode
            )
            if ok:
                self.log_panel.add_app_log("Rele ish rejimi muvaffaqiyatli o'zgartirildi!")
                QMessageBox.information(self, "Muvaffaqiyat", "Rele rejimi o'zgartirildi!")
            else:
                QMessageBox.warning(self, "Xato", "Rele rejimini o'zgartirish rad etildi!")

        elif action == "read_time":
            self.settings_panel.update_time(result)

        elif action == "sync_time":
            ok, dt = result
            if ok:
                self.settings_panel.update_time(dt)
            else:
                QMessageBox.warning(self, "Xato", "Vaqt sinxronlash xatosi!")

        elif action == "change_password":
            if result:
                QMessageBox.information(self, "Muvaffaqiyat", "Parol muvaffaqiyatli o'zgartirildi!")
                self.settings_panel.pwd_input.clear()
            else:
                QMessageBox.warning(self, "Xato", "Parolni o'zgartirib bo'lmadi! Huquqlar yetarli ekanligini tekshiring.")

        elif action == "read_custom":
            obis_str = self.registers_panel.obis_input.text()
            class_id = int(self.registers_panel.class_input.text() or "3")
            self.registers_panel.add_custom_row(obis_str, class_id, str(result))

        QTimer.singleShot(80, self._drain_worker_queue)

    def _on_worker_error(self, action: str, error: str):
        self.lbl_bottom_status.setText(f"Xato: {error}")
        self.lbl_bottom_status.setStyleSheet("font-size: 12px; color: #cf2e2e; padding-top: 4px;")
        self.log_panel.add_app_log(f"XATO [{action}]: {error}")
        if action in ("read_relay", "relay_reconnect", "relay_disconnect", "set_relay_mode"):
            self.relay_panel.hide_loading()
        QTimer.singleShot(80, self._drain_worker_queue)

    def _auto_refresh(self):
        self.auto_refresh_timer.stop()
        if self.conn and self.conn.connected and not self.worker.isRunning():
            if self.pages.currentIndex() == 0 and self.chk_auto_refresh.isChecked():
                self._read_dashboard()

    def _get_refresh_interval_ms(self) -> int:
        txt = self.combo_refresh_interval.currentText()
        try:
            return int(txt.replace("s", "")) * 1000
        except ValueError:
            return 3000

    def _on_auto_refresh_toggled(self, checked: bool):
        if checked:
            if self.conn and self.conn.connected and not self.worker.isRunning() and self.pages.currentIndex() == 0:
                self._read_dashboard()
        else:
            self.auto_refresh_timer.stop()

    def _on_refresh_interval_changed(self):
        if self.chk_auto_refresh.isChecked() and self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()
            self.auto_refresh_timer.start(self._get_refresh_interval_ms())

    def _read_dashboard(self):
        self._run_worker("read_dashboard")

    def _read_info(self):
        self._run_worker("read_info")

    def _read_all_registers(self):
        self._run_worker("read_all_registers")

    def _read_relay(self):
        self.relay_panel.show_loading("read_relay")
        self._run_worker("read_relay")

    def _relay_reconnect(self):
        if self.relay_panel.confirm_action("YOQISH"):
            if self.conn and self.conn.client_addr != 1:
                self.log_panel.add_app_log("Rele uchun Client 1 ga o'tilmoqda...")
                self.conn.disconnect()
                if not self.conn.connect_reader():
                    QMessageBox.warning(self, "Xato", "Client 1 ga ulanish xatosi!")
                    return
            self.relay_panel.show_loading("relay_reconnect")
            self._run_worker("relay_reconnect")

    def _relay_disconnect(self):
        if self.relay_panel.confirm_action("O'CHIRISH"):
            if self.conn and self.conn.client_addr != 1:
                self.conn.disconnect()
                if not self.conn.connect_reader():
                    QMessageBox.warning(self, "Xato", "Client 1 ga ulanish xatosi!")
                    return
            self.relay_panel.show_loading("relay_disconnect")
            self._run_worker("relay_disconnect")

    def _read_time(self):
        self._run_worker("read_time")

    def _sync_time(self):
        if self.settings_panel.confirm_sync():
            self._run_worker("sync_time")

    def _change_password(self):
        new_pwd = self.settings_panel.pwd_input.text().strip()
        if not new_pwd:
            QMessageBox.warning(self, "Xato", "Parol bo'sh bo'lishi mumkin emas!")
            return
        if len(new_pwd) < 4 or len(new_pwd) > 16:
            QMessageBox.warning(self, "Xato", "Parol uzunligi 4-16 ta belgidan iborat bo'lishi kerak!")
            return
        
        reply = QMessageBox.question(
            self, "Tasdiqlash",
            f"Hisoblagich parolini '{new_pwd}' ga o'zgartirishni tasdiqlaysizmi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_worker("change_password", new_pwd)

    def _set_relay_mode(self):
        idx = self.relay_panel.combo_mode.currentIndex()
        reply = QMessageBox.question(
            self, "Tasdiqlash",
            f"Rele ish rejimini {idx} ga o'zgartirishni tasdiqlaysizmi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.conn and self.conn.client_addr != 1:
                self.log_panel.add_app_log("Rele rejimi uchun Client 1 ga o'tilmoqda...")
                self.conn.disconnect()
                if not self.conn.connect_reader():
                    QMessageBox.warning(self, "Xato", "Client 1 ga ulanish xatosi!")
                    return
            self.relay_panel.show_loading("set_relay_mode")
            self._run_worker("set_relay_mode", idx)

    def _read_custom(self):
        obis_str = self.registers_panel.obis_input.text().strip()
        if not obis_str:
            return
        parts = obis_str.split(".")
        if len(parts) != 6:
            QMessageBox.warning(self, "Xato", "OBIS format: A.B.C.D.E.F")
            return
        try:
            obis_tuple = tuple(int(p) for p in parts)
            class_id = int(self.registers_panel.class_input.text() or "3")
        except ValueError:
            return
        self._run_worker("read_custom", class_id, obis_tuple)

    def _refresh_current_page(self):
        index = self.pages.currentIndex()
        if index == 0:
            self._read_dashboard()
        elif index == 1:
            self._read_relay()
        elif index == 2:
            self._read_all_registers()
        elif index == 3:
            self._read_info()

    def _disconnect(self):
        self.auto_refresh_timer.stop()
        if self.worker.isRunning():
            self.worker.wait(3000)
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        self.close()

    def closeEvent(self, event):
        self.auto_refresh_timer.stop()
        if self.worker.isRunning():
            self.worker.wait(3000)
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        event.accept()
