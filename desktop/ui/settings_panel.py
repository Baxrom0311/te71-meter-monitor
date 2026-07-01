"""Settings and meter information panel."""
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget


class InfoCard(QFrame):
    """Small read-only information card."""

    def __init__(self, label: str):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(5)

        title = QLabel(label)
        title.setObjectName("metricTitle")
        layout.addWidget(title)

        self.value_label = QLabel("---")
        self.value_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #38bdf8;")
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.value_label)

    def set_value(self, text: str):
        self.value_label.setText(text or "---")


class SettingsPanel(QWidget):
    """Meter info, time sync, and password controls."""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        info_title = self._section_title("Hisoblagich ma'lumotlari")
        layout.addWidget(info_title)

        info_row = QHBoxLayout()
        info_row.setSpacing(12)
        self.card_serial = InfoCard("Seriya raqami")
        self.card_manufacturer = InfoCard("Ishlab chiqaruvchi")
        self.card_firmware = InfoCard("Firmware")
        self.card_type = InfoCard("Hisoblagich turi")
        for card in (self.card_serial, self.card_manufacturer, self.card_firmware, self.card_type):
            info_row.addWidget(card)
        layout.addLayout(info_row)

        self.btn_read_info = QPushButton("Ma'lumotlarni yangilash")
        self.btn_read_info.setEnabled(False)
        layout.addWidget(self.btn_read_info)

        layout.addWidget(self._section_title("Vaqt sinxronizatsiya"))
        time_card = QFrame()
        time_card.setObjectName("card")
        time_layout = QVBoxLayout(time_card)
        time_layout.setContentsMargins(18, 16, 18, 16)
        time_layout.setSpacing(12)

        self.lbl_meter_time = QLabel("---")
        self.lbl_pc_time = QLabel("---")
        self.lbl_time_diff = QLabel("---")
        time_layout.addLayout(self._time_row("Hisoblagich vaqti:", self.lbl_meter_time, "#10b981"))
        time_layout.addLayout(self._time_row("Kompyuter vaqti:", self.lbl_pc_time, "#38bdf8"))
        time_layout.addLayout(self._time_row("Farq:", self.lbl_time_diff, "#ffffff"))

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_read_time = QPushButton("Vaqtni o'qish")
        self.btn_read_time.setEnabled(False)
        btn_row.addWidget(self.btn_read_time)

        self.btn_sync_time = QPushButton("Kompyuter vaqtiga sinxronlash")
        self.btn_sync_time.setObjectName("primary")
        self.btn_sync_time.setEnabled(False)
        btn_row.addWidget(self.btn_sync_time)
        btn_row.addStretch()
        time_layout.addLayout(btn_row)

        layout.addWidget(time_card)

        layout.addWidget(self._section_title("Parol boshqarish"))
        password_card = QFrame()
        password_card.setObjectName("card")
        pwd_layout = QHBoxLayout(password_card)
        pwd_layout.setContentsMargins(18, 16, 18, 16)
        pwd_layout.setSpacing(10)

        pwd_layout.addWidget(QLabel("Yangi parol:"))
        self.pwd_input = QLineEdit()
        self.pwd_input.setPlaceholderText("00000000")
        self.pwd_input.setMaximumWidth(180)
        pwd_layout.addWidget(self.pwd_input)

        self.btn_set_pwd = QPushButton("O'zgartirish")
        self.btn_set_pwd.setEnabled(False)
        pwd_layout.addWidget(self.btn_set_pwd)
        pwd_layout.addStretch()
        layout.addWidget(password_card)

        layout.addStretch()

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-size: 15px; color: #344054; font-weight: 800;")
        return label

    def _time_row(self, title: str, value: QLabel, color: str) -> QHBoxLayout:
        row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setMinimumWidth(140)
        title_label.setStyleSheet("color: #667085; font-weight: 700;")
        row.addWidget(title_label)
        value.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {color};")
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(value)
        row.addStretch()
        return row

    def update_info(self, serial: str, manufacturer: str, device_name: str, firmware: str, meter_type: str):
        self.card_serial.set_value(serial)
        self.card_manufacturer.set_value(manufacturer or device_name)
        self.card_firmware.set_value(firmware)
        self.card_type.set_value(meter_type)

    def update_time(self, meter_time: datetime | None):
        now = datetime.now()
        self.lbl_pc_time.setText(now.strftime("%Y-%m-%d %H:%M:%S"))
        if not meter_time:
            self.lbl_meter_time.setText("O'qib bo'lmadi")
            self.lbl_time_diff.setText("---")
            return

        self.lbl_meter_time.setText(meter_time.strftime("%Y-%m-%d %H:%M:%S"))
        diff = abs((now - meter_time).total_seconds())
        if diff < 2:
            self.lbl_time_diff.setText(f"{diff:.1f} soniya, sinxron")
            self.lbl_time_diff.setStyleSheet("font-size: 18px; font-weight: 800; color: #10b981;")
        elif diff < 60:
            self.lbl_time_diff.setText(f"{diff:.1f} soniya")
            self.lbl_time_diff.setStyleSheet("font-size: 18px; font-weight: 800; color: #f59e0b;")
        else:
            self.lbl_time_diff.setText(f"{diff / 60:.1f} daqiqa")
            self.lbl_time_diff.setStyleSheet("font-size: 18px; font-weight: 800; color: #f87171;")

    def set_enabled(self, enabled: bool):
        self.btn_read_info.setEnabled(enabled)
        self.btn_read_time.setEnabled(enabled)
        self.btn_sync_time.setEnabled(enabled)
        self.btn_set_pwd.setEnabled(enabled)

    def confirm_sync(self) -> bool:
        msg = QMessageBox(self)
        msg.setWindowTitle("Tasdiqlash")
        msg.setText("Hisoblagich vaqtini kompyuter vaqtiga sinxronlash?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        return msg.exec() == QMessageBox.StandardButton.Yes
