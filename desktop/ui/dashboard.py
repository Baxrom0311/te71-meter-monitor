"""Dashboard panel with clear meter readings."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class ValueCard(QFrame):
    """Single measurement card with a small accent stripe."""

    def __init__(self, title: str, unit: str = "", tone: str = "green", accent: bool = False):
        super().__init__()
        self.setObjectName("metricCard")
        self.setProperty("accent", "true" if accent else "false")
        self.setMinimumHeight(118)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 16, 14)
        root.setSpacing(12)

        stripe = QFrame()
        stripe.setObjectName({
            "blue": "metricStripeBlue",
            "amber": "metricStripeAmber",
        }.get(tone, "metricStripeGreen"))
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

    def set_value(self, value: str, color: str | None = None):
        if color is None:
            color = {"blue": "#38bdf8", "amber": "#f59e0b"}.get(self._tone, "#10b981")
        self.value_label.setText(value)
        self.value_label.setStyleSheet(f"color: {color};")

    def clear(self):
        self.set_value("---", "#475569")


class DashboardPanel(QWidget):
    """Main readings page."""

    def __init__(self):
        super().__init__()
        self.cards: dict[str, ValueCard] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._section_title("Hozirgi ko'rsatkichlar"))
        instant_grid = QGridLayout()
        instant_grid.setSpacing(12)
        layout.addLayout(instant_grid)

        self.cards["voltage_l1"] = ValueCard("Kuchlanish", "V", tone="green", accent=True)
        self.cards["current_l1"] = ValueCard("Tok", "A", tone="green")
        self.cards["power_active_plus"] = ValueCard("Aktiv quvvat", "W", tone="green")
        self.cards["frequency"] = ValueCard("Chastota", "Hz", tone="amber")
        self.cards["power_factor"] = ValueCard("Quvvat koeff.", "cos phi", tone="amber")
        self.cards["voltage_l2"] = ValueCard("Kuchlanish L2", "V", tone="green")
        self.cards["voltage_l3"] = ValueCard("Kuchlanish L3", "V", tone="green")
        self.cards["current_l2"] = ValueCard("Tok L2", "A", tone="green")
        self.cards["current_l3"] = ValueCard("Tok L3", "A", tone="green")

        instant = [
            "voltage_l1", "current_l1", "power_active_plus", "frequency",
            "power_factor", "voltage_l2", "voltage_l3", "current_l2", "current_l3",
        ]
        for index, key in enumerate(instant):
            instant_grid.addWidget(self.cards[key], index // 5, index % 5)

        for col in range(5):
            instant_grid.setColumnStretch(col, 1)

        layout.addWidget(self._section_title("Energiya"))
        energy_grid = QGridLayout()
        energy_grid.setSpacing(12)
        layout.addLayout(energy_grid)

        self.cards["energy_total"] = ValueCard("Umumiy energiya", "kWh", tone="blue", accent=True)
        self.cards["energy_t1"] = ValueCard("Tarif 1", "kWh", tone="blue")
        self.cards["energy_t2"] = ValueCard("Tarif 2", "kWh", tone="blue")
        self.cards["energy_t3"] = ValueCard("Tarif 3", "kWh", tone="blue")
        self.cards["energy_t4"] = ValueCard("Tarif 4", "kWh", tone="blue")

        energy = ["energy_total", "energy_t1", "energy_t2", "energy_t3", "energy_t4"]
        for index, key in enumerate(energy):
            energy_grid.addWidget(self.cards[key], index // 5, index % 5)

        for col in range(5):
            energy_grid.setColumnStretch(col, 1)

        self.set_3phase(False)
        layout.addStretch()

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def set_3phase(self, is_3phase: bool):
        for key in ("voltage_l2", "voltage_l3", "current_l2", "current_l3"):
            self.cards[key].setVisible(is_3phase)

    def update_values(self, data: dict[str, tuple[str, object]]):
        for key, (formatted, _raw_val) in data.items():
            card = self.cards.get(key)
            if not card:
                continue
            parts = formatted.split()
            if parts and parts[0] != "N/A":
                card.set_value(parts[0])
            else:
                card.clear()

    def clear_values(self):
        for card in self.cards.values():
            card.clear()
