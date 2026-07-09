"""Dashboard page with clear meter readings.

Uses shared ValueCard component from ui.widgets.
Responsive layout dynamically rearranges grid based on window width.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from ui.widgets import ValueCard


class DashboardPanel(QWidget):
    """Main readings page (Responsive)."""

    def __init__(self):
        super().__init__()
        self.cards: dict[str, ValueCard] = {}
        self._is_3phase = False
        self._current_cols = 0

        self.instant_keys = [
            "voltage_l1", "current_l1", "power_active_plus",
            "frequency", "power_factor",
            "voltage_l2", "voltage_l3", "current_l2", "current_l3",
        ]
        self.energy_keys = ["energy_total", "energy_t1", "energy_t2", "energy_t3", "energy_t4"]

        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(12)

        self.main_layout.addWidget(self._section_title("Hozirgi ko'rsatkichlar"))
        self.instant_grid = QGridLayout()
        self.instant_grid.setSpacing(12)
        self.main_layout.addLayout(self.instant_grid)

        # Create all cards
        self.cards["voltage_l1"] = ValueCard("Kuchlanish", "V", tone="green", accent=True)
        self.cards["current_l1"] = ValueCard("Tok", "A", tone="green")
        self.cards["power_active_plus"] = ValueCard("Aktiv quvvat", "W", tone="green")
        self.cards["frequency"] = ValueCard("Chastota", "Hz", tone="amber")
        self.cards["power_factor"] = ValueCard("Quvvat koeff.", "cos phi", tone="amber")
        self.cards["voltage_l2"] = ValueCard("Kuchlanish L2", "V", tone="green")
        self.cards["voltage_l3"] = ValueCard("Kuchlanish L3", "V", tone="green")
        self.cards["current_l2"] = ValueCard("Tok L2", "A", tone="green")
        self.cards["current_l3"] = ValueCard("Tok L3", "A", tone="green")

        self.main_layout.addWidget(self._section_title("Energiya"))
        self.energy_grid = QGridLayout()
        self.energy_grid.setSpacing(12)
        self.main_layout.addLayout(self.energy_grid)

        self.cards["energy_total"] = ValueCard("Umumiy energiya", "kWh", tone="blue", accent=True)
        self.cards["energy_t1"] = ValueCard("Tarif 1", "kWh", tone="blue")
        self.cards["energy_t2"] = ValueCard("Tarif 2", "kWh", tone="blue")
        self.cards["energy_t3"] = ValueCard("Tarif 3", "kWh", tone="blue")
        self.cards["energy_t4"] = ValueCard("Tarif 4", "kWh", tone="blue")

        self.main_layout.addStretch()
        self.set_3phase(False)

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def set_3phase(self, is_3phase: bool):
        self._is_3phase = is_3phase
        for key in ("voltage_l2", "voltage_l3", "current_l2", "current_l3"):
            self.cards[key].setVisible(is_3phase)
        # Re-trigger layout rearrangement to place elements properly
        self._rearrange_layout(force=True)

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rearrange_layout()

    def _rearrange_layout(self, force=False):
        """Window kengligiga qarab grid ustunlari sonini responsive tarzda o'zgartiradi."""
        width = self.width()

        # Decide column count based on panel width
        if width < 520:
            cols = 1
        elif width < 820:
            cols = 2
        elif width < 1120:
            cols = 3
        else:
            cols = 4

        if cols == self._current_cols and not force:
            return
        self._current_cols = cols

        # 1. Rearrange Instant readings
        # Remove widgets from grid first
        for key in self.instant_keys:
            self.instant_grid.removeWidget(self.cards[key])

        visible_instant = []
        for key in self.instant_keys:
            # Skip L2/L3 voltage and current if single-phase (TE71)
            if key in ("voltage_l2", "voltage_l3", "current_l2", "current_l3") and not self._is_3phase:
                continue
            visible_instant.append(key)

        for index, key in enumerate(visible_instant):
            self.instant_grid.addWidget(self.cards[key], index // cols, index % cols)

        # Apply stretches
        for c in range(max(cols, 4)):
            self.instant_grid.setColumnStretch(c, 1 if c < cols else 0)

        # 2. Rearrange Energy readings
        for key in self.energy_keys:
            self.energy_grid.removeWidget(self.cards[key])

        for index, key in enumerate(self.energy_keys):
            self.energy_grid.addWidget(self.cards[key], index // cols, index % cols)

        for c in range(max(cols, 4)):
            self.energy_grid.setColumnStretch(c, 1 if c < cols else 0)
