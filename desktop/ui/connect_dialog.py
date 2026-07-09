"""Connection dialog shown before the main application."""
import serial.tools.list_ports
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .styles import CONNECT_DIALOG_STYLE

# Meter type -> (label, baud, fallback_baud)
METER_TYPES = [
    ("TE71  —  1-fazali  (9600 baud)",  9600, 4800),
    ("TE73  —  3-fazali  (4800 baud)",  4800, 9600),
    ("Qo'lda sozlash...",               None, None),
]

BAUD_OPTIONS = ["9600", "4800", "1200", "19200", "38400", "115200"]


class ConnectDialog(QDialog):
    """Simple connection screen for non-technical users."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hisoblagichga ulanish")
        self.setFixedSize(520, 520)
        self.setStyleSheet(CONNECT_DIALOG_STYLE)

        self.result_port = ""
        self.result_baud = 9600
        self.result_auth = 0
        self.result_password = "00000000"

        self._setup_ui()
        self._refresh_ports()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        title = QLabel("Elektr hisoblagich")
        title.setObjectName("page_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("USB-RS485 adapter portini tanlang va hisoblagichga ulaning")
        subtitle.setObjectName("page_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(14)
        root.addWidget(card)

        # Meter type
        card_layout.addWidget(self._field_label("Hisoblagich turi"))
        self.combo_meter = QComboBox()
        self.combo_meter.setMinimumHeight(42)
        for label, _, _ in METER_TYPES:
            self.combo_meter.addItem(label)
        self.combo_meter.currentIndexChanged.connect(self._on_meter_changed)
        card_layout.addWidget(self.combo_meter)

        # COM port row
        port_label_row = QHBoxLayout()
        port_label_row.addWidget(self._field_label("COM port"), 3)
        self.lbl_baud_header = self._field_label("Baud rate")
        port_label_row.addWidget(self.lbl_baud_header, 1)
        card_layout.addLayout(port_label_row)

        port_row = QHBoxLayout()
        port_row.setSpacing(10)

        self.combo_port = QComboBox()
        self.combo_port.setMinimumHeight(42)
        port_row.addWidget(self.combo_port, 3)

        self.btn_refresh = QPushButton("Yangilash")
        self.btn_refresh.setMinimumHeight(42)
        self.btn_refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(self.btn_refresh, 1)

        self.combo_baud = QComboBox()
        self.combo_baud.setMinimumHeight(42)
        self.combo_baud.addItems(BAUD_OPTIONS)
        self.combo_baud.setCurrentText("9600")
        port_row.addWidget(self.combo_baud, 1)

        card_layout.addLayout(port_row)

        # Auth mode
        card_layout.addWidget(self._field_label("Ulanish rejimi"))
        self.combo_auth = QComboBox()
        self.combo_auth.setMinimumHeight(42)
        self.combo_auth.addItems([
            "Reader - o'qish va releni boshqarish",
            "Manager - servis rejimi (parol bilan)",
            "Public - parolsiz o'qish",
        ])
        self.combo_auth.currentIndexChanged.connect(self._on_auth_changed)
        card_layout.addWidget(self.combo_auth)

        # Manager password (hidden by default)
        self.lbl_pwd = self._field_label("Manager paroli")
        self.lbl_pwd.setVisible(False)
        card_layout.addWidget(self.lbl_pwd)

        self.txt_password = QLineEdit("00000000")
        self.txt_password.setMinimumHeight(42)
        self.txt_password.setVisible(False)
        card_layout.addWidget(self.txt_password)

        # Connect button
        self.btn_connect = QPushButton("Hisoblagichga ulanish")
        self.btn_connect.setObjectName("primary")
        self.btn_connect.setMinimumHeight(46)
        self.btn_connect.clicked.connect(self._on_connect)
        card_layout.addWidget(self.btn_connect)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: #f87171; font-weight: 600;")
        card_layout.addWidget(self.lbl_status)

        # Divider
        div_layout = QHBoxLayout()
        line1 = QFrame(); line1.setFixedHeight(1); line1.setStyleSheet("background:#24364f;")
        lbl_or = QLabel("yoki"); lbl_or.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_or.setStyleSheet("color:#475467; font-size:12px; padding: 0 8px;")
        line2 = QFrame(); line2.setFixedHeight(1); line2.setStyleSheet("background:#24364f;")
        div_layout.addWidget(line1, 1)
        div_layout.addWidget(lbl_or)
        div_layout.addWidget(line2, 1)
        card_layout.addLayout(div_layout)

        # ESP32 Flash button
        self.btn_flash = QPushButton("⚡  ESP32 ga firmware yuklash")
        self.btn_flash.setMinimumHeight(42)
        self.btn_flash.setStyleSheet(
            "QPushButton{background:#0f2d4a;color:#60a5fa;border:1.5px solid #1e4976;"
            "border-radius:8px;font-weight:700;}"
            "QPushButton:hover{background:#1e3a5f;color:#93c5fd;}"
        )
        self.btn_flash.clicked.connect(self._on_open_flash)
        card_layout.addWidget(self.btn_flash)

        hint = QLabel(
            "Tavsiya: oddiy tekshiruv va rele boshqarish uchun Reader rejimidan foydalaning."
        )
        hint.setObjectName("page_subtitle")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hint)

        # Initial state
        self._on_meter_changed(0)

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #475467; font-weight: 700;")
        return label

    def _refresh_ports(self):
        self.combo_port.clear()
        ports = serial.tools.list_ports.comports()
        for port in sorted(ports, key=lambda p: p.device):
            desc = "" if port.description == port.device else f" — {port.description}"
            self.combo_port.addItem(f"{port.device}{desc}", port.device)
        if not ports:
            self.combo_port.addItem("Port topilmadi", "")

    def _on_meter_changed(self, index: int):
        _, baud, _ = METER_TYPES[index]
        manual = baud is None
        self.combo_baud.setVisible(manual)
        self.lbl_baud_header.setVisible(manual)
        if baud:
            self.combo_baud.setCurrentText(str(baud))

    def _on_auth_changed(self, index: int):
        show_pwd = index == 1
        self.lbl_pwd.setVisible(show_pwd)
        self.txt_password.setVisible(show_pwd)
        self.setFixedSize(520, 575 if show_pwd else 520)

    def _on_open_flash(self):
        """ESP32 Flash oynasini ochadi (hisoblagich ulanishi shart emas)."""
        from .flash_window import FlashWindow
        self._flash_win = FlashWindow()
        self._flash_win.show()

    def _on_connect(self):
        port = self.combo_port.currentData()
        if not port:
            self.lbl_status.setText("COM port tanlanmagan")
            return

        self.result_port = port
        self.result_baud = int(self.combo_baud.currentText())
        self.result_auth = self.combo_auth.currentIndex()
        self.result_password = self.txt_password.text().strip() or "00000000"

        # Store fallback baud for auto-retry
        idx = self.combo_meter.currentIndex()
        _, _, fallback = METER_TYPES[idx]
        self.result_fallback_baud = fallback

        self.accept()

    def get_settings(self) -> dict:
        return {
            "port": self.result_port,
            "baud": self.result_baud,
            "fallback_baud": getattr(self, "result_fallback_baud", None),
            "auth": self.result_auth,
            "password": self.result_password,
        }
