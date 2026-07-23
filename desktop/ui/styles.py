"""ESP32 Studio — Modern Dark Theme & Visual Design System.

Cross-platform UI design system for PySide6 / PyQt6.
"""

DARK_THEME = """
* {
    font-family: "Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
    color: #e2e8f0;
}

QMainWindow, QDialog {
    background-color: #0b0f19;
}

QWidget {
    background-color: transparent;
}

/* ── Sidebar & Navigation ── */
QWidget#sidebar {
    background-color: #0f172a;
    border-right: 1px solid #1e293b;
}

QLabel#brandTitle {
    color: #38bdf8;
    font-size: 20px;
    font-weight: 900;
    letter-spacing: 0.5px;
}

QLabel#brandSubtitle {
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
}

QPushButton#navButton {
    background-color: transparent;
    color: #94a3b8;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0px;
    padding: 12px 18px;
    text-align: left;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#navButton:hover {
    background-color: #1e293b;
    color: #f8fafc;
}

QPushButton#navButton:checked {
    background-color: #1e293b;
    color: #38bdf8;
    border-left: 3px solid #38bdf8;
    font-weight: 700;
}

/* ── Cards & Containers ── */
QFrame#card {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
}

QFrame#card:hover {
    border-color: #334155;
}

QFrame#cardHeader {
    background-color: #1e293b;
    border-bottom: 1px solid #334155;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}

/* ── Headings & Labels ── */
QLabel#sectionTitle {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 800;
}

QLabel#sectionSub {
    color: #64748b;
    font-size: 12px;
}

QLabel#badgeTag {
    background-color: #0284c7;
    color: #ffffff;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 10px;
    font-weight: 800;
}

QLabel#badgeSuccess {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #059669;
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#badgeWarning {
    background-color: #78350f;
    color: #fbbf24;
    border: 1px solid #d97706;
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}

/* ── Buttons ── */
QPushButton {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #0f172a;
}

QPushButton:disabled {
    background-color: #0f172a;
    color: #475569;
    border-color: #1e293b;
}

QPushButton#btnPrimary {
    background-color: #0284c7;
    color: #ffffff;
    border: 1px solid #0369a1;
    font-weight: 700;
}

QPushButton#btnPrimary:hover {
    background-color: #0369a1;
    border-color: #075985;
}

QPushButton#btnSuccess {
    background-color: #10b981;
    color: #ffffff;
    border: 1px solid #059669;
    font-weight: 700;
}

QPushButton#btnSuccess:hover {
    background-color: #059669;
}

QPushButton#btnDanger {
    background-color: #ef4444;
    color: #ffffff;
    border: 1px solid #dc2626;
    font-weight: 700;
}

QPushButton#btnDanger:hover {
    background-color: #dc2626;
}

/* ── Inputs & Combo Boxes ── */
QLineEdit, QComboBox, QSpinBox {
    background-color: #0f172a;
    color: #f1f5f9;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 22px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #38bdf8;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    selection-background-color: #1e293b;
    selection-color: #38bdf8;
}

/* ── Terminal / Logs ── */
QTextEdit#terminalOutput {
    background-color: #020617;
    color: #38bdf8;
    border: 1px solid #1e293b;
    border-radius: 8px;
    font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    line-height: 1.4;
    padding: 10px;
}

/* ── Progress Bar ── */
QProgressBar {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-weight: 700;
    height: 20px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
    border-radius: 5px;
}

/* ── Tabs ── */
QTabWidget::pane {
    border: 1px solid #1e293b;
    background-color: #0b0f19;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #0f172a;
    color: #94a3b8;
    border: 1px solid #1e293b;
    padding: 8px 16px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: #1e293b;
    color: #38bdf8;
    border-bottom-color: #1e293b;
    font-weight: 700;
}

QTabBar::tab:hover {
    color: #f1f5f9;
}

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
}

QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
