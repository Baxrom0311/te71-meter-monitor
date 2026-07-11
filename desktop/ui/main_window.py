"""Main window — sidebar navigation + content panels.

Bu modul faqat UI layout va navigatsiyani boshqaradi.
Barcha serial aloqa va biznes logikasi MeterController orqali amalga oshiriladi.
"""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QStackedWidget, QFrame,
                              QMessageBox, QScrollArea, QCheckBox, QComboBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from controllers.meter_controller import MeterController
from ui.pages.dashboard_page import DashboardPanel
from ui.pages.relay_page import RelayPanel
from ui.pages.registers_page import RegistersPanel
from ui.pages.settings_page import SettingsPanel
from ui.pages.log_page import LogPanel


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
    """Main application window with sidebar navigation.

    UI fayllarini boshqaradi va MeterController signallariga ulanadi.
    Serial aloqa haqida hech narsa bilmaydi.
    """

    def __init__(self, controller: MeterController, settings: dict):
        super().__init__()
        self.controller = controller
        self.settings = settings

        self.setWindowTitle("Elektr nazorat - TE71/TE73")
        self.setMinimumSize(980, 620)
        self.resize(1240, 800)

        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self._auto_refresh)

        self.nav_buttons: list[NavButton] = []

        self._setup_ui()
        self._connect_controller_signals()

        # Auto-read info on start
        QTimer.singleShot(200, self.controller.read_info)

    # ── UI Setup ──────────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._build_sidebar(main_layout)
        self._build_content(main_layout)

        # Set initial nav
        self._nav_to(0)

        # Connect panel buttons to controller
        self._connect_panel_actions()

    def _build_sidebar(self, parent_layout: QHBoxLayout):
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
        subtitle.setStyleSheet("font-size: 12px; color: #d0d5dd; font-weight: 700;")
        logo_layout.addWidget(subtitle)

        self.lbl_meter_type = QLabel("Hisoblagich aniqlanmoqda")
        self.lbl_meter_type.setStyleSheet("font-size: 12px; color: #98a2b3;")
        logo_layout.addWidget(self.lbl_meter_type)

        sb_layout.addWidget(logo_frame)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #2b364e;")
        sb_layout.addWidget(sep)

        # Nav buttons
        nav_items = [
            ("", "Asosiy panel"),
            ("", "Rele boshqarish"),
            ("", "Tekshiruv"),
            ("", "Servis"),
            ("", "Jurnal"),
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
        self.lbl_port.setStyleSheet("font-size: 12px; color: #d0d5dd;")
        conn_layout.addWidget(self.lbl_port)

        self.lbl_serial = QLabel("")
        self.lbl_serial.setStyleSheet("font-size: 12px; color: #d0d5dd;")
        conn_layout.addWidget(self.lbl_serial)

        # Status dot
        self.lbl_status = QLabel("Status: ulangan")
        self.lbl_status.setStyleSheet("font-size: 12px; color: #98f5bd; font-weight: 700;")
        conn_layout.addWidget(self.lbl_status)

        self.btn_reconnect = QPushButton("🔄 Qayta ulanish")
        self.btn_reconnect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reconnect.setStyleSheet(
            "QPushButton{background:#24314a;color:#ffffff;border:1px solid #40506d;"
            "border-radius:6px;font-weight:700;padding:6px;font-size:11px;margin-top:6px;}"
            "QPushButton:hover{background:#31405c;border-color:#ffffff;color:#ffffff;}"
        )
        self.btn_reconnect.setVisible(False)
        self.btn_reconnect.clicked.connect(self._on_reconnect_clicked)
        conn_layout.addWidget(self.btn_reconnect)

        sb_layout.addWidget(conn_frame)

        # ESP32 Flash button
        btn_flash = QPushButton("ESP32 Flash")
        btn_flash.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_flash.setStyleSheet(
            "QPushButton{background:#24314a;color:#d0d5dd;border:1px solid #40506d;"
            "border-radius:8px;font-weight:700;margin:4px 16px;padding:8px;}"
            "QPushButton:hover{background:#31405c;color:#ffffff;}"
        )
        btn_flash.clicked.connect(self._open_flash_window)
        sb_layout.addWidget(btn_flash)

        # Disconnect button
        btn_disc = QPushButton("Uzish")
        btn_disc.setObjectName("sidebarDanger")
        btn_disc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_disc.clicked.connect(self._disconnect)
        btn_wrap = QWidget()
        btn_wrap_layout = QVBoxLayout(btn_wrap)
        btn_wrap_layout.setContentsMargins(16, 4, 16, 16)
        btn_wrap_layout.addWidget(btn_disc)
        sb_layout.addWidget(btn_wrap)

        parent_layout.addWidget(sidebar)

    def _build_content(self, parent_layout: QHBoxLayout):
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 14)
        content_layout.setSpacing(12)

        # Page header: two rows so controls do not overlap on narrower screens.
        header = QFrame()
        header.setObjectName("headerCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        header_layout.addLayout(top_row)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        self.lbl_page_title = QLabel("Asosiy panel")
        self.lbl_page_title.setObjectName("page_title")
        title_box.addWidget(self.lbl_page_title)

        self.lbl_page_subtitle = QLabel("Hisoblagichning asosiy holati va o'lchovlari")
        self.lbl_page_subtitle.setObjectName("page_subtitle")
        self.lbl_page_subtitle.setWordWrap(True)
        title_box.addWidget(self.lbl_page_subtitle)
        top_row.addLayout(title_box, 1)

        self.header_status = QLabel("Ulangan")
        self.header_status.setObjectName("statusChipOk")
        top_row.addWidget(self.header_status)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)
        header_layout.addLayout(bottom_row)

        page_label = QLabel("Sahifa:")
        page_label.setObjectName("smallLabel")
        bottom_row.addWidget(page_label)

        self.combo_pages = QComboBox()
        self.combo_pages.addItems([
            "Asosiy panel",
            "Rele boshqarish",
            "Tekshiruv",
            "Servis",
            "Jurnal",
        ])
        self.combo_pages.setMinimumWidth(170)
        self.combo_pages.currentIndexChanged.connect(self._nav_to)
        bottom_row.addWidget(self.combo_pages)

        self.header_port_value = self._header_info(bottom_row, "PORT", self.settings.get("port", ""))
        self.header_serial_value = self._header_info(bottom_row, "SERIAL", "---")
        bottom_row.addStretch()

        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)
        header_layout.addLayout(actions_row)

        self.btn_header_refresh = QPushButton("Yangilash")
        self.btn_header_refresh.setObjectName("primary")
        self.btn_header_refresh.clicked.connect(self._refresh_current_page)
        actions_row.addWidget(self.btn_header_refresh, 1)

        self.btn_prev_page = QPushButton("Oldingi")
        self.btn_prev_page.clicked.connect(lambda: self._nav_to(max(0, self.pages.currentIndex() - 1)))
        actions_row.addWidget(self.btn_prev_page)

        self.btn_next_page = QPushButton("Keyingi")
        self.btn_next_page.clicked.connect(lambda: self._nav_to(min(self.pages.count() - 1, self.pages.currentIndex() + 1)))
        actions_row.addWidget(self.btn_next_page)
        actions_row.addStretch()

        # Auto-refresh controls
        self.chk_auto_refresh = QCheckBox("Avtomatik")
        self.chk_auto_refresh.setChecked(True)
        self.chk_auto_refresh.toggled.connect(self._on_auto_refresh_toggled)
        actions_row.addWidget(self.chk_auto_refresh)

        self.combo_refresh_interval = QComboBox()
        self.combo_refresh_interval.addItems(["3s", "5s", "10s", "30s"])
        self.combo_refresh_interval.setCurrentIndex(0)
        self.combo_refresh_interval.currentIndexChanged.connect(self._on_refresh_interval_changed)
        self.combo_refresh_interval.setMaximumWidth(80)
        actions_row.addWidget(self.combo_refresh_interval)

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

        parent_layout.addWidget(content, 1)

    # ── Controller Signal Connections ─────────────────────────────────────

    def _connect_controller_signals(self):
        ctrl = self.controller

        ctrl.info_updated.connect(self._on_info_updated)
        ctrl.dashboard_updated.connect(self._on_dashboard_updated)
        ctrl.relay_updated.connect(self._on_relay_updated)
        ctrl.relay_action_done.connect(self._on_relay_action_done)
        ctrl.registers_loaded.connect(self._on_registers_loaded)
        ctrl.time_read.connect(self._on_time_read)
        ctrl.time_synced.connect(self._on_time_synced)
        ctrl.password_changed.connect(self._on_password_changed)
        ctrl.custom_register_read.connect(self._on_custom_register_read)
        ctrl.reconnect_result.connect(self._on_reconnect_result)
        ctrl.connection_lost.connect(self._on_connection_lost)
        ctrl.status_message.connect(self._on_status_message)
        ctrl.error_occurred.connect(self._on_error_occurred)

        # Set log callbacks
        self.controller.conn.set_callbacks(
            on_tx=self.log_panel.add_tx,
            on_rx=self.log_panel.add_rx,
            on_log=self.log_panel.add_app_log,
        )
        self.controller.service.set_log_callback(self.log_panel.add_app_log)

    def _connect_panel_actions(self):
        # Relay panel
        self.relay_panel.btn_reconnect.clicked.connect(self._relay_reconnect)
        self.relay_panel.btn_disconnect.clicked.connect(self._relay_disconnect)
        self.relay_panel.btn_refresh.clicked.connect(self._read_relay)
        self.relay_panel.btn_set_mode.clicked.connect(self._set_relay_mode)

        # Registers panel
        self.registers_panel.btn_read_all.clicked.connect(self.controller.read_all_registers)
        self.registers_panel.btn_read_custom.clicked.connect(self._read_custom)

        # Settings panel
        self.settings_panel.btn_read_info.clicked.connect(self.controller.read_info)
        self.settings_panel.btn_read_time.clicked.connect(self.controller.read_time)
        self.settings_panel.btn_sync_time.clicked.connect(self._sync_time)
        self.settings_panel.btn_set_pwd.clicked.connect(self._change_password)

        # Enable panels
        self.relay_panel.set_enabled(True)
        self.registers_panel.set_enabled(True)
        self.settings_panel.set_enabled(True)

    # ── Controller Signal Handlers ────────────────────────────────────────

    def _on_info_updated(self, info):
        serial = info.serial or "aniqlanmadi"
        self.lbl_meter_type.setText(f"{info.meter_type}  |  S/N: {serial}")
        self.lbl_serial.setText(f"S/N: {serial}")
        self.header_serial_value.setText(info.serial or "---")
        self.settings_panel.update_info(
            info.serial, info.manufacturer, info.device_name,
            info.firmware, info.meter_type,
        )
        self.dashboard.set_3phase(info.meter_type == "TE73")
        # Queue follow-up reads
        self.controller.read_dashboard()
        self.controller.read_relay()

    def _on_dashboard_updated(self, data: dict):
        self.dashboard.update_values(data)
        if self.chk_auto_refresh.isChecked() and self.pages.currentIndex() == 0:
            self.auto_refresh_timer.start(self._get_refresh_interval_ms())

    def _on_relay_updated(self, status):
        self.relay_panel.hide_loading()
        self.relay_panel.update_status(
            status.output_state, status.control_text, status.mode_text,
            getattr(status, "control_mode", 5)
        )

    def _on_relay_action_done(self, action: str, ok: bool, status):
        self.relay_panel.hide_loading()
        self.relay_panel.update_status(
            status.output_state, status.control_text, status.mode_text,
            getattr(status, "control_mode", 5)
        )
        if action == "set_relay_mode":
            if ok:
                self.log_panel.add_app_log("Rele ish rejimi muvaffaqiyatli o'zgartirildi!")
                QMessageBox.information(self, "Muvaffaqiyat", "Rele rejimi o'zgartirildi!")
            else:
                QMessageBox.warning(self, "Xato", "Rele rejimini o'zgartirish rad etildi!")
        else:
            if ok:
                msg = "yoqildi" if action == "relay_reconnect" else "o'chirildi"
                self.log_panel.add_app_log(f"Rele {msg}!")
            else:
                QMessageBox.warning(self, "Xato", "Rele buyrug'i rad etildi!")

    def _on_registers_loaded(self, data: list):
        self.registers_panel.populate(data)

    def _on_time_read(self, dt):
        self.settings_panel.update_time(dt)

    def _on_time_synced(self, ok: bool, dt):
        if ok:
            self.settings_panel.update_time(dt)
        else:
            QMessageBox.warning(self, "Xato", "Vaqt sinxronlash xatosi!")

    def _on_password_changed(self, ok: bool):
        if ok:
            QMessageBox.information(self, "Muvaffaqiyat", "Parol muvaffaqiyatli o'zgartirildi!")
            self.settings_panel.pwd_input.clear()
        else:
            QMessageBox.warning(self, "Xato", "Parolni o'zgartirib bo'lmadi! Huquqlar yetarli ekanligini tekshiring.")

    def _on_custom_register_read(self, value: str):
        obis_str = self.registers_panel.obis_input.text()
        class_id = int(self.registers_panel.class_input.text() or "3")
        attr = int(self.registers_panel.attr_input.text() or "2")
        self.registers_panel.add_custom_row(obis_str, class_id, attr, value)

    def _on_reconnect_result(self, ok: bool):
        if ok:
            self.lbl_status.setText("Status: ulangan")
            self.lbl_status.setStyleSheet("font-size: 12px; color: #98f5bd; font-weight: 700;")
            self.btn_reconnect.setVisible(False)
            self.log_panel.add_app_log("Hisoblagichga qayta ulanish muvaffaqiyatli!")

            info = self.controller.service.info
            serial = info.serial or "aniqlanmadi"
            self.lbl_meter_type.setText(f"{info.meter_type}  |  S/N: {serial}")
            self.lbl_serial.setText(f"S/N: {serial}")
            self.header_serial_value.setText(info.serial or "---")
            self.settings_panel.update_info(
                info.serial, info.manufacturer, info.device_name,
                info.firmware, info.meter_type,
            )
            self.dashboard.set_3phase(info.meter_type == "TE73")

            if self.chk_auto_refresh.isChecked() and self.pages.currentIndex() == 0:
                self.controller.read_dashboard()
        else:
            self.lbl_status.setText("Status: ulanish xatosi")
            self.lbl_status.setStyleSheet("font-size: 12px; color: #f87171; font-weight: 700;")
            self.btn_reconnect.setVisible(True)
            self.log_panel.add_app_log("Hisoblagichga qayta ulanib bo'lmadi!")

    def _on_connection_lost(self):
        self.lbl_status.setText("Status: aloqa uzildi")
        self.lbl_status.setStyleSheet("font-size: 12px; color: #f87171; font-weight: 700;")
        self.btn_reconnect.setVisible(True)
        self.auto_refresh_timer.stop()
        self.log_panel.add_app_log("Aloqa butunlay uzildi (3 marta ketma-ket xato). Iltimos, ulanishni va portni tekshiring!")

    def _on_status_message(self, message: str, color: str):
        self.lbl_bottom_status.setText(message)
        self.lbl_bottom_status.setStyleSheet(f"font-size: 12px; color: {color}; padding-top: 4px;")

    def _on_error_occurred(self, action: str, error: str):
        self.lbl_bottom_status.setText(f"Xato: {error}")
        self.lbl_bottom_status.setStyleSheet("font-size: 12px; color: #cf2e2e; padding-top: 4px;")
        self.log_panel.add_app_log(f"XATO [{action}]: {error}")
        if action in ("read_relay", "relay_reconnect", "relay_disconnect", "set_relay_mode"):
            self.relay_panel.hide_loading()

        # Auto-retry dashboard on non-critical errors
        if (action == "read_dashboard" and self.controller.consecutive_failures < 3
                and self.chk_auto_refresh.isChecked() and self.pages.currentIndex() == 0):
            self.log_panel.add_app_log(f"Qayta urinish ({self.controller.consecutive_failures}/3)...")
            QTimer.singleShot(2000, self.controller.read_dashboard)

    # ── Navigation ────────────────────────────────────────────────────────

    def _nav_to(self, index: int):
        self.pages.setCurrentIndex(index)

        for btn in self.nav_buttons:
            btn.setChecked(btn.index == index)

        if hasattr(self, "combo_pages") and self.combo_pages.currentIndex() != index:
            self.combo_pages.blockSignals(True)
            self.combo_pages.setCurrentIndex(index)
            self.combo_pages.blockSignals(False)

        if hasattr(self, "btn_prev_page"):
            self.btn_prev_page.setEnabled(index > 0)
            self.btn_next_page.setEnabled(index < self.pages.count() - 1)

        titles = [
            ("Asosiy panel", "Asosiy elektr ko'rsatkichlari va energiya sarfi"),
            ("Rele boshqarish", "Yuklama relesi holati va boshqaruvi"),
            ("Tekshiruv", "OBIS registrlar va qo'lda o'qish"),
            ("Servis", "Hisoblagich ma'lumotlari, vaqt va servis amallari"),
            ("Jurnal", "Aloqa freymlari va dastur xabarlari"),
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

        # Auto-refresh page content on tab change
        if self.controller.conn and self.controller.conn.connected:
            if index == 0:
                if self.chk_auto_refresh.isChecked():
                    self.controller.read_dashboard()
            elif index == 1:
                self._read_relay()
            elif index == 3:
                self.controller.read_time()

    # ── User Actions ──────────────────────────────────────────────────────

    def _refresh_current_page(self):
        index = self.pages.currentIndex()
        if index == 0:
            self.controller.read_dashboard()
        elif index == 1:
            self._read_relay()
        elif index == 2:
            self.controller.read_all_registers()
        elif index == 3:
            self.controller.read_info()

    def _read_relay(self):
        self.relay_panel.show_loading("read_relay")
        self.controller.read_relay()

    def _relay_reconnect(self):
        if self.relay_panel.confirm_action("YOQISH"):
            self.relay_panel.show_loading("relay_reconnect")
            self.controller.relay_reconnect()

    def _relay_disconnect(self):
        if self.relay_panel.confirm_action("O'CHIRISH"):
            self.relay_panel.show_loading("relay_disconnect")
            self.controller.relay_disconnect()

    def _set_relay_mode(self):
        idx = self.relay_panel.combo_mode.currentIndex()
        reply = QMessageBox.question(
            self, "Tasdiqlash",
            f"Rele ish rejimini {idx} ga o'zgartirishni tasdiqlaysizmi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.relay_panel.show_loading("set_relay_mode")
            self.controller.set_relay_mode(idx)

    def _sync_time(self):
        if self.settings_panel.confirm_sync():
            self.controller.sync_time()

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
            self.controller.change_password(new_pwd)

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
            attr = int(self.registers_panel.attr_input.text() or "2")
        except ValueError:
            return
        if attr < 1:
            QMessageBox.warning(self, "Xato", "Attribute raqami 1 dan katta bo'lishi kerak")
            return
        self.controller.read_custom_register(class_id, obis_tuple, attr)

    def _on_reconnect_clicked(self):
        self.lbl_status.setText("Status: ulanmoqda...")
        self.lbl_status.setStyleSheet("font-size: 12px; color: #f59e0b; font-weight: 700;")
        self.btn_reconnect.setVisible(False)
        self.log_panel.add_app_log("Hisoblagichga qayta ulanish boshlandi...")
        self.controller.reconnect()

    # ── Auto-refresh ──────────────────────────────────────────────────────

    def _auto_refresh(self):
        self.auto_refresh_timer.stop()
        if self.controller.conn and self.controller.conn.connected and not self.controller.is_busy:
            if self.pages.currentIndex() == 0 and self.chk_auto_refresh.isChecked():
                self.controller.read_dashboard()

    def _get_refresh_interval_ms(self) -> int:
        txt = self.combo_refresh_interval.currentText()
        try:
            return int(txt.replace("s", "")) * 1000
        except ValueError:
            return 3000

    def _on_auto_refresh_toggled(self, checked: bool):
        if checked:
            if (self.controller.conn and self.controller.conn.connected
                    and not self.controller.is_busy and self.pages.currentIndex() == 0):
                self.controller.read_dashboard()
        else:
            self.auto_refresh_timer.stop()

    def _on_refresh_interval_changed(self):
        if self.chk_auto_refresh.isChecked() and self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()
            self.auto_refresh_timer.start(self._get_refresh_interval_ms())

    # ── Helpers ───────────────────────────────────────────────────────────

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

    def _open_flash_window(self):
        from .flash_window import FlashWindow
        if not hasattr(self, "_flash_win") or not self._flash_win.isVisible():
            self._flash_win = FlashWindow(self)
        self._flash_win.show()
        self._flash_win.raise_()

    def _disconnect(self):
        self.auto_refresh_timer.stop()
        self.controller.stop()
        if self.controller.conn:
            try:
                self.controller.conn.close()
            except Exception:
                pass
        self.close()

    def closeEvent(self, event):
        self.auto_refresh_timer.stop()
        self.controller.stop()
        if self.controller.conn:
            try:
                self.controller.conn.close()
            except Exception:
                pass
        event.accept()
