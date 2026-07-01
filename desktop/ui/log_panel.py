"""Communication log panel."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                              QPushButton, QLabel, QCheckBox, QFrame)
from PyQt6.QtCore import Qt
from datetime import datetime


class LogPanel(QWidget):
    """HDLC communication and application log."""

    def __init__(self):
        super().__init__()
        self._max_lines = 3000
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("card")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 10, 16, 10)
        tb_layout.setSpacing(12)

        self.chk_show_tx = QCheckBox("TX yuborish")
        self.chk_show_tx.setChecked(True)
        tb_layout.addWidget(self.chk_show_tx)

        self.chk_show_rx = QCheckBox("RX qabul qilish")
        self.chk_show_rx.setChecked(True)
        tb_layout.addWidget(self.chk_show_rx)

        tb_layout.addStretch()

        self.btn_clear = QPushButton("Tozalash")
        self.btn_clear.clicked.connect(self._clear_all)
        tb_layout.addWidget(self.btn_clear)

        self.btn_copy = QPushButton("Nusxa olish")
        self.btn_copy.clicked.connect(self._copy_log)
        tb_layout.addWidget(self.btn_copy)

        self.btn_save = QPushButton("Faylga saqlash")
        self.btn_save.clicked.connect(self._save_log)
        tb_layout.addWidget(self.btn_save)

        layout.addWidget(toolbar)

        # Log area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

    def add_tx(self, hex_data: str):
        if self.chk_show_tx.isChecked():
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.log_area.append(
                f'<span style="color:#ff8844;">[{ts}] TX \u2192 {hex_data}</span>'
            )
            self._trim()

    def add_rx(self, hex_data: str):
        if self.chk_show_rx.isChecked():
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.log_area.append(
                f'<span style="color:#44ff88;">[{ts}] RX \u2190 {hex_data}</span>'
            )
            self._trim()

    def add_app_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(
            f'<span style="color:#7a8aaa;">[{ts}]</span> '
            f'<span style="color:#e8eaed;">{msg}</span>'
        )
        self._trim()

    def _trim(self):
        doc = self.log_area.document()
        if doc.blockCount() > self._max_lines:
            cursor = self.log_area.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor,
                                doc.blockCount() - self._max_lines)
            cursor.removeSelectedText()

    def _clear_all(self):
        self.log_area.clear()

    def _copy_log(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.log_area.toPlainText())

    def _save_log(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        path, _ = QFileDialog.getSaveFileName(
            self, "Log faylini saqlash", "", "Matnli fayllar (*.txt *.log)"
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_area.toPlainText())
            QMessageBox.information(self, "Muvaffaqiyat", f"Log saqlandi:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Xato", f"Faylni saqlashda xato yuz berdi:\n{str(e)}")
