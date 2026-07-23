"""FlashController — ESP32 to'g'ridan-to'g'ri esptool va PlatformIO thread boshqaruvchisi.

QThread'lar yordamida esptool flashing, chip diagnostikasi va serial monitor jarayonlarini bajaradi.
"""
import os
import re
import time
import subprocess
import serial
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from services.flash_service import FlashService
from services.esptool_service import EsptoolService


class DirectFlashWorker(QThread):
    """esptool.py orqali to'g'ridan-to me .bin faylni ESP32 ga uruvchi background thread."""
    log_line = pyqtSignal(str, str)   # (text, color)
    progress = pyqtSignal(int)        # 0-100
    finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, port: str, bin_path: str, offset: str = "0x10000", baud: int = 460800, chip: str = "auto", erase_first: bool = False):
        super().__init__()
        self.port = port
        self.bin_path = bin_path
        self.offset = offset
        self.baud = baud
        self.chip = chip
        self.erase_first = erase_first
        self._cancelled = False
        self._proc = None

    def cancel(self):
        self._cancelled = True
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def run(self):
        self._cancelled = False
        if not os.path.exists(self.bin_path):
            self.finished.emit(False, f"Firmware binary topilmadi: {self.bin_path}")
            return

        self.log_line.emit(f"🚀 ESP32 Flashing boshlandi...", "#38bdf8")
        self.log_line.emit(f"Port: {self.port} | Baud Rate: {self.baud}", "#94a3b8")
        self.log_line.emit(f"Firmware: {os.path.basename(self.bin_path)} | Offset: {self.offset}", "#94a3b8")
        self.progress.emit(5)

        try:
            self._proc = EsptoolService.flash_binary(
                port=self.port,
                bin_path=self.bin_path,
                offset=self.offset,
                baud=self.baud,
                chip=self.chip,
                erase_first=self.erase_first
            )

            # Regex for progress matching e.g. Writing at 0x00010000... (25 %)
            prog_re = re.compile(r"\((\d+)\s*%\)")

            for line in iter(self._proc.stdout.readline, ''):
                if self._cancelled:
                    break
                line_str = line.strip()
                if not line_str:
                    continue

                color = "#cbd5e1"
                if "error" in line_str.lower() or "fatal" in line_str.lower():
                    color = "#f87171"
                elif "writing at" in line_str.lower():
                    color = "#38bdf8"
                    match = prog_re.search(line_str)
                    if match:
                        pct = int(match.group(1))
                        self.progress.emit(pct)
                elif "hash of data verified" in line_str.lower() or "leaving..." in line_str.lower():
                    color = "#4ade80"
                    self.progress.emit(100)

                self.log_line.emit(line_str, color)

            self._proc.stdout.close()
            return_code = self._proc.wait()

            if return_code == 0 and not self._cancelled:
                self.progress.emit(100)
                self.finished.emit(True, "Firmware ESP32 ga muvaffaqiyatli yuklandi! ✨")
            else:
                self.finished.emit(False, f"Flashing xatosi bilan tugadi (exit code {return_code}). Port va boot mode ni tekshiring.")

        except Exception as e:
            self.finished.emit(False, f"Xatolik yuz berdi: {str(e)}")


class ChipInfoWorker(QThread):
    """ESP32 chip ma'lumotlarini (MAC, Chip turi, Flash) oluvchi background thread."""
    info_signal = pyqtSignal(dict)

    def __init__(self, port: str, baud: int = 115200):
        super().__init__()
        self.port = port
        self.baud = baud

    def run(self):
        info = EsptoolService.get_chip_info(self.port, self.baud)
        self.info_signal.emit(info)


class SerialMonitorWorker(QThread):
    """Kiritilgan serial portdan ma'lumotlarni o'quvchi va yuboruvchi background thread."""
    data_received = pyqtSignal(str, str)  # (port, line_text)
    status_changed = pyqtSignal(str, bool, str)  # (port, is_connected, status_msg)

    def __init__(self, port: str, baud: int = 115200):
        super().__init__()
        self.port = port
        self.baud = baud
        self._running = False
        self._ser = None

    def stop(self):
        self._running = False
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:
                pass

    def send_command(self, cmd: str):
        """Serial portga buyruq yuboradi."""
        if self._ser and self._ser.is_open:
            try:
                self._ser.write((cmd + "\r\n").encode("utf-8"))
            except Exception as e:
                self.data_received.emit(self.port, f"[ERR] Send failed: {str(e)}")

    def run(self):
        self._running = True
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=0.1)
            self.status_changed.emit(self.port, True, f"Ulandi: {self.port} @ {self.baud}")

            buf = ""
            while self._running:
                if self._ser.in_waiting > 0:
                    raw = self._ser.read(self._ser.in_waiting).decode("utf-8", errors="replace")
                    buf += raw
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line_clean = line.strip("\r")
                        if line_clean:
                            self.data_received.emit(self.port, line_clean)
                else:
                    time.sleep(0.05)

        except Exception as e:
            self.status_changed.emit(self.port, False, f"Port xatosi: {str(e)}")
        finally:
            if self._ser and self._ser.is_open:
                try:
                    self._ser.close()
                except Exception:
                    pass
            self.status_changed.emit(self.port, False, f"Ulanish uzildi: {self.port}")


class FlashController(QObject):
    """Barcha flashing va serial workerlarni koordinatsiya qiluvchi controller."""

    def __init__(self):
        super().__init__()
        self.pio_path = FlashService.find_pio()
        self.project_root = FlashService.find_project_root()
        self._active_flash_worker = None
        self._active_chip_worker = None
        self._serial_workers = {}

    def start_direct_flash(
        self,
        port: str,
        bin_path: str,
        offset: str = "0x10000",
        baud: int = 460800,
        chip: str = "auto",
        erase_first: bool = False,
        log_cb=None,
        prog_cb=None,
        finish_cb=None
    ):
        """To'g'ridan-to'g'ri .bin flashing jarayonini boshlaydi."""
        if self._active_flash_worker and self._active_flash_worker.isRunning():
            return False, "Flashing jarayoni allaqachon bajarilmoqda!"

        # Close serial monitor if open on this port
        self.stop_serial_monitor(port)

        worker = DirectFlashWorker(
            port=port,
            bin_path=bin_path,
            offset=offset,
            baud=baud,
            chip=chip,
            erase_first=erase_first
        )

        if log_cb:
            worker.log_line.connect(log_cb)
        if prog_cb:
            worker.progress.connect(prog_cb)
        if finish_cb:
            worker.finished.connect(finish_cb)

        self._active_flash_worker = worker
        worker.start()
        return True, "Flashing boshlandi"

    def cancel_flash(self):
        if self._active_flash_worker and self._active_flash_worker.isRunning():
            self._active_flash_worker.cancel()

    def fetch_chip_info(self, port: str, baud: int, callback):
        """Chip diagnostikasini background workerda ishga tushiradi."""
        worker = ChipInfoWorker(port, baud)
        worker.info_signal.connect(callback)
        self._active_chip_worker = worker
        worker.start()

    def start_serial_monitor(self, port: str, baud: int, data_cb, status_cb) -> SerialMonitorWorker:
        """Serial monitorni ishga tushiradi."""
        self.stop_serial_monitor(port)

        worker = SerialMonitorWorker(port, baud)
        worker.data_received.connect(data_cb)
        worker.status_changed.connect(status_cb)
        self._serial_workers[port] = worker
        worker.start()
        return worker

    def stop_serial_monitor(self, port: str):
        if port in self._serial_workers:
            w = self._serial_workers.pop(port)
            w.stop()
            w.wait(500)
