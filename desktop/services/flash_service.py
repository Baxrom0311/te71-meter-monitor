"""Flash service — PlatformIO build va firmware fayllari bilan ishlash.

Cross-platform (macOS, Windows, Linux) qo'llab-quvvatlaydi.
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
        home = os.path.expanduser("~")
        if sys.platform == "win32":
            candidates += [
                os.path.join(home, ".platformio", "penv", "Scripts", "pio.exe"),
                r"C:\Users\%s\.platformio\penv\Scripts\pio.exe" % os.getenv("USERNAME", ""),
            ]
        else:
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
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                continue
        return None

    @staticmethod
    def find_project_root() -> str | None:
        """platformio.ini faylini topadi."""
        cur = os.path.dirname(os.path.abspath(__file__))
        for _ in range(6):
            if os.path.exists(os.path.join(cur, "platformio.ini")):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

        # Check relative to repo root
        repo_iot = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "iot"))
        if os.path.exists(os.path.join(repo_iot, "platformio.ini")):
            return repo_iot

        return None

    @staticmethod
    def find_compiled_bin(project_root: str, env_name: str) -> str | None:
        """PlatformIO tomonidan yig'ilgan firmware.bin faylini topadi."""
        bin_path = os.path.join(project_root, ".pio", "build", env_name, "firmware.bin")
        if os.path.exists(bin_path):
            return bin_path
        return None

    @staticmethod
    def make_build_flags(
        sensor: str,
        server_url: str,
        device_token: str,
        wifi_ssid: str,
        wifi_pass: str,
        test_mode: bool = False,
        sensor_opts: dict | None = None,
    ) -> str:
        """Barcha build flaglarini PlatformIO ini formatida yig'adi."""
        sensor_flag = f"-DSENSOR_{sensor.upper()}"
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
            f"-DDEFAULT_TEST_MODE={1 if test_mode else 0}",
        ]

        if sensor == "soil" and sensor_opts:
            if sensor_opts.get("lcd"):
                lines.append("-DHAVE_LCD")
            lines.append(f"-DPIN_SOIL_ADC={sensor_opts.get('adc_pin', 32)}")
            lines.append(f"-DSOIL_ADC_DRY={sensor_opts.get('dry', 3300)}")
            lines.append(f"-DSOIL_ADC_WET={sensor_opts.get('wet', 1400)}")

        if sensor == "sound" and sensor_opts:
            if sensor_opts.get("lcd"):
                lines.append("-DHAVE_LCD")
            lines.append(f"-DPIN_SOUND_ADC={sensor_opts.get('adc_pin', 34)}")
            lines.append(f"-DREAD_INTERVAL_MS={sensor_opts.get('interval', 10000)}")

        return "\n".join(lines)
