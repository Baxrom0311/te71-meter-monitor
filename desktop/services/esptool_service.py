"""esptool service — ESP32 to'g'ridan-to'g'ri esptool.py orqali proshivka urish va chip diagnostikasi.

Cross-platform (macOS, Windows, Linux) qo'llab-quvvatlaydi.
"""
import sys
import os
import subprocess
import serial.tools.list_ports


class EsptoolService:
    """esptool.py yordamida ESP32 mikrokontrollerlari bilan ishlash xizmati."""

    @staticmethod
    def list_serial_ports() -> list[dict]:
        """Tizimdagi barcha ulangan USB-Serial portlarni qaytaradi."""
        ports = []
        for p in serial.tools.list_ports.comports():
            # Skip internal debug ports if desired, but keep usbserial/COM/tty
            dev = p.device
            desc = p.description or "USB Serial Port"
            hwid = p.hwid or ""

            is_esp = False
            # Check common ESP32 USB VID:PID signatures
            if any(vid in hwid for vid in ["1A86:7523", "10C4:EA60", "303A:", "0403:6001"]):
                is_esp = True

            ports.append({
                "device": dev,
                "description": desc,
                "hwid": hwid,
                "is_esp": is_esp,
                "display_name": f"{dev} — {desc}" if desc != "n/a" else dev
            })
        return ports

    @staticmethod
    def get_python_executable() -> str:
        """Joriy python icrosini topadi."""
        return sys.executable

    @classmethod
    def get_chip_info(cls, port: str, baud: int = 115200) -> dict:
        """ESP32 chip ma'lumotlarini (MAC, Flash hajmi, Chip turi) oladi."""
        py_bin = cls.get_python_executable()
        cmd = [py_bin, "-m", "esptool", "--port", port, "--baud", str(baud), "chip_id"]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            output = res.stdout + "\n" + res.stderr
            info = {
                "raw": output,
                "chip_type": "ESP32",
                "mac": "N/A",
                "features": "N/A",
                "success": res.returncode == 0
            }

            for line in output.splitlines():
                line_lower = line.lower()
                if "detecting chip type..." in line_lower or "chip is" in line_lower:
                    info["chip_type"] = line.split(":")[-1].strip() if ":" in line else line
                elif "mac:" in line_lower:
                    info["mac"] = line.split("MAC:")[-1].strip()
                elif "features:" in line_lower:
                    info["features"] = line.split("Features:")[-1].strip()

            # Try flash_id to get flash size
            cmd_flash = [py_bin, "-m", "esptool", "--port", port, "--baud", str(baud), "flash_id"]
            res_flash = subprocess.run(cmd_flash, capture_output=True, text=True, timeout=10)
            if res_flash.returncode == 0:
                for line in res_flash.stdout.splitlines():
                    if "Detected flash size:" in line:
                        info["flash_size"] = line.split(":")[-1].strip()

            return info
        except Exception as e:
            return {"success": False, "error": str(e), "raw": str(e)}

    @classmethod
    def erase_flash(cls, port: str, baud: int = 115200, chip: str = "auto") -> subprocess.Popen:
        """ESP32 xotirasini to'liq tozalaydi (erase_flash)."""
        py_bin = cls.get_python_executable()
        cmd = [py_bin, "-m", "esptool", "--chip", chip, "--port", port, "--baud", str(baud), "erase_flash"]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

    @classmethod
    def flash_binary(
        cls,
        port: str,
        bin_path: str,
        offset: str = "0x10000",
        baud: int = 460800,
        chip: str = "auto",
        erase_first: bool = False,
        extra_files: list[tuple[str, str]] | None = None
    ) -> subprocess.Popen:
        """Firmware binary faylini ESP32 ga yuklaydi.
        
        extra_files: [(offset, bin_path), ...] bootloader va partitions uchun
        """
        py_bin = cls.get_python_executable()
        cmd = [
            py_bin, "-m", "esptool",
            "--chip", chip,
            "--port", port,
            "--baud", str(baud),
            "--before", "default_reset",
            "--after", "hard_reset",
            "write_flash", "-z",
        ]

        if erase_first:
            cmd.insert(cmd.index("write_flash"), "--erase-all")

        # Add files with offset
        if extra_files:
            for off, path in extra_files:
                cmd.extend([off, path])
        
        cmd.extend([offset, bin_path])

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )
