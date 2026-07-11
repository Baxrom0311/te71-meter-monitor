"""Connection dialog shown before the main application."""
import serial.tools.list_ports
from PyQt6.QtCore import Qt, QSettings
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
        self.setFixedSize(560, 620)
        self.setStyleSheet(CONNECT_DIALOG_STYLE)

        self.settings_storage = QSettings("Toshelectroapparat", "MeterTool")

        self.result_port = ""
        self.result_baud = 9600
        self.result_auth = 0
        self.result_password = "00000000"

        self._setup_ui()
        self._refresh_ports()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(16)

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
        card_layout.setSpacing(16)
        root.addWidget(card)

        # Meter type
        card_layout.addWidget(self._field_label("Hisoblagich turi"))
        self.combo_meter = QComboBox()
        self.combo_meter.setMinimumHeight(40)
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
        self.combo_port.setMinimumHeight(40)
        port_row.addWidget(self.combo_port, 3)

        self.btn_refresh = QPushButton("Yangilash")
        self.btn_refresh.setMinimumHeight(40)
        self.btn_refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(self.btn_refresh, 1)

        self.combo_baud = QComboBox()
        self.combo_baud.setMinimumHeight(40)
        self.combo_baud.addItems(BAUD_OPTIONS)
        self.combo_baud.setCurrentText("9600")
        port_row.addWidget(self.combo_baud, 1)

        card_layout.addLayout(port_row)

        # Parity & Stop bits row (Manual mode only)
        extra_row = QHBoxLayout()
        extra_row.setSpacing(10)

        v_parity = QVBoxLayout()
        v_parity.setSpacing(4)
        self.lbl_parity = self._field_label("Paritet (Parity)")
        self.combo_parity = QComboBox()
        self.combo_parity.setMinimumHeight(40)
        self.combo_parity.addItems(["N (None)", "E (Even)", "O (Odd)"])
        v_parity.addWidget(self.lbl_parity)
        v_parity.addWidget(self.combo_parity)
        extra_row.addLayout(v_parity, 1)

        v_stopbits = QVBoxLayout()
        v_stopbits.setSpacing(4)
        self.lbl_stopbits = self._field_label("Stop bitlar")
        self.combo_stopbits = QComboBox()
        self.combo_stopbits.setMinimumHeight(40)
        self.combo_stopbits.addItems(["1", "1.5", "2"])
        v_stopbits.addWidget(self.lbl_stopbits)
        v_stopbits.addWidget(self.combo_stopbits)
        extra_row.addLayout(v_stopbits, 1)

        card_layout.addLayout(extra_row)

        # Auth mode
        card_layout.addWidget(self._field_label("Ulanish rejimi"))
        self.combo_auth = QComboBox()
        self.combo_auth.setMinimumHeight(40)
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
        self.txt_password.setMinimumHeight(40)
        self.txt_password.setVisible(False)
        card_layout.addWidget(self.txt_password)

        # Connect button
        self.btn_connect = QPushButton("Hisoblagichga ulanish")
        self.btn_connect.setObjectName("primary")
        self.btn_connect.setMinimumHeight(44)
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
        lbl_or.setStyleSheet("color:#64748b; font-size:12px; padding: 0 8px;")
        line2 = QFrame(); line2.setFixedHeight(1); line2.setStyleSheet("background:#24364f;")
        div_layout.addWidget(line1, 1)
        div_layout.addWidget(lbl_or)
        div_layout.addWidget(line2, 1)
        card_layout.addLayout(div_layout)

        # ESP32 Flash button
        self.btn_flash = QPushButton("ESP32 ga firmware yuklash")
        self.btn_flash.setMinimumHeight(40)
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
        last_meter = int(self.settings_storage.value("last_meter_index", 0))
        last_auth = int(self.settings_storage.value("last_auth_index", 0))
        last_baud = self.settings_storage.value("last_baud", "9600")
        last_parity = self.settings_storage.value("last_parity", "N (None)")
        last_stopbits = self.settings_storage.value("last_stopbits", "1")

        self.combo_meter.setCurrentIndex(last_meter)
        self.combo_auth.setCurrentIndex(last_auth)
        self.combo_baud.setCurrentText(last_baud)
        self.combo_parity.setCurrentText(last_parity)
        self.combo_stopbits.setCurrentText(last_stopbits)

        self._on_meter_changed(last_meter)
        self._on_auth_changed(last_auth)

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #94a3b8; font-weight: 700;")
        return label

    def _refresh_ports(self):
        self.combo_port.clear()
        ports = serial.tools.list_ports.comports()
        for port in sorted(ports, key=lambda p: p.device):
            desc = "" if port.description == port.device else f" — {port.description}"
            self.combo_port.addItem(f"{port.device}{desc}", port.device)
        if not ports:
            self.combo_port.addItem("Port topilmadi", "")
        else:
            last_port = self.settings_storage.value("last_port", "")
            if last_port:
                idx = self.combo_port.findData(last_port)
                if idx != -1:
                    self.combo_port.setCurrentIndex(idx)

    def _adjust_height(self):
        show_pwd = self.combo_auth.currentIndex() == 1
        manual = self.combo_meter.currentIndex() == 2
        h = 620
        if show_pwd:
            h += 55
        if manual:
            h += 75
        self.setFixedSize(520, h)

    def _on_meter_changed(self, index: int):
        _, baud, _ = METER_TYPES[index]
        manual = baud is None
        self.combo_baud.setVisible(manual)
        self.lbl_baud_header.setVisible(manual)
        
        self.lbl_parity.setVisible(manual)
        self.combo_parity.setVisible(manual)
        self.lbl_stopbits.setVisible(manual)
        self.combo_stopbits.setVisible(manual)

        if baud:
            self.combo_baud.setCurrentText(str(baud))
            self.combo_parity.setCurrentIndex(0)  # N
            self.combo_stopbits.setCurrentText("1")  # 1

        self._adjust_height()

    def _on_auth_changed(self, index: int):
        show_pwd = index == 1
        self.lbl_pwd.setVisible(show_pwd)
        self.txt_password.setVisible(show_pwd)
        self._adjust_height()

    def _on_open_flash(self):
        """ESP32 Flash oynasini ochadi (hisoblagich ulanishi shart emas)."""
        from .flash_window import FlashWindow
        from PyQt6.QtCore import Qt
        win = FlashWindow()
        self._flash_win = win
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        def _on_flash_closed():
            try:
                self.show()
            except RuntimeError:
                pass  # ConnectDialog allaqachon o'chirilgan (app yopilayapti)
        win.destroyed.connect(_on_flash_closed)
        self.hide()
        win.show()

    def _on_connect(self):
        port = self.combo_port.currentData()
        if not port:
            self.lbl_status.setText("COM port tanlanmagan")
            return

        self.result_port = port
        self.result_baud = int(self.combo_baud.currentText())
        self.result_auth = self.combo_auth.currentIndex()
        self.result_password = self.txt_password.text().strip() or "00000000"

        parity_map = {"N (None)": "N", "E (Even)": "E", "O (Odd)": "O"}
        self.result_parity = parity_map.get(self.combo_parity.currentText(), "N")
        self.result_stopbits = float(self.combo_stopbits.currentText())

        # Save to storage
        self.settings_storage.setValue("last_port", port)
        self.settings_storage.setValue("last_meter_index", self.combo_meter.currentIndex())
        self.settings_storage.setValue("last_auth_index", self.combo_auth.currentIndex())
        self.settings_storage.setValue("last_baud", self.combo_baud.currentText())
        self.settings_storage.setValue("last_parity", self.combo_parity.currentText())
        self.settings_storage.setValue("last_stopbits", self.combo_stopbits.currentText())

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
            "parity": getattr(self, "result_parity", "N"),
            "stopbits": getattr(self, "result_stopbits", 1.0),
        }
