"""Flash service — PlatformIO build va firmware fayllari bilan ishlash.

UI yoki Qt haqida hech narsa bilmaydi.
"""
import os
import sys
import subprocess


class FlashService:
    """PlatformIO build va flash xizmati logikasi."""

    @staticmethod
    def find_pio() -> str | None:
        """PlatformIO CLI yo'lini topadi."""
        candidates = ["pio", "platformio"]
        # Windows: check common install paths
        if sys.platform == "win32":
            home = os.path.expanduser("~")
            candidates += [
                os.path.join(home, ".platformio", "penv", "Scripts", "pio.exe"),
                r"C:\Users\%s\.platformio\penv\Scripts\pio.exe" % os.getenv("USERNAME", ""),
            ]
        else:
            home = os.path.expanduser("~")
            candidates += [
                os.path.join(home, ".platformio", "penv", "bin", "pio"),
                "/usr/local/bin/pio",
                "/opt/homebrew/bin/pio",
                os.path.join(home, ".local", "bin", "pio"),
            ]
        for c in candidates:
            try:
                result = subprocess.run(
                    [c, "--version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return c
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None

    @staticmethod
    def find_project_root() -> str | None:
        """platformio.ini faylini topadi."""
        cur = os.path.dirname(os.path.abspath(__file__))
        for _ in range(6):
            if os.path.exists(os.path.join(cur, "platformio.ini")):
                return cur
            # Search parent directories
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        return None

    @staticmethod
    def make_build_flags(firmware_env: str, server_url: str, device_token: str, wifi_ssid: str, wifi_pass: str) -> str:
        """Barcha build flaglarini PlatformIO ini formatida yig'adi."""
        sensor_flag = f"-DSENSOR_{firmware_env.upper()}"
        # Escape any single quotes inside values (edge case)
        server = server_url.replace("'", "\\'")
        token = device_token.replace("'", "\\'")
        ssid = wifi_ssid.replace("'", "\\'")
        pwd = wifi_pass.replace("'", "\\'")

        lines = [
            "-std=gnu++17",
            "-DCORE_DEBUG_LEVEL=0",
            sensor_flag,
            f"""'-DDEFAULT_SERVER_URL="{server}"'""",
            f"""'-DDEFAULT_DEVICE_TOKEN="{token}"'""",
            f"""'-DDEFAULT_WIFI_SSID="{ssid}"'""",
            f"""'-DDEFAULT_WIFI_PASS="{pwd}"'""",
        ]
        return "\n".join(lines)
