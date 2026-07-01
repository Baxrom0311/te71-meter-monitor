"""Register browser — clean table with filters."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                              QTableWidgetItem, QPushButton, QLineEdit, QLabel,
                              QHeaderView, QComboBox, QFrame)
from PyQt6.QtCore import Qt


class RegistersPanel(QWidget):
    """Browse and read all meter registers."""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ===== Toolbar =====
        toolbar = QFrame()
        toolbar.setObjectName("card")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 12, 16, 12)
        tb_layout.setSpacing(12)

        self.btn_read_all = QPushButton("Registrlarni o'qish")
        self.btn_read_all.setObjectName("primary")
        self.btn_read_all.setEnabled(False)
        tb_layout.addWidget(self.btn_read_all)

        self.btn_export = QPushButton("Eksport (CSV)")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_csv)
        tb_layout.addWidget(self.btn_export)

        # Filter
        tb_layout.addSpacing(8)
        filter_lbl = QLabel("Filtr:")
        filter_lbl.setStyleSheet("color: #667085; font-weight: 700;")
        tb_layout.addWidget(filter_lbl)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "Hammasi",
            "Energiya",
            "Hozirgi qiymatlar",
            "Ma'lumot",
            "Rele",
        ])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        tb_layout.addWidget(self.filter_combo)

        tb_layout.addStretch()

        # Custom OBIS
        obis_lbl = QLabel("OBIS:")
        obis_lbl.setStyleSheet("color: #667085; font-weight: 700;")
        tb_layout.addWidget(obis_lbl)

        self.obis_input = QLineEdit()
        self.obis_input.setPlaceholderText("1.0.15.8.0.255")
        self.obis_input.setMaximumWidth(160)
        self.obis_input.setMinimumHeight(36)
        tb_layout.addWidget(self.obis_input)

        self.class_input = QLineEdit("3")
        self.class_input.setPlaceholderText("Class")
        self.class_input.setMaximumWidth(50)
        self.class_input.setMinimumHeight(36)
        tb_layout.addWidget(self.class_input)

        self.btn_read_custom = QPushButton("Bitta o'qish")
        self.btn_read_custom.setEnabled(False)
        tb_layout.addWidget(self.btn_read_custom)

        layout.addWidget(toolbar)

        # ===== Table =====
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "OBIS kod", "Nomi", "Qiymat", "Birlik", "Turi"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

        # Status
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #667085; font-size: 12px; padding: 4px;")
        layout.addWidget(self.lbl_status)

    def populate(self, data: list[dict]):
        self.table.setRowCount(len(data))
        for row, item in enumerate(data):
            self.table.setItem(row, 0, QTableWidgetItem(item["obis"]))

            name = item.get("name_uz") or item["name"]
            self.table.setItem(row, 1, QTableWidgetItem(name))

            val_item = QTableWidgetItem(str(item["value"]))
            if item["value"] == "N/A":
                val_item.setForeground(Qt.GlobalColor.darkGray)
            else:
                from PyQt6.QtGui import QColor
                val_item.setForeground(QColor("#10b981"))
            self.table.setItem(row, 2, val_item)

            self.table.setItem(row, 3, QTableWidgetItem(item["unit"]))

            cat_names = {
                "energy": "Energiya", "instant": "Hozirgi",
                "info": "Ma'lumot", "relay": "Rele",
                "time": "Vaqt", "system": "Tizim",
            }
            cat_display = cat_names.get(item["category"], item["category"])
            self.table.setItem(row, 4, QTableWidgetItem(cat_display))

            for col in range(5):
                wi = self.table.item(row, col)
                if wi:
                    wi.setData(Qt.ItemDataRole.UserRole, item["category"])

        ok_count = sum(1 for item in data if item["value"] != "N/A")
        self.lbl_status.setText(f"{len(data)} ta registr tekshirildi, {ok_count} tasi o'qildi")
        self.btn_export.setEnabled(self.table.rowCount() > 0)

    def add_custom_row(self, obis: str, class_id: int, value: str):
        row = self.table.rowCount()
        self.table.setRowCount(row + 1)
        self.table.setItem(row, 0, QTableWidgetItem(obis))
        self.table.setItem(row, 1, QTableWidgetItem("Qo'lda kiritilgan"))
        from PyQt6.QtGui import QColor
        val_item = QTableWidgetItem(value)
        val_item.setForeground(QColor("#38bdf8"))
        self.table.setItem(row, 2, val_item)
        self.table.setItem(row, 3, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem("Custom"))
        self.table.scrollToBottom()
        self.btn_export.setEnabled(True)

    def _apply_filter(self, index):
        cats = [None, "energy", "instant", "info", "relay"]
        cat = cats[index] if index < len(cats) else None
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                row_cat = item.data(Qt.ItemDataRole.UserRole)
                self.table.setRowHidden(row, cat is not None and row_cat != cat)

    def set_enabled(self, enabled: bool):
        self.btn_read_all.setEnabled(enabled)
        self.btn_read_custom.setEnabled(enabled)

    def clear(self):
        self.table.setRowCount(0)
        self.lbl_status.setText("")
        self.btn_export.setEnabled(False)

    def _export_csv(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import csv

        path, _ = QFileDialog.getSaveFileName(
            self, "CSV formatida saqlash", "", "CSV fayllar (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["OBIS kod", "Nomi", "Qiymat", "Birlik", "Turi"])

                for row in range(self.table.rowCount()):
                    if not self.table.isRowHidden(row):
                        obis = self.table.item(row, 0).text()
                        name = self.table.item(row, 1).text()
                        val = self.table.item(row, 2).text()
                        unit = self.table.item(row, 3).text()
                        cat = self.table.item(row, 4).text()
                        writer.writerow([obis, name, val, unit, cat])

            QMessageBox.information(self, "Muvaffaqiyat", f"Ma'lumotlar saqlandi:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Xato", f"Faylni saqlashda xato yuz berdi:\n{str(e)}")
