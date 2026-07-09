"""Settings and meter information page.

Uses shared InfoCard component from ui.widgets.
Responsive layout dynamically rearranges info cards based on window width.
"""
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget, QGridLayout

from ui.theme import Colors, Fonts, inline_style
from ui.widgets import InfoCard


class SettingsPanel(QWidget):
    """Meter info, time sync, and password controls (Responsive)."""

    def __init__(self):
        super().__init__()
        self._current_cols = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(self._section_title("Hisoblagich ma'lumotlari"))

        # Responsive info cards grid
        self.info_grid = QGridLayout()
        self.info_grid.setSpacing(12)
        layout.addLayout(self.info_grid)

        self.card_serial = InfoCard("Seriya raqami")
        self.card_manufacturer = InfoCard("Ishlab chiqaruvchi")
        self.card_firmware = InfoCard("Firmware")
        self.card_type = InfoCard("Hisoblagich turi")

        self.info_cards = [
            self.card_serial,
            self.card_manufacturer,
            self.card_firmware,
            self.card_type
        ]

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
        time_layout.addLayout(self._time_row("Hisoblagich vaqti:", self.lbl_meter_time, Colors.STATUS_GREEN))
        time_layout.addLayout(self._time_row("Kompyuter vaqti:", self.lbl_pc_time, Colors.ACCENT_BLUE))
        time_layout.addLayout(self._time_row("Farq:", self.lbl_time_diff, Colors.TEXT_WHITE))

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
        self._rearrange_layout()

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def _time_row(self, title: str, value: QLabel, color: str) -> QHBoxLayout:
        row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setMinimumWidth(140)
        title_label.setStyleSheet(inline_style(color=Colors.TEXT_DIMMED, font_weight=Fonts.WEIGHT_BOLD))
        row.addWidget(title_label)
        value.setStyleSheet(inline_style(font_size=Fonts.SIZE_HEADER, font_weight=Fonts.WEIGHT_EXTRA_BOLD, color=color))
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
            self.lbl_time_diff.setStyleSheet(inline_style(font_size=Fonts.SIZE_HEADER, font_weight=Fonts.WEIGHT_EXTRA_BOLD, color=Colors.STATUS_GREEN))
        elif diff < 60:
            self.lbl_time_diff.setText(f"{diff:.1f} soniya")
            self.lbl_time_diff.setStyleSheet(inline_style(font_size=Fonts.SIZE_HEADER, font_weight=Fonts.WEIGHT_EXTRA_BOLD, color=Colors.STATUS_WARN))
        else:
            self.lbl_time_diff.setText(f"{diff / 60:.1f} daqiqa")
            self.lbl_time_diff.setStyleSheet(inline_style(font_size=Fonts.SIZE_HEADER, font_weight=Fonts.WEIGHT_EXTRA_BOLD, color=Colors.STATUS_ERROR))

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rearrange_layout()

    def _rearrange_layout(self):
        width = self.width()

        # Choose column count based on panel width
        if width < 500:
            cols = 1
        elif width < 800:
            cols = 2
        else:
            cols = 4

        if cols == self._current_cols:
            return
        self._current_cols = cols

        # Remove cards from grid
        for card in self.info_cards:
            self.info_grid.removeWidget(card)

        # Place back into grid with new columns
        for index, card in enumerate(self.info_cards):
            self.info_grid.addWidget(card, index // cols, index % cols)

        # Set stretches
        for c in range(max(cols, 4)):
            self.info_grid.setColumnStretch(c, 1 if c < cols else 0)
