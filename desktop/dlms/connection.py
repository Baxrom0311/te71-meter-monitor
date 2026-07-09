"""DLMS/COSEM connection manager over HDLC/RS-485."""
import os
import serial
import time
from typing import Callable

from .hdlc import make_hdlc, send_recv, hex_str

LLC = b"\xE6\xE6\x00"

# Client address -> HDLC source byte: (addr << 1) | 1
CLIENT_PUBLIC = 16   # 0x21 - no auth
CLIENT_READER = 1    # 0x03 - HLS5 (read + relay)
CLIENT_MANAGER = 2   # 0x05 - LOW auth (read)


def _client_to_hdlc(client_addr: int) -> int:
    return (client_addr << 1) | 1


class DLMSConnection:
    """Manages DLMS/COSEM connection to a TE71/TE73 meter."""

    def __init__(self, port: str, baud: int = 9600, server_addr: int = 0x03, parity: str = 'N', stopbits: float = 1.0):
        self.port = port
        self.baud = baud
        self.server_addr = server_addr  # HDLC dest (server logical addr 1 = 0x03)
        self.parity = parity
        self.stopbits = stopbits
        self.ser: serial.Serial | None = None
        self.client_addr = CLIENT_PUBLIC
        self.client_src = _client_to_hdlc(CLIENT_PUBLIC)
        self.send_seq = 0
        self.recv_seq = 0
        self.invoke_id = 0xC0
        self.connected = False
        self.auth_mode = "none"
        self._on_tx: Callable | None = None
        self._on_rx: Callable | None = None
        self._on_log: Callable | None = None

    def set_callbacks(self, on_tx=None, on_rx=None, on_log=None):
        self._on_tx = on_tx
        self._on_rx = on_rx
        self._on_log = on_log

    def _log(self, msg: str):
        if self._on_log:
            self._on_log(msg)

    def open(self):
        self.ser = serial.Serial(
            self.port, self.baud, bytesize=8, parity=self.parity, stopbits=self.stopbits, timeout=3
        )
        time.sleep(0.3)
        self._log(f"Port ochildi: {self.port} @ {self.baud}")

    def close(self):
        if self.connected:
            self.disconnect()
        if self.ser and self.ser.is_open:
            self.ser.close()
            self._log("Port yopildi")
        self.ser = None

    def _send_recv(self, frame: bytes, timeout: float = 3.0) -> bytes:
        return send_recv(self.ser, frame, timeout, self._on_tx, self._on_rx)

    def _snrm(self) -> bool:
        ua = self._send_recv(
            make_hdlc(self.server_addr, self.client_src, 0x93), timeout=2
        )
        if ua and len(ua) > 5:
            self._log("SNRM: OK")
            return True
        self._log("SNRM: javob yo'q")
        return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self._send_recv(
                make_hdlc(self.server_addr, self.client_src, 0x53), timeout=1
            )
        self.connected = False
        self.send_seq = 0
        self.recv_seq = 0
        self.invoke_id = 0xC0
        self._log("DISC: uzildi")

    def connect_public(self) -> bool:
        """Connect as public client (16) — no authentication."""
        self.client_addr = CLIENT_PUBLIC
        self.client_src = _client_to_hdlc(CLIENT_PUBLIC)
        self.auth_mode = "none"

        if not self._snrm():
            return False

        aarq_body = bytes([
            0xA1, 0x09, 0x06, 0x07, 0x60, 0x85, 0x74, 0x05, 0x08, 0x01, 0x01,
            0xBE, 0x10, 0x04, 0x0E,
            0x01, 0x00, 0x00, 0x00, 0x06, 0x5F, 0x1F, 0x04,
            0x00, 0x00, 0x7E, 0x1F, 0x04, 0xB0
        ])
        aarq = bytes([0x60, len(aarq_body)]) + aarq_body
        return self._finish_aarq(aarq)

    def connect_reader(self) -> bool:
        """Connect as reader (client 1) — HLS5 (HIGH_SHA256), no password needed."""
        self.client_addr = CLIENT_READER
        self.client_src = _client_to_hdlc(CLIENT_READER)
        self.auth_mode = "hls5"

        if not self._snrm():
            return False

        ctos = os.urandom(16)
        app_ctx = bytes([0xA1, 0x09, 0x06, 0x07, 0x60, 0x85, 0x74, 0x05, 0x08, 0x01, 0x01])
        acse = bytes([0x8A, 0x02, 0x07, 0x80])
        mech = bytes([0x8B, 0x07, 0x60, 0x85, 0x74, 0x05, 0x08, 0x02, 0x05])
        auth = bytes([0xAC, len(ctos) + 2, 0x80, len(ctos)]) + ctos
        ui = bytes([0xBE, 0x10, 0x04, 0x0E, 0x01, 0x00, 0x00, 0x00,
                     0x06, 0x5F, 0x1F, 0x04, 0x00, 0x00, 0x7E, 0x1F, 0x04, 0xB0])
        body = app_ctx + acse + mech + auth + ui
        aarq = bytes([0x60, len(body)]) + body
        return self._finish_aarq(aarq)

    def connect_manager(self, password: str = "00000000") -> bool:
        """Connect as manager (client 2) — LOW auth with ASCII password."""
        self.client_addr = CLIENT_MANAGER
        self.client_src = _client_to_hdlc(CLIENT_MANAGER)
        self.auth_mode = "low"

        if not self._snrm():
            return False

        pwd_bytes = password.encode("ascii")
        app_ctx = bytes([0xA1, 0x09, 0x06, 0x07, 0x60, 0x85, 0x74, 0x05, 0x08, 0x01, 0x01])
        acse = bytes([0x8A, 0x02, 0x07, 0x80])
        mech = bytes([0x8B, 0x07, 0x60, 0x85, 0x74, 0x05, 0x08, 0x02, 0x01])
        auth = bytes([0xAC, len(pwd_bytes) + 2, 0x80, len(pwd_bytes)]) + pwd_bytes
        ui = bytes([0xBE, 0x10, 0x04, 0x0E, 0x01, 0x00, 0x00, 0x00,
                     0x06, 0x5F, 0x1F, 0x04, 0x00, 0x00, 0x7E, 0x1F, 0x04, 0xB0])
        body = app_ctx + acse + mech + auth + ui
        aarq = bytes([0x60, len(body)]) + body
        return self._finish_aarq(aarq)

    def _finish_aarq(self, aarq: bytes) -> bool:
        aare = self._send_recv(
            make_hdlc(self.server_addr, self.client_src, 0x10, LLC + aarq)
        )
        if aare and b"\xA2\x03\x02\x01\x00" in aare:
            self.connected = True
            self.send_seq = 1
            self.recv_seq = 1
            self.invoke_id = 0xC0
            self._log(f"AARQ: ACCEPTED (client={self.client_addr}, auth={self.auth_mode})")
            return True
        self._log("AARQ: rad etildi")
        return False

    def _next_ctrl(self) -> int:
        ctrl = ((self.send_seq & 7) << 5) | 0x10 | ((self.recv_seq & 7) << 1)
        self.send_seq = (self.send_seq + 1) % 8
        self.recv_seq = (self.recv_seq + 1) % 8
        return ctrl

    def _next_invoke(self) -> int:
        inv = self.invoke_id
        self.invoke_id = (self.invoke_id + 1) & 0xFF
        return inv

    def get_attribute(self, class_id: int, obis: tuple, attr: int = 2) -> bytes | None:
        """Send GET-Request-Normal, return raw data (after C4 header) or None."""
        if not self.connected:
            return None

        invoke = self._next_invoke()
        get_pdu = bytes([0xC0, 0x01, invoke,
                         (class_id >> 8) & 0xFF, class_id & 0xFF]) + \
                  bytes(obis) + bytes([attr, 0x00])
        ctrl = self._next_ctrl()
        resp = self._send_recv(
            make_hdlc(self.server_addr, self.client_src, ctrl, LLC + get_pdu)
        )
        if not resp or len(resp) < 10:
            return None

        # Find LLC response
        llc_idx = resp.find(b"\xE6\xE7\x00")
        if llc_idx < 0:
            # Try raw parsing
            info = resp[8:-3] if len(resp) > 11 else resp
        else:
            info = resp[llc_idx + 3:]

        # C4 01 invoke_id 00 = GET-Response-Normal, success
        if len(info) >= 4 and info[0] == 0xC4:
            if info[3] == 0x00:
                return info[4:]  # raw DLMS typed data
            else:
                # Access error
                err_codes = {1: "read-write-denied", 2: "data-not-available",
                             3: "read-write-denied", 4: "object-undefined"}
                err = err_codes.get(info[3], f"error={info[3]}")
                self._log(f"GET error: {err} (class={class_id}, obis={obis}, attr={attr})")
                return None
        return None

    def set_attribute(self, class_id: int, obis: tuple, attr: int,
                      data: bytes) -> bool:
        """Send SET-Request-Normal. Returns True on success."""
        if not self.connected:
            return False

        invoke = self._next_invoke()
        set_pdu = bytes([0xC1, 0x01, invoke,
                         (class_id >> 8) & 0xFF, class_id & 0xFF]) + \
                  bytes(obis) + bytes([attr, 0x00]) + data
        ctrl = self._next_ctrl()
        resp = self._send_recv(
            make_hdlc(self.server_addr, self.client_src, ctrl, LLC + set_pdu),
            timeout=5
        )
        if not resp:
            return False

        llc_idx = resp.find(b"\xE6\xE7\x00")
        info = resp[llc_idx + 3:] if llc_idx >= 0 else resp[8:-3]

        # C5 01 invoke 00 = success
        if len(info) >= 4 and info[0] == 0xC5 and info[3] == 0x00:
            self._log("SET: success")
            return True
        self._log(f"SET: failed ({hex_str(info)})")
        return False

    def action(self, class_id: int, obis: tuple, method: int,
               data: bytes = b"\x0F\x00") -> tuple[bool, int]:
        """Send ACTION-Request-Normal. Returns (success, result_code)."""
        if not self.connected:
            return False, -1

        invoke = self._next_invoke()
        action_pdu = bytes([0xC3, 0x01, invoke,
                            (class_id >> 8) & 0xFF, class_id & 0xFF]) + \
                     bytes(obis) + bytes([method, 0x01]) + data
        ctrl = self._next_ctrl()
        resp = self._send_recv(
            make_hdlc(self.server_addr, self.client_src, ctrl, LLC + action_pdu),
            timeout=5
        )
        if not resp:
            return False, -1

        llc_idx = resp.find(b"\xE6\xE7\x00")
        info = resp[llc_idx + 3:] if llc_idx >= 0 else resp[8:-3]

        # C7 01 invoke result_code
        if len(info) >= 4 and info[0] == 0xC7:
            result = info[3]
            success = (result == 0)
            if success:
                self._log(f"ACTION: success (method={method})")
            else:
                codes = {0: "success", 1: "hw-fault", 2: "temp-failure",
                         3: "read-write-denied", 4: "object-undefined",
                         9: "other-reason", 250: "action-not-allowed"}
                self._log(f"ACTION: {codes.get(result, f'code={result}')}")
            return success, result
        return False, -1

    def reconnect(self) -> bool:
        """Re-establish connection (DISC + SNRM + AARQ) with same parameters."""
        self.disconnect()
        time.sleep(0.3)
        if self.auth_mode == "none":
            return self.connect_public()
        elif self.auth_mode == "hls5":
            return self.connect_reader()
        elif self.auth_mode == "low":
            return self.connect_manager()
        return False
