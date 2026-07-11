"""Register browser page.

Stillashtirish uchun theme.py konstantalari ishlatiladi.
"""
import csv

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                              QTableWidgetItem, QPushButton, QLineEdit, QLabel,
                              QHeaderView, QComboBox, QFrame, QFileDialog, QMessageBox)

from ui.theme import Colors, Fonts, inline_style


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
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 12, 16, 12)
        toolbar_layout.setSpacing(10)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        toolbar_layout.addLayout(action_layout)

        self.btn_read_all = QPushButton("Registrlarni o'qish")
        self.btn_read_all.setObjectName("primary")
        self.btn_read_all.setEnabled(False)
        action_layout.addWidget(self.btn_read_all)

        self.btn_export = QPushButton("Eksport (CSV)")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_csv)
        action_layout.addWidget(self.btn_export)
        action_layout.addStretch()

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        toolbar_layout.addLayout(filter_layout)

        # Filter
        filter_lbl = QLabel("Filtr:")
        filter_lbl.setStyleSheet(inline_style(color=Colors.TEXT_DIMMED, font_weight=Fonts.WEIGHT_BOLD))
        filter_layout.addWidget(filter_lbl)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "Hammasi",
            "Energiya",
            "Hozirgi qiymatlar",
            "Ma'lumot",
            "Rele",
        ])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter_and_search)
        filter_layout.addWidget(self.filter_combo)

        # Search Bar
        search_lbl = QLabel("Qidirish:")
        search_lbl.setStyleSheet(inline_style(color=Colors.TEXT_DIMMED, font_weight=Fonts.WEIGHT_BOLD))
        filter_layout.addWidget(search_lbl)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nomi yoki OBIS kodini yozing...")
        self.search_input.setMinimumHeight(36)
        self.search_input.textChanged.connect(self._apply_filter_and_search)
        filter_layout.addWidget(self.search_input, 1)

        custom_layout = QHBoxLayout()
        custom_layout.setSpacing(10)
        toolbar_layout.addLayout(custom_layout)

        # Custom OBIS
        obis_lbl = QLabel("OBIS:")
        obis_lbl.setStyleSheet(inline_style(color=Colors.TEXT_DIMMED, font_weight=Fonts.WEIGHT_BOLD))
        custom_layout.addWidget(obis_lbl)

        self.obis_input = QLineEdit()
        self.obis_input.setPlaceholderText("1.0.15.8.0.255")
        self.obis_input.setMinimumWidth(180)
        self.obis_input.setMaximumWidth(220)
        self.obis_input.setMinimumHeight(36)
        custom_layout.addWidget(self.obis_input)

        self.class_input = QLineEdit("3")
        self.class_input.setPlaceholderText("Class")
        self.class_input.setMaximumWidth(70)
        self.class_input.setMinimumHeight(36)
        custom_layout.addWidget(self.class_input)

        self.attr_input = QLineEdit("2")
        self.attr_input.setPlaceholderText("Attr")
        self.attr_input.setMaximumWidth(70)
        self.attr_input.setMinimumHeight(36)
        custom_layout.addWidget(self.attr_input)

        self.btn_read_custom = QPushButton("Bitta o'qish")
        self.btn_read_custom.setEnabled(False)
        custom_layout.addWidget(self.btn_read_custom)
        custom_layout.addStretch()

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
        self.lbl_status.setStyleSheet(inline_style(color=Colors.TEXT_DIMMED, font_size=Fonts.SIZE_BODY, padding="4px"))
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
                val_item.setForeground(QColor(Colors.STATUS_GREEN))
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

    def add_custom_row(self, obis: str, class_id: int, attr: int, value: str):
        row = self.table.rowCount()
        self.table.setRowCount(row + 1)
        self.table.setItem(row, 0, QTableWidgetItem(obis))
        self.table.setItem(row, 1, QTableWidgetItem(f"Qo'lda kiritilgan (class {class_id}, attr {attr})"))
        val_item = QTableWidgetItem(value)
        val_item.setForeground(QColor(Colors.ACCENT_BLUE))
        self.table.setItem(row, 2, val_item)
        self.table.setItem(row, 3, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem("Custom"))
        self.table.scrollToBottom()
        self.btn_export.setEnabled(True)

    def _apply_filter_and_search(self, *args):
        # Get category filter
        idx = self.filter_combo.currentIndex()
        cats = [None, "energy", "instant", "info", "relay"]
        cat = cats[idx] if idx < len(cats) else None

        # Get search text
        search_text = self.search_input.text().strip().lower()

        for row in range(self.table.rowCount()):
            # Read OBIS code and Name columns for searching
            obis_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)

            if obis_item and name_item:
                row_cat = obis_item.data(Qt.ItemDataRole.UserRole)
                obis = obis_item.text().lower()
                name = name_item.text().lower()

                # Checks
                category_matches = (cat is None or row_cat == cat)
                search_matches = (not search_text or search_text in obis or search_text in name)

                # Row visibility
                self.table.setRowHidden(row, not (category_matches and search_matches))

    def set_enabled(self, enabled: bool):
        self.btn_read_all.setEnabled(enabled)
        self.btn_read_custom.setEnabled(enabled)

    def clear(self):
        self.table.setRowCount(0)
        self.lbl_status.setText("")
        self.btn_export.setEnabled(False)

    def _export_csv(self):
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
