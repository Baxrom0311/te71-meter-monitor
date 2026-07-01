"""Premium modern dark theme for the meter application."""

APP_STYLE = """
* {
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog, QWidget {
    background: #070913;
    color: #e2e8f0;
}

QLabel {
    background: transparent;
}

QFrame#surface, QWidget#surface {
    background: #0b0f19;
}

QWidget#sidebar {
    background: #03050a;
    border-right: 1px solid #161e2e;
}

QWidget#sidebar QWidget,
QWidget#sidebar QLabel {
    background: transparent;
}

QLabel#brand {
    color: #38bdf8;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 0.5px;
}

QLabel#muted {
    color: #64748b;
    font-size: 12px;
}

QLabel#page_title {
    color: #ffffff;
    font-size: 24px;
    font-weight: 800;
}

QLabel#page_subtitle {
    color: #94a3b8;
    font-size: 13px;
}

QPushButton {
    background: #0f172a;
    color: #cbd5e1;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: 700;
}

QPushButton:hover {
    background: #1e293b;
    border-color: #38bdf8;
    color: #ffffff;
}

QPushButton:pressed {
    background: #0f172a;
}

QPushButton:disabled {
    color: #475569;
    background: #0f172a;
    border-color: #1e293b;
}

QPushButton#primary {
    background: #0284c7;
    color: #ffffff;
    border: 1px solid #0284c7;
}

QPushButton#primary:hover {
    background: #0369a1;
    border-color: #0369a1;
}

QPushButton#success {
    background: #059669;
    color: #ffffff;
    border: 1px solid #059669;
}

QPushButton#success:hover {
    background: #047857;
    border-color: #047857;
}

QPushButton#danger {
    background: #dc2626;
    color: #ffffff;
    border: 1px solid #dc2626;
}

QPushButton#danger:hover {
    background: #b91c1c;
    border-color: #b91c1c;
}

QPushButton#navButton {
    background: transparent;
    color: #94a3b8;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0;
    padding: 14px 20px;
    text-align: left;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#navButton:hover {
    background: #0f172a;
    color: #ffffff;
}

QPushButton#navButton:checked {
    background: #0f172a;
    color: #38bdf8;
    border-left: 3px solid #38bdf8;
}

QPushButton#sidebarDanger {
    background: transparent;
    color: #fca5a5;
    border: 1px solid #991b1b;
    border-radius: 6px;
    padding: 9px 12px;
}

QPushButton#sidebarDanger:hover {
    background: #991b1b;
    color: #ffffff;
}

QLineEdit, QComboBox {
    background: #0f172a;
    color: #ffffff;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 10px 14px;
    min-height: 24px;
}

QLineEdit:focus, QComboBox:focus {
    border-color: #38bdf8;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    background: #0f172a;
    color: #ffffff;
    border: 1px solid #1e293b;
    selection-background-color: #1e293b;
    selection-color: #38bdf8;
}

QFrame#card {
    background: #0b0f19;
    border: 1px solid #161e2e;
    border-radius: 12px;
}

QFrame#headerCard {
    background: #0b0f19;
    border: 1px solid #161e2e;
    border-radius: 12px;
}

QLabel#statusChipOk {
    color: #4ade80;
    background: rgba(74, 222, 128, 0.1);
    border: 1px solid rgba(74, 222, 128, 0.2);
    border-radius: 12px;
    padding: 4px 10px;
    font-weight: 700;
}

QLabel#smallLabel {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

QLabel#smallValue {
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
}

QFrame#metricCard {
    background: #0b0f19;
    border: 1px solid #161e2e;
    border-radius: 12px;
}

QFrame#metricCard[accent="true"] {
    border: 1px solid rgba(56, 189, 248, 0.4);
    background: #0e1626;
}

QFrame#metricStripeBlue {
    background: #38bdf8;
    border-radius: 2px;
}

QFrame#metricStripeGreen {
    background: #10b981;
    border-radius: 2px;
}

QFrame#metricStripeAmber {
    background: #f59e0b;
    border-radius: 2px;
}

QLabel#metricTitle {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

QLabel#metricValue {
    color: #ffffff;
    font-size: 26px;
    font-weight: 800;
    font-family: "Consolas", "Courier New", monospace;
}

QLabel#metricUnit {
    color: #64748b;
    font-size: 12px;
    font-weight: 600;
}

QLabel#sectionTitle {
    color: #e2e8f0;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 0.3px;
    margin-top: 6px;
}

QTableWidget {
    background: #0b0f19;
    color: #ffffff;
    border: 1px solid #161e2e;
    border-radius: 12px;
    gridline-color: #1e293b;
    selection-background-color: #1e293b;
    selection-color: #38bdf8;
}

QTableWidget::item {
    padding: 10px;
    border-bottom: 1px solid #161e2e;
}

QTableWidget::item:alternate {
    background: #0e1322;
}

QHeaderView::section {
    background: #03050a;
    color: #94a3b8;
    border: none;
    border-bottom: 2px solid #161e2e;
    padding: 10px;
    font-weight: 700;
}

QTextEdit, QPlainTextEdit {
    background: #03050a;
    color: #38bdf8;
    border: 1px solid #161e2e;
    border-radius: 12px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 12px;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
}

QScrollBar::handle:vertical {
    background: #1e293b;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #334155;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QStatusBar {
    background: #05070c;
    color: #94a3b8;
    border-top: 1px solid #161e2e;
}
"""

DARK_THEME = APP_STYLE
CONNECT_DIALOG_STYLE = APP_STYLE
