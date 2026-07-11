"""MeterController — UI va MeterService o'rtasidagi ko'prik.

Bu modul QThread orqali serial kommunikatsiyani fon jarayonida bajarib,
natijalarni pyqtSignal orqali UI ga uzatadi.

Markaziy MeterState orqali dastur holatini boshqaradi.
"""
from dataclasses import dataclass, field
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

from dlms.connection import DLMSConnection
from dlms.parser import parse_dlms_data, format_value
from services.meter_service import MeterService, MeterInfo, RelayStatus


# ── Worker Thread ─────────────────────────────────────────────────────────────

class _MeterWorker(QThread):
    """Background thread — serial port bilan barcha aloqani shu yerda bajaradi.

    UI thread'ni bloklashning oldini oladi. Har bir amal MeterService
    orqali amalga oshiriladi.
    """
    finished = pyqtSignal(str, object)   # (action_name, result)
    error = pyqtSignal(str, str)         # (action_name, error_message)

    def __init__(self):
        super().__init__()
        self.service: MeterService | None = None
        self._action: str | None = None
        self._args: tuple = ()

    def run_action(self, action: str, *args):
        self._action = action
        self._args = args
        self.start()

    def run(self):
        if not self.service:
            self.error.emit(self._action, "MeterService not initialized")
            return
        try:
            result = self._dispatch()
            if result is not None:
                self.finished.emit(self._action, result)
        except Exception as e:
            self.error.emit(self._action, str(e))

    def _dispatch(self):
        """Amalni nomi bo'yicha bajaradi va natija qaytaradi."""
        svc = self.service

        if self._action == "read_info":
            info = svc.read_info()
            svc.read_scalers()
            return info

        elif self._action == "read_dashboard":
            return svc.read_dashboard()

        elif self._action == "read_all_registers":
            return svc.read_all_registers()

        elif self._action == "read_relay":
            return svc.read_relay_status()

        elif self._action == "relay_reconnect":
            ok = svc.relay_reconnect()
            if ok:
                self.msleep(1500)
            status = svc.read_relay_status()
            return (ok, status)

        elif self._action == "relay_disconnect":
            ok = svc.relay_disconnect()
            if ok:
                self.msleep(1500)
            status = svc.read_relay_status()
            return (ok, status)

        elif self._action == "read_time":
            return svc.read_datetime()

        elif self._action == "sync_time":
            ok = svc.set_datetime()
            dt = svc.read_datetime() if ok else None
            return (ok, dt)

        elif self._action == "change_password":
            new_pwd = self._args[0]
            return svc.change_password(new_pwd)

        elif self._action == "set_relay_mode":
            mode = self._args[0]
            ok = svc.set_relay_mode(mode)
            if ok:
                self.msleep(1000)
            status = svc.read_relay_status()
            return (ok, status)

        elif self._action == "read_custom":
            class_id, obis_tuple, attr = self._args
            raw = svc.conn.get_attribute(class_id, obis_tuple, attr)
            if raw:
                val, _, _ = parse_dlms_data(raw)
                return format_value(val)
            return "N/A"

        elif self._action == "reconnect":
            try:
                svc.conn.disconnect()
            except Exception:
                pass
            ok = svc.conn.reconnect()
            if ok:
                try:
                    svc.read_info()
                    svc.read_scalers()
                except Exception:
                    pass
            return ok

        return None


# ── Controller ────────────────────────────────────────────────────────────────

class MeterController(QObject):
    """UI va MeterService o'rtasidagi markaziy controller.

    Barcha serial aloqani worker thread orqali bajaradi va
    natijalarni signallar orqali UI ga uzatadi.

    UI bu controller'ga ulanadi va signallarni tinglaydi:
    - info_updated: MeterInfo o'qilganda
    - dashboard_updated: Dashboard ma'lumotlari yangilanganda
    - relay_updated: Relay holati o'qilganda
    - relay_action_done: Relay yoqish/o'chirish/rejim o'zgartirish tugaganda
    - registers_loaded: Barcha registrlar o'qilganda
    - time_read: Vaqt o'qilganda
    - time_synced: Vaqt sinxronlanganda
    - password_changed: Parol o'zgartirilganda
    - custom_register_read: Custom OBIS o'qilganda
    - reconnect_result: Qayta ulanish natijasi
    - connection_lost: Aloqa butunlay uzilganda (3 marta xato)
    - status_message: Pastki status satri uchun xabar
    - error_occurred: Har qanday xato yuz berganda
    """

    # ── Signallar ─────────────────────────────────────────────────────────
    info_updated = pyqtSignal(object)           # MeterInfo
    dashboard_updated = pyqtSignal(dict)         # {key: (formatted, raw)}
    relay_updated = pyqtSignal(object)           # RelayStatus
    relay_action_done = pyqtSignal(str, bool, object)  # (action, ok, RelayStatus)
    registers_loaded = pyqtSignal(list)          # [dict, ...]
    time_read = pyqtSignal(object)               # datetime | None
    time_synced = pyqtSignal(bool, object)       # (ok, datetime | None)
    password_changed = pyqtSignal(bool)          # ok
    custom_register_read = pyqtSignal(str)       # formatted value
    reconnect_result = pyqtSignal(bool)          # ok
    connection_lost = pyqtSignal()               # 3+ ketma-ket xato
    status_message = pyqtSignal(str, str)        # (message, css_color)
    error_occurred = pyqtSignal(str, str)        # (action, error_text)

    def __init__(self, conn: DLMSConnection, service: MeterService):
        super().__init__()
        self.conn = conn
        self.service = service

        self._worker = _MeterWorker()
        self._worker.service = service
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._pending: list[tuple[str, tuple]] = []
        self._consecutive_failures = 0

    @property
    def is_busy(self) -> bool:
        return self._worker.isRunning()

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    # ── Public API (UI bu metodlarni chaqiradi) ───────────────────────────

    def read_info(self):
        self._enqueue("read_info")

    def read_dashboard(self):
        self._enqueue("read_dashboard")

    def read_all_registers(self):
        self._enqueue("read_all_registers")

    def read_relay(self):
        self._enqueue("read_relay")

    def relay_reconnect(self):
        """Releni yoqish. Kerak bo'lsa Client 1 ga o'tadi."""
        if self.conn and self.conn.client_addr != 1:
            self.service._log("Rele uchun Client 1 ga o'tilmoqda...")
            self.conn.disconnect()
            if not self.conn.connect_reader():
                self.error_occurred.emit("relay_reconnect", "Client 1 ga ulanish xatosi!")
                return
        self._enqueue("relay_reconnect")

    def relay_disconnect(self):
        """Releni o'chirish. Kerak bo'lsa Client 1 ga o'tadi."""
        if self.conn and self.conn.client_addr != 1:
            self.conn.disconnect()
            if not self.conn.connect_reader():
                self.error_occurred.emit("relay_disconnect", "Client 1 ga ulanish xatosi!")
                return
        self._enqueue("relay_disconnect")

    def set_relay_mode(self, mode: int):
        """Rele ish rejimini o'zgartirish. Kerak bo'lsa Client 1 ga o'tadi."""
        if self.conn and self.conn.client_addr != 1:
            self.service._log("Rele rejimi uchun Client 1 ga o'tilmoqda...")
            self.conn.disconnect()
            if not self.conn.connect_reader():
                self.error_occurred.emit("set_relay_mode", "Client 1 ga ulanish xatosi!")
                return
        self._enqueue("set_relay_mode", mode)

    def read_time(self):
        self._enqueue("read_time")

    def sync_time(self):
        self._enqueue("sync_time")

    def change_password(self, new_password: str):
        self._enqueue("change_password", new_password)

    def read_custom_register(self, class_id: int, obis_tuple: tuple, attr: int = 2):
        self._enqueue("read_custom", class_id, obis_tuple, attr)

    def reconnect(self):
        self._enqueue("reconnect")

    def stop(self):
        """Worker'ni to'xtatish (dastur yopilayotganda)."""
        if self._worker.isRunning():
            self._worker.wait(3000)

    # ── Queue Management ──────────────────────────────────────────────────

    def _enqueue(self, action: str, *args):
        if self._worker.isRunning():
            if not any(item[0] == action for item in self._pending):
                self._pending.append((action, args))
                self.status_message.emit(f"Navbatda: {action}", "#667085")
            return
        self.status_message.emit(f"Ishlayapti: {action}...", "#1663d8")
        self._worker.run_action(action, *args)

    def _drain_queue(self):
        if self._worker.isRunning() or not self._pending:
            return
        action, args = self._pending.pop(0)
        self._enqueue(action, *args)

    # ── Signal Handlers ───────────────────────────────────────────────────

    def _on_finished(self, action: str, result):
        self._consecutive_failures = 0
        self.status_message.emit("Tayyor", "#667085")

        if action == "read_info":
            self.info_updated.emit(result)

        elif action == "read_dashboard":
            self.dashboard_updated.emit(result)

        elif action == "read_all_registers":
            self.registers_loaded.emit(result)

        elif action == "read_relay":
            self.relay_updated.emit(result)

        elif action in ("relay_reconnect", "relay_disconnect"):
            ok, status = result
            self.relay_action_done.emit(action, ok, status)

        elif action == "set_relay_mode":
            ok, status = result
            self.relay_action_done.emit(action, ok, status)

        elif action == "read_time":
            self.time_read.emit(result)

        elif action == "sync_time":
            ok, dt = result
            self.time_synced.emit(ok, dt)

        elif action == "change_password":
            self.password_changed.emit(result)

        elif action == "read_custom":
            self.custom_register_read.emit(str(result))

        elif action == "reconnect":
            self.reconnect_result.emit(result)

        QTimer.singleShot(80, self._drain_queue)

    def _on_error(self, action: str, error_text: str):
        self.error_occurred.emit(action, error_text)

        # Track consecutive failures for connection-related actions
        if action in ("read_info", "read_dashboard", "read_relay", "read_time", "reconnect"):
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                self.connection_lost.emit()

        QTimer.singleShot(80, self._drain_queue)
