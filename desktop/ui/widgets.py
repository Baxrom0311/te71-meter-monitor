"""Shared UI widgets for the Meter Tool application.

Barcha qayta ishlatiladigan UI elementlar shu faylda jamlanadi.
Stillashtirish uchun theme.py dagi konstantalardan foydalaniladi.
"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QGraphicsDropShadowEffect

from ui.theme import Colors, Fonts, Spacing, inline_style


class SpinnerWidget(QWidget):
    """Circular Material-style flat spinner for loading animations."""

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
        pen.setColor(QColor(Colors.BORDER_MID))
        painter.setPen(pen)
        painter.drawEllipse(2, 2, side, side)

        # Rotating neon blue segment
        pen.setColor(QColor(Colors.ACCENT_BLUE))
        painter.setPen(pen)
        painter.drawArc(2, 2, side, side, -self.angle * 16, 120 * 16)


class ValueCard(QFrame):
    """Single measurement card with an accent stripe."""

    def __init__(self, title: str, unit: str = "", tone: str = "green", accent: bool = False):
        super().__init__()
        self.setObjectName("metricCard")
        self.setProperty("accent", "true" if accent else "false")
        self.setMinimumHeight(118)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 16, 14)
        root.setSpacing(12)

        stripe = QFrame()
        stripe_name = {
            "blue": "metricStripeBlue",
            "amber": "metricStripeAmber",
        }.get(tone, "metricStripeGreen")
        stripe.setObjectName(stripe_name)
        stripe.setFixedWidth(5)
        root.addWidget(stripe)

        body = QVBoxLayout()
        body.setSpacing(6)
        root.addLayout(body, 1)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("metricTitle")
        body.addWidget(self.title_label)

        self.value_label = QLabel("---")
        self.value_label.setObjectName("metricValue")
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.addWidget(self.value_label)

        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("metricUnit")
        body.addWidget(self.unit_label)

        self._tone = tone

        if accent:
            # Add glowing effect to primary/accent cards
            add_glow_effect(self, color_hex=Colors.ACCENT_BLUE, alpha=65, blur=18)

    def set_value(self, value: str, color: str | None = None):
        if color is None:
            color = {"blue": Colors.ACCENT_BLUE, "amber": Colors.STATUS_WARN}.get(self._tone, Colors.STATUS_GREEN)
        self.value_label.setText(value)
        self.value_label.setStyleSheet(inline_style(color=color))

    def clear(self):
        self.set_value("---", "#475569")


class InfoCard(QFrame):
    """Small read-only information card for system settings."""

    def __init__(self, label: str):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(5)

        title = QLabel(label)
        title.setObjectName("metricTitle")
        layout.addWidget(title)

        self.value_label = QLabel("---")
        self.value_label.setStyleSheet(inline_style(font_size=Fonts.SIZE_TITLE, font_weight=Fonts.WEIGHT_BOLD, color=Colors.ACCENT_BLUE))
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.value_label)

    def set_value(self, text: str):
        self.value_label.setText(text or "---")


class RelayDiagramWidget(QWidget):
    """Graphical circuit breaker contact switch diagram."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connected = None  # None = unknown, True = closed, False = open
        self.setMinimumSize(280, 100)
        self.setMaximumSize(360, 120)

    def set_state(self, connected: bool | None):
        self.connected = connected
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cy = h / 2

        # Draw transparent card container background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#03050a"))
        painter.drawRoundedRect(0, 0, w, h, 8, 8)

        # Draw wire lines
        pen = QPen(QColor(Colors.BORDER_MID), 3)
        painter.setPen(pen)

        # Left wire: from w/2-100 to w/2-50
        lx1, lx2 = int(w/2 - 100), int(w/2 - 50)
        painter.drawLine(lx1, int(cy), lx2, int(cy))

        # Right wire: from w/2+50 to w/2+100
        rx1, rx2 = int(w/2 + 50), int(w/2 + 100)
        painter.drawLine(rx1, int(cy), rx2, int(cy))

        # Text labels
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font)

        # Kirish / INPUT
        painter.setPen(QColor(Colors.TEXT_MUTED))
        painter.drawText(lx1, int(cy - 12), "KIRISH")

        # Yuklama / LOAD
        painter.drawText(int(rx2 - 50), int(cy - 12), "CHIQISH")

        # Switch terminals (Circles)
        painter.setBrush(QColor(Colors.BORDER_MID))
        painter.setPen(QPen(QColor(Colors.BORDER_DARK), 2))
        painter.drawEllipse(lx2 - 6, int(cy - 6), 12, 12)
        painter.drawEllipse(rx1 - 6, int(cy - 6), 12, 12)

        # State dependent arm drawing
        if self.connected is True:
            # CLOSED contact - neon green horizontal line connecting terminals
            pen_arm = QPen(QColor(Colors.STATUS_GREEN), 4)
            painter.setPen(pen_arm)
            painter.drawLine(lx2, int(cy), rx1, int(cy))

            # Status dot
            painter.setBrush(QColor(Colors.STATUS_GREEN))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(w/2 - 5), int(h - 22), 10, 10)
            painter.setPen(QColor(Colors.STATUS_GREEN))
            painter.drawText(int(w/2 + 10), int(h - 13), "ZANJIR YOPILGAN (ON)")

        elif self.connected is False:
            # OPEN contact - neon red line pointing up 35 degrees
            pen_arm = QPen(QColor(Colors.STATUS_ERROR), 4)
            painter.setPen(pen_arm)
            # End points calculations: dx = 80, dy = -45
            painter.drawLine(lx2, int(cy), int(lx2 + 70), int(cy - 35))

            # Status dot
            painter.setBrush(QColor(Colors.STATUS_ERROR))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(w/2 - 5), int(h - 22), 10, 10)
            painter.setPen(QColor(Colors.STATUS_ERROR))
            painter.drawText(int(w/2 + 10), int(h - 13), "ZANJIR OCHILGAN (OFF)")

        else:
            # Unknown state - grey dashed line
            pen_arm = QPen(QColor(Colors.TEXT_DIMMED), 3, Qt.PenStyle.DashLine)
            painter.setPen(pen_arm)
            painter.drawLine(lx2, int(cy), rx1, int(cy))

            # Status dot
            painter.setBrush(QColor(Colors.TEXT_DIMMED))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(w/2 - 5), int(h - 22), 10, 10)
            painter.setPen(QColor(Colors.TEXT_DIMMED))
            painter.drawText(int(w/2 + 10), int(h - 13), "NOMA'LUM STATUS")


def add_glow_effect(widget, color_hex: str, alpha: int = 60, blur: int = 15):
    """Adds a modern glowing neon effect around a widget using QGraphicsDropShadowEffect."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    color = QColor(color_hex)
    color.setAlpha(alpha)
    effect.setColor(color)
    effect.setOffset(0, 0)
    widget.setGraphicsEffect(effect)


def add_deep_shadow(widget, blur: int = 20):
    """Adds a smooth dark shadow for depth feeling."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setColor(QColor(0, 0, 0, 120))
    effect.setOffset(0, 4)
    widget.setGraphicsEffect(effect)

