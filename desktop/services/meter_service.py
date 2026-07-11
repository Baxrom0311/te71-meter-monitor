"""Meter service — TE71/TE73 hisoblagich bilan ishlash.

Bu modul DLMS/COSEM protokoli orqali hisoblagichdan ma'lumotlarni o'qish,
relay boshqaruvi, vaqt sinxronizatsiya va parol o'zgartirish amallarini bajaradi.

Protocol Layer (dlms/) ustida qurilgan yuqori darajadagi abstraksiya.
UI yoki Qt haqida hech narsa bilmaydi.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from dlms.connection import DLMSConnection
from dlms.parser import parse_dlms_data, parse_scaler_unit, format_value, encode_datetime
from dlms.obis import (REGISTERS, Register, RELAY_OBIS, RELAY_CLASS,
                        DASHBOARD_1P, DASHBOARD_3P, ALL_REGISTER_KEYS)


@dataclass
class MeterInfo:
    serial: str = ""
    manufacturer: str = ""
    device_name: str = ""
    firmware: str = ""
    meter_type: str = "TE71"  # "TE71" or "TE73"


@dataclass
class RelayStatus:
    output_state: bool = False      # True = connected, False = disconnected
    control_state: int = 0          # 0=disconnected, 1=connected, 2=ready_for_reconnection
    control_mode: int = 0

    @property
    def output_text(self) -> str:
        return "YOQILGAN" if self.output_state else "O'CHIRILGAN"

    @property
    def control_text(self) -> str:
        states = {0: "Disconnected", 1: "Connected", 2: "Ready for reconnection"}
        return states.get(self.control_state, f"Unknown ({self.control_state})")

    @property
    def mode_text(self) -> str:
        modes = {
            0: "None", 1: "Disconnect/Reconnect",
            2: "Local disconnect + Remote reconnect",
            3: "Remote disconnect + Local reconnect",
            4: "Remote disconnect + Remote/Local reconnect",
            5: "Remote disconnect + Reconnect",
            6: "Local disconnect + Local/Remote reconnect",
        }
        return modes.get(self.control_mode, f"Mode {self.control_mode}")


class MeterService:
    """TE71/TE73 hisoblagich bilan barcha amallar uchun service.

    Bu klass transport qatlami (DLMSConnection) ustida ishlaydi va
    UI haqida hech narsa bilmaydi.
    """

    def __init__(self, conn: DLMSConnection):
        self.conn = conn
        self.info = MeterInfo()
        self._scalers: dict[str, tuple[int, str]] = {}
        self._on_log: Callable | None = None

    def set_log_callback(self, cb):
        self._on_log = cb

    def _log(self, msg: str):
        if self._on_log:
            self._on_log(msg)

    # ── Info ──────────────────────────────────────────────────────────────

    def read_info(self) -> MeterInfo:
        """Read meter identification info."""
        for key, field in [("serial", "serial"), ("manufacturer", "manufacturer"),
                           ("device_name", "device_name"), ("firmware", "firmware")]:
            reg = REGISTERS.get(key)
            if not reg:
                continue
            raw = self.conn.get_attribute(reg.class_id, reg.obis, reg.attr)
            if raw:
                val, _, _ = parse_dlms_data(raw)
                setattr(self.info, field, str(val) if val else "")

        # Detect TE73 by checking if L2 voltage register exists
        reg_l2 = REGISTERS.get("voltage_l2")
        if reg_l2:
            raw = self.conn.get_attribute(reg_l2.class_id, reg_l2.obis, reg_l2.attr)
            if raw:
                val, _, _ = parse_dlms_data(raw)
                if val is not None and isinstance(val, (int, float)) and val > 0:
                    self.info.meter_type = "TE73"
                else:
                    self.info.meter_type = "TE71"
            else:
                self.info.meter_type = "TE71"

        self._log(f"Hisoblagich: {self.info.meter_type}, Serial: {self.info.serial}")
        return self.info

    def read_scalers(self):
        """Read scaler/unit for key registers (attribute 3)."""
        scaler_keys = [
            key for key, reg in REGISTERS.items()
            if reg.class_id == 3 and reg.category in {"energy", "instant"}
        ]
        for key in scaler_keys:
            reg = REGISTERS.get(key)
            if not reg or reg.class_id != 3:
                continue
            raw = self.conn.get_attribute(reg.class_id, reg.obis, 3)
            if raw:
                scaler, unit = parse_scaler_unit(raw)
                self._scalers[key] = (scaler, unit)
                # Update register defaults if we got real data
                if scaler != 0 or unit:
                    reg.scaler = scaler
                    if unit:
                        reg.unit = unit

    # ── Register Reading ─────────────────────────────────────────────────

    def read_register(self, key: str) -> tuple:
        """Read a single register by key. Returns (formatted_value, raw_value, register)."""
        reg = REGISTERS.get(key)
        if not reg:
            return ("Unknown register", None, None)

        raw = self.conn.get_attribute(reg.class_id, reg.obis, reg.attr)
        if raw is None:
            return ("N/A", None, reg)

        val, tag, _ = parse_dlms_data(raw)
        formatted = format_value(val, reg.scaler, reg.unit)
        return (formatted, val, reg)

    def read_dashboard(self) -> dict[str, tuple[str, any]]:
        """Read all dashboard registers. Returns {key: (formatted, raw_value)}."""
        keys = DASHBOARD_3P if self.info.meter_type == "TE73" else DASHBOARD_1P
        results = {}
        for key in keys:
            formatted, raw_val, reg = self.read_register(key)
            results[key] = (formatted, raw_val)
        return results

    def read_all_registers(self) -> list[dict]:
        """Read all known registers. Returns list of dicts with register info."""
        results = []
        for key in ALL_REGISTER_KEYS:
            reg = REGISTERS[key]
            # Skip 3-phase registers for TE71
            if reg.phases == "3p" and self.info.meter_type == "TE71":
                continue
            formatted, raw_val, _ = self.read_register(key)
            results.append({
                "key": key,
                "obis": reg.obis_str,
                "class_id": reg.class_id,
                "name": reg.name,
                "name_uz": reg.name_uz,
                "value": formatted,
                "raw": raw_val,
                "unit": reg.unit,
                "category": reg.category,
            })
        return results

    # ── Date/Time ────────────────────────────────────────────────────────

    def read_datetime(self) -> datetime | None:
        """Read meter date/time."""
        reg = REGISTERS["datetime"]
        raw = self.conn.get_attribute(reg.class_id, reg.obis, reg.attr)
        if raw:
            val, _, _ = parse_dlms_data(raw)
            if isinstance(val, datetime):
                return val
        return None

    def set_datetime(self, dt: datetime | None = None) -> bool:
        """Set meter date/time. Uses current time if dt is None."""
        if dt is None:
            dt = datetime.now()
        encoded = bytes([0x09, 0x0C]) + encode_datetime(dt)
        reg = REGISTERS["datetime"]
        result = self.conn.set_attribute(reg.class_id, reg.obis, reg.attr, encoded)
        if result:
            self._log(f"Vaqt o'rnatildi: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            self._log("Vaqt o'rnatish xatosi")
        return result

    # ── Password ─────────────────────────────────────────────────────────

    def change_password(self, new_password: str) -> bool:
        """Change the password for the current client association."""
        pwd_bytes = new_password.encode("ascii")
        encoded = bytes([0x09, len(pwd_bytes)]) + pwd_bytes
        client_id = self.conn.client_addr
        obis = (0, 0, 40, 0, client_id, 255)
        result = self.conn.set_attribute(15, obis, 7, encoded)
        if result:
            self._log(f"Parol o'rnatildi (Client {client_id})")
        else:
            self._log("Parol o'rnatish xatosi")
        return result

    # ── Relay ────────────────────────────────────────────────────────────

    def read_relay_status(self) -> RelayStatus:
        """Read relay/disconnect control status."""
        status = RelayStatus()

        # Attribute 2: output_state (boolean)
        raw = self.conn.get_attribute(RELAY_CLASS, RELAY_OBIS, 2)
        if raw:
            val, _, _ = parse_dlms_data(raw)
            status.output_state = bool(val)

        # Attribute 3: control_state (enum)
        raw = self.conn.get_attribute(RELAY_CLASS, RELAY_OBIS, 3)
        if raw:
            val, _, _ = parse_dlms_data(raw)
            if isinstance(val, int):
                status.control_state = val

        # Attribute 4: control_mode (enum)
        raw = self.conn.get_attribute(RELAY_CLASS, RELAY_OBIS, 4)
        if raw:
            val, _, _ = parse_dlms_data(raw)
            if isinstance(val, int):
                status.control_mode = val

        return status

    def relay_reconnect(self) -> bool:
        """Turn relay ON (remote_reconnect, method 2)."""
        success, code = self.conn.action(RELAY_CLASS, RELAY_OBIS, 2)
        if success:
            self._log("Rele YOQILDI")
        else:
            self._log(f"Rele yoqish xatosi (code={code})")
        return success

    def relay_disconnect(self) -> bool:
        """Turn relay OFF (remote_disconnect, method 1)."""
        success, code = self.conn.action(RELAY_CLASS, RELAY_OBIS, 1)
        if success:
            self._log("Rele O'CHIRILDI")
        else:
            self._log(f"Rele o'chirish xatosi (code={code})")
        return success

    def set_relay_mode(self, mode: int) -> bool:
        """Set the relay control mode (attribute 4, enum)."""
        encoded = bytes([0x16, mode])
        result = self.conn.set_attribute(RELAY_CLASS, RELAY_OBIS, 4, encoded)
        if result:
            self._log(f"Rele boshqaruv rejimi o'zgartirildi: {mode}")
        else:
            self._log("Rele boshqaruv rejimini o'zgartirish xatosi")
        return result
