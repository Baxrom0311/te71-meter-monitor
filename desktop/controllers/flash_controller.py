"""FlashController — ESP32 firmware build/upload va serial monitor workerlarni boshqarish.

QThread'lar yordamida jarayonlarni fonda bajaradi va natijalarni pyqtSignal orqali uzatadi.
"""
import os
import subprocess
import serial
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from services.flash_service import FlashService


class FlashWorker(QThread):
    """PlatformIO orqali build va flash/upload ishlarini bajaruvchi background thread."""
    log_line = pyqtSignal(str, str)   # (text, color)
    progress = pyqtSignal(int)        # 0-100
    finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self):
        super().__init__()
        self.pio_path = None
        self.project_root = None
        self.firmware_env = "electricity"
        self.sensor_name = ""
        self.sensor_opts: dict = {}
        self.upload_port = ""
        self.server_url = ""
        self.device_token = ""
        self.wifi_ssid = ""
        self.wifi_pass = ""
        self.test_mode = False
        self.build_only = False
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        self._cancelled = False
        try:
            self._do_flash()
        except Exception as e:
            self.finished.emit(False, str(e))

    def _do_flash(self):
        if not self.pio_path:
            self.finished.emit(False, "PlatformIO topilmadi! Iltimos, PlatformIO ni o'rnating.")
            return
        if not self.project_root:
            self.finished.emit(False, "platformio.ini topilmadi! Loyiha papkasini tekshiring.")
            return

        self.log_line.emit(f"PlatformIO: {self.pio_path}", "#94a3b8")
        self.log_line.emit(f"Loyiha: {self.project_root}", "#94a3b8")
        self.log_line.emit(f"Firmware: {self.firmware_env}", "#94a3b8")
        if not self.build_only:
            self.log_line.emit(f"Port: {self.upload_port}", "#94a3b8")
        self.log_line.emit("─" * 60, "#334155")

        # Build flags (server, token, wifi)
        build_flags = FlashService.make_build_flags(
            self.sensor_name or self.firmware_env,
            self.server_url,
            self.device_token,
            self.wifi_ssid,
            self.wifi_pass,
            self.test_mode,
            sensor_opts=self.sensor_opts,
        )
        self.log_line.emit("Build flags:", "#94a3b8")
        for f in build_flags.splitlines():
            if f.strip():
                display_flag = f.strip()
                if "DEFAULT_DEVICE_TOKEN" in display_flag:
                    display_flag = "'-DDEFAULT_DEVICE_TOKEN=\"***\"'"
                self.log_line.emit(f"  {display_flag}", "#64748b")
        self.log_line.emit("─" * 60, "#334155")

        # PlatformIO command
        cmd = [self.pio_path, "run", "-e", self.firmware_env]
        if not self.build_only:
            cmd += ["-t", "upload", "--upload-port", self.upload_port]
        cmd += ["-O", f"build_flags={build_flags}"]

        self.log_line.emit(f"▶  {' '.join(cmd)}", "#60a5fa")
        self.progress.emit(5)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PLATFORMIO_DISABLE_PROGRESSBAR"] = "true"

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
        except FileNotFoundError:
            self.finished.emit(False, f"PlatformIO ishga tushmadi: {self.pio_path}")
            return

        pct = 5
        for line in proc.stdout:
            if self._cancelled:
                proc.kill()
                self.finished.emit(False, "Bekor qilindi.")
                return
            line = line.rstrip()
            if not line:
                continue
            color = self._line_color(line)
            self.log_line.emit(line, color)

            # Progress estimation
            if "Compiling" in line or "Building" in line:
                pct = min(pct + 2, 60)
                self.progress.emit(pct)
            elif "Linking" in line:
                self.progress.emit(65)
            elif "Uploading" in line or "Writing" in line or "Flashing" in line:
                pct = max(pct, 70)
                pct = min(pct + 3, 95)
                self.progress.emit(pct)
            elif "Hard resetting" in line or "Leaving" in line:
                self.progress.emit(98)

        proc.wait()
        if proc.returncode == 0:
            self.progress.emit(100)
            action = "Build" if self.build_only else "Flash"
            self.finished.emit(True, f"{action} muvaffaqiyatli tugadi!")
        else:
            self.finished.emit(False, f"PlatformIO xatosi (kod {proc.returncode})")

    def _line_color(self, line: str) -> str:
        l = line.lower()
        if any(w in l for w in ("error", "failed", "xato", "critical")):
            return "#f87171"
        if any(w in l for w in ("warning", "warn")):
            return "#fbbf24"
        if any(w in l for w in ("success", "done", "finished", "muvaffaqiyat", "uploading", "writing")):
            return "#86efac"
        if line.startswith("▶") or "compiling" in l or "linking" in l or "building" in l:
            return "#60a5fa"
        return "#cbd5e1"


class SerialMonitorWorker(QThread):
    """Serial port loglarini o'qish uchun background thread."""
    line_received = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._port = ""
        self._baud = 115200
        self._running = False
        self._ser = None

    def start_monitor(self, port: str, baud: int = 115200):
        self._port = port
        self._baud = baud
        self._running = True
        self.start()

    def stop_monitor(self):
        self._running = False
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass

    def run(self):
        try:
            self._ser = serial.Serial(self._port, self._baud, timeout=1)
        except serial.SerialException as e:
            self.error.emit(str(e))
            return
        while self._running:
            try:
                line = self._ser.readline()
                if line:
                    self.line_received.emit(line.decode("utf-8", errors="replace").rstrip())
            except serial.SerialException as e:
                if self._running:
                    self.error.emit(str(e))
                break
        try:
            self._ser.close()
        except Exception:
            pass


class FlashController(QObject):
    """UI va FlashService o'rtasidagi controller."""
    log_line = pyqtSignal(str, str)
    progress = pyqtSignal(int)
    flash_finished = pyqtSignal(bool, str)
    monitor_line = pyqtSignal(str)
    monitor_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.pio_path = FlashService.find_pio()
        self.project_root = FlashService.find_project_root()

        self._flash_worker = FlashWorker()
        self._flash_worker.pio_path = self.pio_path
        self._flash_worker.project_root = self.project_root
        self._flash_worker.log_line.connect(self.log_line.emit)
        self._flash_worker.progress.connect(self.progress.emit)
        self._flash_worker.finished.connect(self.flash_finished.emit)

        self._monitor_worker = SerialMonitorWorker()
        self._monitor_worker.line_received.connect(self.monitor_line.emit)
        self._monitor_worker.error.connect(self.monitor_error.emit)

    def is_flashing(self) -> bool:
        return self._flash_worker.isRunning()

    def is_monitoring(self) -> bool:
        return self._monitor_worker.isRunning()

    def start_flash(
        self,
        env: str,
        port: str,
        build_only: bool,
        server: str,
        token: str,
        ssid: str,
        wifi_pass: str,
        test_mode: bool = False,
        sensor: str = "",
        sensor_opts: dict | None = None,
    ):
        if self._flash_worker.isRunning():
            return
        self._flash_worker.firmware_env = env
        self._flash_worker.sensor_name = sensor or env
        self._flash_worker.sensor_opts = sensor_opts or {}
        self._flash_worker.upload_port = port
        self._flash_worker.build_only = build_only
        self._flash_worker.server_url = server
        self._flash_worker.device_token = token
        self._flash_worker.wifi_ssid = ssid
        self._flash_worker.wifi_pass = wifi_pass
        self._flash_worker.test_mode = test_mode
        self._flash_worker.start()

    def cancel_flash(self):
        self._flash_worker.cancel()

    def start_monitor(self, port: str, baud: int = 115200):
        self._monitor_worker.start_monitor(port, baud)

    def stop_monitor(self):
        self._monitor_worker.stop_monitor()
