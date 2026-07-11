"""Clean operator-focused theme for the desktop application."""

APP_STYLE = """
* {
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog, QWidget {
    background: #f4f7fb;
    color: #172033;
}

QLabel {
    background: transparent;
}

QWidget#sidebar {
    background: #172033;
    border-right: 1px solid #101828;
}

QWidget#sidebar QWidget,
QWidget#sidebar QLabel {
    background: transparent;
}

QLabel#brand {
    color: #ffffff;
    font-size: 19px;
    font-weight: 800;
}

QLabel#page_title {
    color: #172033;
    font-size: 22px;
    font-weight: 800;
}

QLabel#page_subtitle {
    color: #667085;
    font-size: 13px;
}

QLabel#sectionTitle {
    color: #172033;
    font-size: 15px;
    font-weight: 800;
}

QPushButton {
    background: #ffffff;
    color: #172033;
    border: 1px solid #cfd8e6;
    border-radius: 8px;
    padding: 9px 15px;
    font-weight: 700;
}

QPushButton:hover {
    background: #eef4ff;
    border-color: #1769e0;
    color: #1455b8;
}

QPushButton:pressed {
    background: #e6edf6;
}

QPushButton:disabled {
    color: #98a2b3;
    background: #f2f4f7;
    border-color: #e4e7ec;
}

QPushButton#primary {
    background: #1769e0;
    color: #ffffff;
    border: 1px solid #1769e0;
}

QPushButton#primary:hover {
    background: #1455b8;
    border-color: #1455b8;
    color: #ffffff;
}

QPushButton#success {
    background: #0f8a4b;
    color: #ffffff;
    border: 1px solid #0f8a4b;
}

QPushButton#success:hover {
    background: #0b6f3d;
    border-color: #0b6f3d;
    color: #ffffff;
}

QPushButton#danger {
    background: #c03535;
    color: #ffffff;
    border: 1px solid #c03535;
}

QPushButton#danger:hover {
    background: #9f2626;
    border-color: #9f2626;
    color: #ffffff;
}

QPushButton#navButton {
    background: transparent;
    color: #d0d5dd;
    border: none;
    border-left: 4px solid transparent;
    border-radius: 0;
    padding: 13px 20px;
    text-align: left;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#navButton:hover {
    background: #24314a;
    color: #ffffff;
}

QPushButton#navButton:checked {
    background: #ffffff;
    color: #172033;
    border-left: 4px solid #1769e0;
}

QPushButton#sidebarDanger {
    background: transparent;
    color: #f2b8b8;
    border: 1px solid #6f2b2b;
    border-radius: 6px;
    padding: 9px 12px;
}

QPushButton#sidebarDanger:hover {
    background: #7a2e2e;
    color: #ffffff;
}

QLineEdit, QComboBox {
    background: #ffffff;
    color: #172033;
    border: 1px solid #cfd8e6;
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 24px;
}

QLineEdit:focus, QComboBox:focus {
    border-color: #1769e0;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    background: #ffffff;
    color: #172033;
    border: 1px solid #cfd8e6;
    selection-background-color: #eef4ff;
    selection-color: #1455b8;
}

QFrame#card, QFrame#headerCard {
    background: #ffffff;
    border: 1px solid #d9e2ef;
    border-radius: 8px;
}

QLabel#statusChipOk {
    color: #0f8a4b;
    background: #e9f8ef;
    border: 1px solid #bfe8cf;
    border-radius: 12px;
    padding: 4px 10px;
    font-weight: 700;
}

QLabel#smallLabel {
    color: #667085;
    font-size: 11px;
    font-weight: 700;
}

QLabel#smallValue {
    color: #172033;
    font-size: 13px;
    font-weight: 700;
}

QFrame#metricCard {
    background: #ffffff;
    border: 1px solid #d9e2ef;
    border-radius: 8px;
}

QFrame#metricCard:hover {
    border-color: #bad1f5;
    background: #f8fbff;
}

QFrame#metricCard[accent="true"] {
    border: 1px solid #bad1f5;
    background: #f8fbff;
}

QFrame#metricCard[accent="true"]:hover {
    border-color: #1769e0;
    background: #eef4ff;
}

QFrame#metricStripeBlue {
    background: #1769e0;
    border-radius: 2px;
}

QFrame#metricStripeGreen {
    background: #0f8a4b;
    border-radius: 2px;
}

QFrame#metricStripeAmber {
    background: #b7791f;
    border-radius: 2px;
}

QLabel#metricTitle {
    color: #667085;
    font-size: 11px;
    font-weight: 700;
}

QLabel#metricValue {
    color: #172033;
    font-size: 25px;
    font-weight: 800;
    font-family: "Consolas", "Courier New", monospace;
}

QLabel#metricUnit {
    color: #667085;
    font-size: 12px;
}

QTableWidget {
    background: #ffffff;
    color: #172033;
    border: 1px solid #d9e2ef;
    border-radius: 8px;
    gridline-color: #eef2f7;
    alternate-background-color: #f8fafc;
    selection-background-color: #eef4ff;
    selection-color: #1455b8;
}

QTableWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #eef2f7;
}

QHeaderView::section {
    background: #f8fafc;
    color: #667085;
    border: none;
    border-bottom: 1px solid #d9e2ef;
    padding: 9px 10px;
    font-weight: 800;
}

QTextEdit, QPlainTextEdit {
    background: #101828;
    color: #e4e7ec;
    border: 1px solid #26344f;
    border-radius: 8px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    padding: 8px;
}

QCheckBox {
    color: #344054;
    spacing: 8px;
    font-weight: 600;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #cfd8e6;
    border-radius: 4px;
    background: #ffffff;
}

QCheckBox::indicator:checked {
    background: #1769e0;
    border-color: #1769e0;
}

QScrollArea {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #cfd8e6;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #98a2b3;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    height: 0;
    background: transparent;
}
"""

DARK_THEME = APP_STYLE

CONNECT_DIALOG_STYLE = APP_STYLE + """
QDialog {
    background: #f4f7fb;
}
"""
