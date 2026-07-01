"""Relay control panel."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

class SpinnerWidget(QWidget):
    """Modern circular Material-style flat spinner."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(16)  # ~60 FPS smooth animation
        self.setMinimumSize(40, 40)
        self.setMaximumSize(40, 40)

    def rotate(self):
        self.angle = (self.angle + 6) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        side = min(width, height) - 4
        
        pen = QPen()
        pen.setWidth(4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        
        # Track ring
        pen.setColor(QColor("#1e293b"))
        painter.setPen(pen)
        painter.drawEllipse(2, 2, side, side)
        
        # Rotating neon blue segment
        pen.setColor(QColor("#38bdf8"))
        painter.setPen(pen)
        painter.drawArc(2, 2, side, side, -self.angle * 16, 120 * 16)


class RelayPanel(QWidget):
    """Clear relay status and controls."""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.status_card = QFrame()
        self.status_card.setObjectName("card")
        self.status_card.setMinimumHeight(170)
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(24, 20, 24, 20)
        status_layout.setSpacing(8)

        self.lbl_state = QLabel("Holat noma'lum")
        self.lbl_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_state.setStyleSheet("font-size: 30px; font-weight: 800; color: #94a3b8;")
        status_layout.addWidget(self.lbl_state)

        self.lbl_desc = QLabel("Rele holatini o'qish uchun 'Holatni yangilash' tugmasini bosing.")
        self.lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("font-size: 14px; color: #94a3b8;")
        status_layout.addWidget(self.lbl_desc)

        self.spinner = SpinnerWidget()
        self.spinner.setVisible(False)

        self.spinner_layout = QHBoxLayout()
        self.spinner_layout.addStretch()
        self.spinner_layout.addWidget(self.spinner)
        self.spinner_layout.addStretch()
        status_layout.addLayout(self.spinner_layout)

        layout.addWidget(self.status_card)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        self.btn_reconnect = QPushButton("Releni yoqish")
        self.btn_reconnect.setObjectName("success")
        self.btn_reconnect.setMinimumHeight(52)
        self.btn_reconnect.setEnabled(False)
        button_row.addWidget(self.btn_reconnect)

        self.btn_disconnect = QPushButton("Releni o'chirish")
        self.btn_disconnect.setObjectName("danger")
        self.btn_disconnect.setMinimumHeight(52)
        self.btn_disconnect.setEnabled(False)
        button_row.addWidget(self.btn_disconnect)

        self.btn_refresh = QPushButton("Holatni yangilash")
        self.btn_refresh.setMinimumHeight(52)
        self.btn_refresh.setEnabled(False)
        button_row.addWidget(self.btn_refresh)

        layout.addLayout(button_row)

        details = QHBoxLayout()
        details.setSpacing(12)
        self.lbl_control_state = self._detail_card(details, "Boshqaruv holati")
        self.lbl_control_mode = self._detail_card(details, "Boshqaruv rejimi")
        layout.addLayout(details)

        mode_card = QFrame()
        mode_card.setObjectName("card")
        mode_layout = QHBoxLayout(mode_card)
        mode_layout.setContentsMargins(18, 14, 18, 14)
        mode_layout.setSpacing(12)

        mode_lbl = QLabel("Rele ish rejimini o'zgartirish:")
        mode_lbl.setStyleSheet("font-weight: 700; color: #344054;")
        mode_layout.addWidget(mode_lbl)

        from PyQt6.QtWidgets import QComboBox
        self.combo_mode = QComboBox()
        self.combo_mode.setMinimumHeight(40)
        self.combo_mode.addItems([
            "0: None (Boshqaruvsiz)",
            "1: Disconnect/Reconnect",
            "2: Local disconnect + Remote reconnect",
            "3: Remote disconnect + Local reconnect",
            "4: Remote disconnect + Remote/Local reconnect",
            "5: Remote disconnect + Reconnect (Tavsiya etiladi)",
            "6: Local disconnect + Local/Remote reconnect"
        ])
        self.combo_mode.setCurrentIndex(5)
        mode_layout.addWidget(self.combo_mode, 1)

        self.btn_set_mode = QPushButton("Rejimni yozish")
        self.btn_set_mode.setMinimumHeight(40)
        self.btn_set_mode.setEnabled(False)
        mode_layout.addWidget(self.btn_set_mode)

        layout.addWidget(mode_card)

        note = QLabel(
            "Eslatma: rele buyrug'i Reader rejimida yuboriladi. Dastur kerak bo'lsa shu rejimga avtomatik o'tadi."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #667085;")
        layout.addWidget(note)
        layout.addStretch()

    def _detail_card(self, parent_layout: QHBoxLayout, title: str) -> QLabel:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(5)

        lbl = QLabel(title)
        lbl.setObjectName("metricTitle")
        layout.addWidget(lbl)

        value = QLabel("---")
        value.setStyleSheet("font-size: 16px; font-weight: 700; color: #111827;")
        value.setWordWrap(True)
        layout.addWidget(value)

        parent_layout.addWidget(card)
        return value

    def update_status(self, output_state: bool, control_text: str, mode_text: str, control_mode: int = 5):
        if output_state:
            self.lbl_state.setText("YOQILGAN")
            self.lbl_state.setStyleSheet("font-size: 30px; font-weight: 800; color: #10b981;")
            self.lbl_desc.setText("Elektr uzatilmoqda. Hisoblagich relesi ulangan.")
            self.lbl_desc.setStyleSheet("font-size: 14px; color: #a7f3d0;")
            self.status_card.setStyleSheet(
                "QFrame#card { background: rgba(16, 185, 129, 0.1); border: 2px solid #10b981; border-radius: 12px; }"
            )
        else:
            self.lbl_state.setText("O'CHIRILGAN")
            self.lbl_state.setStyleSheet("font-size: 30px; font-weight: 800; color: #f87171;")
            self.lbl_desc.setText("Elektr uzatilmayapti. Kerak bo'lsa releni yoqing.")
            self.lbl_desc.setStyleSheet("font-size: 14px; color: #fca5a5;")
            self.status_card.setStyleSheet(
                "QFrame#card { background: rgba(239, 68, 68, 0.1); border: 2px solid #f87171; border-radius: 12px; }"
            )

        self.lbl_control_state.setText(control_text)
        self.lbl_control_mode.setText(mode_text)
        if 0 <= control_mode <= 6:
            self.combo_mode.setCurrentIndex(control_mode)

    def set_enabled(self, enabled: bool):
        self.btn_reconnect.setEnabled(enabled)
        self.btn_disconnect.setEnabled(enabled)
        self.btn_refresh.setEnabled(enabled)
        self.btn_set_mode.setEnabled(enabled)

    def confirm_action(self, action: str) -> bool:
        msg = QMessageBox(self)
        msg.setWindowTitle("Tasdiqlash")
        msg.setText(f"Releni {action} qilasizmi?")
        msg.setInformativeText("Bu amal elektr uzatilishiga bevosita ta'sir qiladi.")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        return msg.exec() == QMessageBox.StandardButton.Yes

    def show_loading(self, action: str):
        self.set_enabled(False)
        self.spinner.setVisible(True)
        self.status_card.setStyleSheet(
            "QFrame#card { background: rgba(56, 189, 248, 0.05); border: 2px dashed #1e293b; border-radius: 12px; }"
        )

        if action == "relay_reconnect":
            self.lbl_state.setText("YOQILMOQDA...")
            self.lbl_state.setStyleSheet("font-size: 30px; font-weight: 800; color: #38bdf8;")
            self.lbl_desc.setText("Rele yoqilmoqda. Jismoniy kontaktlar ulanishini kuting (1.5 soniya)...")
            self.lbl_desc.setStyleSheet("font-size: 14px; color: #94a3b8;")
        elif action == "relay_disconnect":
            self.lbl_state.setText("O'CHIRILMOQDA...")
            self.lbl_state.setStyleSheet("font-size: 30px; font-weight: 800; color: #38bdf8;")
            self.lbl_desc.setText("Rele o'chirilmoqda. Jismoniy kontaktlar uzilishini kuting (1.5 soniya)...")
            self.lbl_desc.setStyleSheet("font-size: 14px; color: #94a3b8;")
        else:
            self.lbl_state.setText("YANGILANMOQDA...")
            self.lbl_state.setStyleSheet("font-size: 30px; font-weight: 800; color: #38bdf8;")
            self.lbl_desc.setText("Rele holati o'qilmoqda, kuting...")
            self.lbl_desc.setStyleSheet("font-size: 14px; color: #94a3b8;")

    def hide_loading(self):
        self.spinner.setVisible(False)
        self.set_enabled(True)
