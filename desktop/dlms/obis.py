"""OBIS code registry for TE71 (single-phase) and TE73 (three-phase) meters."""
from dataclasses import dataclass, field


@dataclass
class Register:
    class_id: int
    obis: tuple[int, ...]
    name: str
    name_uz: str = ""
    attr: int = 2           # default attribute to read (2=value)
    scaler: int = 0         # 10^scaler multiplier (0=no scaling, -1=divide by 10, etc.)
    unit: str = ""
    category: str = "other"
    phases: str = "all"     # "all", "1p" (TE71 only), "3p" (TE73 only)
    writable: bool = False

    @property
    def obis_str(self) -> str:
        return ".".join(str(x) for x in self.obis)

    @property
    def obis_short(self) -> str:
        """Short OBIS without leading 1.0. and trailing .255."""
        o = self.obis
        if len(o) == 6:
            if o[0] in (0, 1) and o[5] == 255:
                return ".".join(str(x) for x in o[1:5] if True)
        return self.obis_str


# Complete register map
REGISTERS: dict[str, Register] = {}

def _r(key, class_id, obis, name, name_uz="", unit="", scaler=0, category="other",
       phases="all", attr=2, writable=False):
    REGISTERS[key] = Register(
        class_id=class_id, obis=obis, name=name, name_uz=name_uz,
        attr=attr, scaler=scaler, unit=unit, category=category,
        phases=phases, writable=writable,
    )

# ===== Identification =====
_r("serial",       1, (0,0,96,1,0,255),  "Serial Number",      "Seriya raqami",    category="info")
_r("manufacturer", 1, (0,0,96,1,1,255),  "Manufacturer",       "Ishlab chiqaruvchi",category="info")
_r("device_name",  1, (0,0,42,0,0,255),  "Device Name",        "Qurilma nomi",     category="info")
_r("firmware",     1, (1,0,0,2,0,255),   "Firmware Version",   "Firmware versiya",  category="info")

# ===== Date/Time =====
_r("datetime",     8, (0,0,1,0,0,255),   "Date/Time",          "Sana/Vaqt",        category="time")

# ===== Total Energy =====
_r("energy_total", 3, (1,0,15,8,0,255),  "Total Energy |A|",   "Umumiy energiya",  unit="Wh", scaler=-2, category="energy")
_r("energy_t1",    3, (1,0,15,8,1,255),  "Energy Tariff 1",    "Tarif 1",          unit="Wh", scaler=-2, category="energy")
_r("energy_t2",    3, (1,0,15,8,2,255),  "Energy Tariff 2",    "Tarif 2",          unit="Wh", scaler=-2, category="energy")
_r("energy_t3",    3, (1,0,15,8,3,255),  "Energy Tariff 3",    "Tarif 3",          unit="Wh", scaler=-2, category="energy")
_r("energy_t4",    3, (1,0,15,8,4,255),  "Energy Tariff 4",    "Tarif 4",          unit="Wh", scaler=-2, category="energy")

# ===== Import/Export Energy =====
_r("import_active",   3, (1,0,1,8,0,255), "Import A+",         "Import A+",        unit="Wh", scaler=-2, category="energy")
_r("import_active_t1",3, (1,0,1,8,1,255), "Import A+ T1",      "Import A+ T1",     unit="Wh", scaler=-2, category="energy")
_r("import_active_t2",3, (1,0,1,8,2,255), "Import A+ T2",      "Import A+ T2",     unit="Wh", scaler=-2, category="energy")
_r("import_active_t3",3, (1,0,1,8,3,255), "Import A+ T3",      "Import A+ T3",     unit="Wh", scaler=-2, category="energy")
_r("import_active_t4",3, (1,0,1,8,4,255), "Import A+ T4",      "Import A+ T4",     unit="Wh", scaler=-2, category="energy")
_r("export_active",   3, (1,0,2,8,0,255), "Export A-",          "Eksport A-",       unit="Wh", scaler=-2, category="energy")
_r("reactive_plus",   3, (1,0,3,8,0,255), "Reactive Q+",       "Reaktiv Q+",       unit="VARh", scaler=-2, category="energy")
_r("reactive_minus",  3, (1,0,4,8,0,255), "Reactive Q-",       "Reaktiv Q-",       unit="VARh", scaler=-2, category="energy")

# ===== Instantaneous - Voltage =====
_r("voltage_l1", 3, (1,0,32,7,0,255), "Voltage L1",    "Kuchlanish L1", unit="V",   scaler=-1, category="instant")
_r("voltage_l2", 3, (1,0,52,7,0,255), "Voltage L2",    "Kuchlanish L2", unit="V",   scaler=-1, category="instant", phases="3p")
_r("voltage_l3", 3, (1,0,72,7,0,255), "Voltage L3",    "Kuchlanish L3", unit="V",   scaler=-1, category="instant", phases="3p")

# ===== Instantaneous - Current =====
_r("current_l1", 3, (1,0,31,7,0,255), "Current L1",    "Tok L1",        unit="A",   scaler=-3, category="instant")
_r("current_l2", 3, (1,0,51,7,0,255), "Current L2",    "Tok L2",        unit="A",   scaler=-3, category="instant", phases="3p")
_r("current_l3", 3, (1,0,71,7,0,255), "Current L3",    "Tok L3",        unit="A",   scaler=-3, category="instant", phases="3p")
_r("current_total",3,(1,0,11,7,0,255),"Current Total",  "Tok (umumiy)",  unit="A",   scaler=-3, category="instant")
_r("current_neutral",3,(1,0,91,7,0,255),"Current Neutral","Tok (neytral)",unit="A",  scaler=-3, category="instant")

# ===== Instantaneous - Power =====
_r("power_active_plus",  3, (1,0,1,7,0,255), "Active Power P+",  "Aktiv quvvat P+",  unit="W", scaler=0, category="instant")
_r("power_active_minus", 3, (1,0,2,7,0,255), "Active Power P-",  "Aktiv quvvat P-",  unit="W", scaler=0, category="instant")
_r("power_reactive_plus",3, (1,0,3,7,0,255), "Reactive Power Q+","Reaktiv Q+",        unit="VAR",scaler=0,category="instant")
_r("power_reactive_minus",3,(1,0,4,7,0,255), "Reactive Power Q-","Reaktiv Q-",        unit="VAR",scaler=0,category="instant")
_r("power_apparent",     3, (1,0,9,7,0,255), "Apparent Power S", "To'la quvvat S",   unit="VA", scaler=0, category="instant")

# ===== Instantaneous - Other =====
_r("power_factor", 3, (1,0,13,7,0,255), "Power Factor",  "Quvvat koeffitsienti", unit="", scaler=-3, category="instant")
_r("frequency",    3, (1,0,14,7,0,255), "Frequency",     "Chastota",             unit="Hz", scaler=-2, category="instant")

# ===== Relay / Disconnect Control =====
_r("relay_state",   70, (0,0,96,3,10,255), "Relay Output State",   "Rele holati",      category="relay", attr=2)
_r("relay_control", 70, (0,0,96,3,10,255), "Relay Control State",  "Boshqaruv holati", category="relay", attr=3)
_r("relay_mode",    70, (0,0,96,3,10,255), "Relay Control Mode",   "Boshqaruv rejimi", category="relay", attr=4)

# ===== Association =====
# Attribute 2 is the COSEM object list. It is not a normal scalar register and
# can be large or inaccessible depending on the client, so it is intentionally
# excluded from the default "read all registers" flow.
_r("assoc_ln_1", 15, (0,0,40,0,1,255), "Association LN 1", "Assotsiatsiya 1", category="system")

# Disconnect control OBIS (used for relay actions)
RELAY_OBIS = (0, 0, 96, 3, 10, 255)
RELAY_CLASS = 70

# Dashboard register keys for quick reading
DASHBOARD_1P = [
    "voltage_l1", "current_l1", "power_active_plus", "frequency",
    "power_factor", "energy_total", "energy_t1", "energy_t2", "energy_t3", "energy_t4",
]

DASHBOARD_3P = [
    "voltage_l1", "voltage_l2", "voltage_l3",
    "current_l1", "current_l2", "current_l3",
    "power_active_plus", "frequency", "power_factor",
    "energy_total", "energy_t1", "energy_t2", "energy_t3", "energy_t4",
]

ALL_REGISTER_KEYS = [key for key in REGISTERS.keys() if key != "assoc_ln_1"]
