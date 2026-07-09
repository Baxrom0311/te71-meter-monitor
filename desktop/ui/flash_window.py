"""ESP32 Flash Window — firmware yuklash va serial monitor."""
import os
import sys
import subprocess
import threading
import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QTextEdit, QProgressBar,
    QFrame, QFileDialog, QMessageBox, QRadioButton, QButtonGroup,
    QGroupBox, QSplitter, QCheckBox, QTabWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCursor

# ─── Firmware turlari ─────────────────────────────────────────────────────────
FIRMWARE_TYPES = [
    ("electricity", "⚡  Elektr",     "TE71/TE73 RS-485 DLMS hisoblagich"),
    ("water",       "💧  Suv",        "2x analog bosim sensori"),
    ("gas",         "🔥  Gaz",        "1x analog bosim sensori"),
]

DEFAULT_SERVER  = "http://67.205.171.93"
DEFAULT_TOKEN   = "T30gwzZJ6YTvQeLRMCZyTi-GBAYogsQV"
DEFAULT_WIFI_SSID = "12"
DEFAULT_WIFI_PASS = "12345678"


def _find_pio() -> str | None:
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


def _find_project_root() -> str | None:
    """platformio.ini faylini topadi."""
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(cur, "platformio.ini")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


# ─── Flash Worker ─────────────────────────────────────────────────────────────

class FlashWorker(QThread):
    log_line   = pyqtSignal(str, str)   # (text, color)
    progress   = pyqtSignal(int)        # 0-100
    finished   = pyqtSignal(bool, str)  # (success, message)

    def __init__(self):
        super().__init__()
        self.pio_path      = None
        self.project_root  = None
        self.firmware_env  = "electricity"
        self.upload_port   = ""
        self.server_url    = DEFAULT_SERVER
        self.device_token  = DEFAULT_TOKEN
        self.wifi_ssid     = DEFAULT_WIFI_SSID
        self.wifi_pass     = DEFAULT_WIFI_PASS
        self.build_only    = False
        self._cancelled    = False

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
        build_flags = self._make_build_flags()
        self.log_line.emit("Build flags:", "#94a3b8")
        for f in build_flags.splitlines():
            if f.strip():
                self.log_line.emit(f"  {f.strip()}", "#64748b")
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
        # Suppress pio update check
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

    def _make_build_flags(self) -> str:
        """Barcha build flaglarini bir qatorda yig'adi."""
        sensor_flag = f"-DSENSOR_{self.firmware_env.upper()}"
        server = self.server_url.replace('"', '\\"')
        token  = self.device_token.replace('"', '\\"')
        ssid   = self.wifi_ssid.replace('"', '\\"')
        pwd    = self.wifi_pass.replace('"', '\\"')

        lines = [
            "-std=gnu++17",
            "-DCORE_DEBUG_LEVEL=0",
            sensor_flag,
            f'-DDEFAULT_SERVER_URL=\\"{server}\\"',
            f'-DDEFAULT_DEVICE_TOKEN=\\"{token}\\"',
            f'-DDEFAULT_WIFI_SSID=\\"{ssid}\\"',
            f'-DDEFAULT_WIFI_PASS=\\"{pwd}\\"',
        ]
        return "\n".join(lines)

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


# ─── Serial Monitor Worker ─────────────────────────────────────────────────────

class SerialMonitorWorker(QThread):
    line_received = pyqtSignal(str)
    error         = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._port    = ""
        self._baud    = 115200
        self._running = False
        self._ser     = None

    def start_monitor(self, port: str, baud: int = 115200):
        self._port    = port
        self._baud    = baud
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


# ─── Flash Window ─────────────────────────────────────────────────────────────

class FlashWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ESP32 Dasturchi — Firmware Yuklash")
        self.setMinimumSize(900, 680)
        self.resize(1020, 740)

        self.pio_path     = _find_pio()
        self.project_root = _find_project_root()

        self._flash_worker   = FlashWorker()
        self._flash_worker.log_line.connect(self._on_log)
        self._flash_worker.progress.connect(self._progress_bar.setValue if False else lambda v: None)
        self._flash_worker.finished.connect(self._on_flash_finished)

        self._monitor_worker = SerialMonitorWorker()
        self._monitor_worker.line_received.connect(self._on_monitor_line)
        self._monitor_worker.error.connect(self._on_monitor_error)

        self._setup_ui()
        self._check_pio()

        # Wire progress after setup
        self._flash_worker.progress.connect(self.progress_bar.setValue)

    def _setup_ui(self):
        from .styles import DARK_THEME
        self.setStyleSheet(DARK_THEME)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sol panel (boshqaruv) ──────────────────────────────────────────
        left = QWidget()
        left.setObjectName("sidebar")
        left.setFixedWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(20, 24, 20, 20)
        left_layout.setSpacing(16)

        # Brand
        brand = QLabel("ESP32 Dasturchi")
        brand.setObjectName("brand")
        left_layout.addWidget(brand)

        sub = QLabel("Firmware yuklash va serial monitor")
        sub.setStyleSheet("color:#94a3b8; font-size:12px;")
        left_layout.addWidget(sub)

        # PIO status
        self.lbl_pio = QLabel()
        self.lbl_pio.setStyleSheet("font-size:12px; font-weight:700;")
        left_layout.addWidget(self.lbl_pio)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#1e3a5f;")
        left_layout.addWidget(sep)

        # ── COM port ──────────────────────────────────────────────────────
        left_layout.addWidget(self._section("USB Port (ESP32)"))

        port_row = QHBoxLayout()
        self.combo_port = QComboBox()
        self.combo_port.setMinimumHeight(38)
        port_row.addWidget(self.combo_port, 1)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedSize(38, 38)
        btn_refresh.setToolTip("Portlarni yangilash")
        btn_refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(btn_refresh)
        left_layout.addLayout(port_row)

        # ── Firmware turi ─────────────────────────────────────────────────
        left_layout.addWidget(self._section("Firmware turi"))
        self._fw_group  = QButtonGroup(self)
        self._fw_radios = {}
        for env, label, desc in FIRMWARE_TYPES:
            rb = QRadioButton(label)
            rb.setToolTip(desc)
            self._fw_group.addButton(rb)
            self._fw_radios[env] = rb
            left_layout.addWidget(rb)
        self._fw_radios["electricity"].setChecked(True)

        # ── Server sozlamalari ────────────────────────────────────────────
        left_layout.addWidget(self._section("Server sozlamalari"))

        left_layout.addWidget(self._small_label("Server URL"))
        self.txt_server = QLineEdit(DEFAULT_SERVER)
        self.txt_server.setMinimumHeight(36)
        self.txt_server.setPlaceholderText("http://192.168.1.100")
        left_layout.addWidget(self.txt_server)

        left_layout.addWidget(self._small_label("Device Token"))
        self.txt_token = QLineEdit(DEFAULT_TOKEN)
        self.txt_token.setMinimumHeight(36)
        left_layout.addWidget(self.txt_token)

        # ── WiFi sozlamalari ──────────────────────────────────────────────
        left_layout.addWidget(self._section("WiFi sozlamalari"))

        left_layout.addWidget(self._small_label("WiFi SSID"))
        self.txt_ssid = QLineEdit(DEFAULT_WIFI_SSID)
        self.txt_ssid.setMinimumHeight(36)
        self.txt_ssid.setPlaceholderText("Tarmoq nomi")
        left_layout.addWidget(self.txt_ssid)

        left_layout.addWidget(self._small_label("WiFi Parol"))
        self.txt_wifi_pass = QLineEdit(DEFAULT_WIFI_PASS)
        self.txt_wifi_pass.setMinimumHeight(36)
        self.txt_wifi_pass.setEchoMode(QLineEdit.EchoMode.Password)
        left_layout.addWidget(self.txt_wifi_pass)

        chk_show = QCheckBox("Parolni ko'rsatish")
        chk_show.toggled.connect(
            lambda v: self.txt_wifi_pass.setEchoMode(
                QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password
            )
        )
        left_layout.addWidget(chk_show)

        left_layout.addStretch()

        # ── Tugmalar ──────────────────────────────────────────────────────
        self.btn_flash = QPushButton("⚡  FLASH QILISH")
        self.btn_flash.setObjectName("primary")
        self.btn_flash.setMinimumHeight(46)
        self.btn_flash.clicked.connect(self._start_flash)
        left_layout.addWidget(self.btn_flash)

        self.btn_build = QPushButton("🔨  Faqat build")
        self.btn_build.setMinimumHeight(38)
        self.btn_build.clicked.connect(self._start_build_only)
        left_layout.addWidget(self.btn_build)

        self.btn_cancel = QPushButton("■  Bekor qilish")
        self.btn_cancel.setObjectName("sidebarDanger")
        self.btn_cancel.setMinimumHeight(38)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        left_layout.addWidget(self.btn_cancel)

        root.addWidget(left)

        # ── O'ng panel (log + monitor) ─────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 20, 20, 16)
        right_layout.setSpacing(10)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar{background:#1e3a5f;border:none;border-radius:4px;}"
            "QProgressBar::chunk{background:#3b82f6;border-radius:4px;}"
        )
        right_layout.addWidget(self.progress_bar)

        # Status label
        self.lbl_status = QLabel("Tayyor")
        self.lbl_status.setStyleSheet("color:#94a3b8; font-size:12px; font-weight:600;")
        right_layout.addWidget(self.lbl_status)

        # Tabs: Flash log / Serial Monitor
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane{border:1px solid #1e3a5f;border-radius:6px;}"
            "QTabBar::tab{background:#0f2035;color:#94a3b8;padding:8px 18px;border-radius:6px 6px 0 0;}"
            "QTabBar::tab:selected{background:#1e3a5f;color:#e2e8f0;}"
        )
        right_layout.addWidget(self.tabs)

        # Flash log tab
        self.flash_log = QTextEdit()
        self.flash_log.setReadOnly(True)
        self.flash_log.setFont(QFont("Consolas" if sys.platform == "win32" else "Menlo", 11))
        self.flash_log.setStyleSheet(
            "QTextEdit{background:#06111e;color:#cbd5e1;border:none;border-radius:6px;}"
        )
        self.tabs.addTab(self.flash_log, "📋  Flash Log")

        # Serial monitor tab
        monitor_widget = QWidget()
        monitor_layout = QVBoxLayout(monitor_widget)
        monitor_layout.setContentsMargins(0, 8, 0, 0)
        monitor_layout.setSpacing(6)

        mon_ctrl = QHBoxLayout()
        self.combo_mon_baud = QComboBox()
        self.combo_mon_baud.addItems(["115200", "9600", "57600", "921600"])
        self.combo_mon_baud.setFixedWidth(120)
        mon_ctrl.addWidget(QLabel("Baud:"))
        mon_ctrl.addWidget(self.combo_mon_baud)
        mon_ctrl.addStretch()

        self.btn_mon_start = QPushButton("▶  Boshlash")
        self.btn_mon_start.setFixedHeight(32)
        self.btn_mon_start.clicked.connect(self._start_monitor)
        mon_ctrl.addWidget(self.btn_mon_start)

        self.btn_mon_stop = QPushButton("■  To'xtatish")
        self.btn_mon_stop.setFixedHeight(32)
        self.btn_mon_stop.setEnabled(False)
        self.btn_mon_stop.clicked.connect(self._stop_monitor)
        mon_ctrl.addWidget(self.btn_mon_stop)

        btn_mon_clear = QPushButton("🗑")
        btn_mon_clear.setFixedSize(32, 32)
        btn_mon_clear.clicked.connect(self._clear_monitor)
        mon_ctrl.addWidget(btn_mon_clear)

        monitor_layout.addLayout(mon_ctrl)

        self.monitor_log = QTextEdit()
        self.monitor_log.setReadOnly(True)
        self.monitor_log.setFont(QFont("Consolas" if sys.platform == "win32" else "Menlo", 11))
        self.monitor_log.setStyleSheet(
            "QTextEdit{background:#06111e;color:#86efac;border:none;border-radius:6px;}"
        )
        monitor_layout.addWidget(self.monitor_log)

        self.tabs.addTab(monitor_widget, "📡  Serial Monitor")

        root.addWidget(right, 1)

        # Initial port scan
        self._refresh_ports()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet("color:#3b82f6; font-size:11px; font-weight:800; letter-spacing:1px;")
        return lbl

    def _small_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#475467; font-size:12px; font-weight:700;")
        return lbl

    def _check_pio(self):
        if self.pio_path:
            self.lbl_pio.setText(f"✓ PlatformIO topildi")
            self.lbl_pio.setStyleSheet("font-size:12px; font-weight:700; color:#86efac;")
        else:
            self.lbl_pio.setText("✗ PlatformIO topilmadi!")
            self.lbl_pio.setStyleSheet("font-size:12px; font-weight:700; color:#f87171;")
            self.btn_flash.setEnabled(False)
            self.btn_build.setEnabled(False)
            self._log("PlatformIO topilmadi. O'rnatish uchun:\n  pip install platformio\n  yoki  https://platformio.org/install/cli", "#f87171")

        if self.project_root:
            self._log(f"Loyiha: {self.project_root}", "#64748b")
        else:
            self._log("platformio.ini topilmadi. Loyiha papkasidan ishga tushiring.", "#fbbf24")

    def _refresh_ports(self):
        self.combo_port.clear()
        ports = sorted(serial.tools.list_ports.comports(), key=lambda p: p.device)
        for p in ports:
            desc = p.description if p.description != p.device else ""
            vid_pid = f" [{p.vid:04X}:{p.pid:04X}]" if p.vid else ""
            label = f"{p.device}  {desc}{vid_pid}".strip()
            self.combo_port.addItem(label, p.device)
        if not ports:
            self.combo_port.addItem("Port topilmadi", "")

    def _selected_firmware(self) -> str:
        for env, rb in self._fw_radios.items():
            if rb.isChecked():
                return env
        return "electricity"

    def _log(self, text: str, color: str = "#cbd5e1"):
        self.flash_log.moveCursor(QTextCursor.MoveOperation.End)
        self.flash_log.setTextColor(QColor(color))
        self.flash_log.insertPlainText(text + "\n")
        self.flash_log.moveCursor(QTextCursor.MoveOperation.End)

    def _set_busy(self, busy: bool):
        self.btn_flash.setEnabled(not busy and bool(self.pio_path))
        self.btn_build.setEnabled(not busy and bool(self.pio_path))
        self.btn_cancel.setEnabled(busy)
        self.combo_port.setEnabled(not busy)
        for rb in self._fw_radios.values():
            rb.setEnabled(not busy)

    # ── Flash ─────────────────────────────────────────────────────────────────

    def _start_flash(self):
        port = self.combo_port.currentData()
        if not port:
            QMessageBox.warning(self, "Xato", "USB port tanlanmagan!")
            return
        self._run_pio(port=port, build_only=False)

    def _start_build_only(self):
        self._run_pio(port="", build_only=True)

    def _run_pio(self, port: str, build_only: bool):
        if self._flash_worker.isRunning():
            return

        self.flash_log.clear()
        self.progress_bar.setValue(0)

        fw = self._selected_firmware()
        self.lbl_status.setText(f"{'Build' if build_only else 'Flash'} qilinmoqda: {fw}...")
        self.lbl_status.setStyleSheet("color:#60a5fa; font-size:12px; font-weight:600;")

        self._flash_worker.pio_path     = self.pio_path
        self._flash_worker.project_root = self.project_root
        self._flash_worker.firmware_env = fw
        self._flash_worker.upload_port  = port
        self._flash_worker.server_url   = self.txt_server.text().strip() or DEFAULT_SERVER
        self._flash_worker.device_token = self.txt_token.text().strip() or DEFAULT_TOKEN
        self._flash_worker.wifi_ssid    = self.txt_ssid.text().strip() or DEFAULT_WIFI_SSID
        self._flash_worker.wifi_pass    = self.txt_wifi_pass.text() or DEFAULT_WIFI_PASS
        self._flash_worker.build_only   = build_only

        self._set_busy(True)
        self._flash_worker.start()

    def _cancel(self):
        self._flash_worker.cancel()
        self.lbl_status.setText("Bekor qilinmoqda...")

    def _on_log(self, text: str, color: str):
        self._log(text, color)

    def _on_flash_finished(self, success: bool, message: str):
        self._set_busy(False)
        self.progress_bar.setValue(100 if success else self.progress_bar.value())

        if success:
            self.lbl_status.setText(f"✓  {message}")
            self.lbl_status.setStyleSheet("color:#86efac; font-size:12px; font-weight:700;")
            self._log(f"\n✓  {message}", "#86efac")
            # Auto-switch to serial monitor
            port = self.combo_port.currentData()
            if port and not self._flash_worker.build_only:
                reply = QMessageBox.question(
                    self, "Serial Monitor",
                    "Flash muvaffaqiyatli!\nSerial monitor ochilsinmi?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.tabs.setCurrentIndex(1)
                    QTimer.singleShot(500, self._start_monitor)
        else:
            self.lbl_status.setText(f"✗  {message}")
            self.lbl_status.setStyleSheet("color:#f87171; font-size:12px; font-weight:700;")
            self._log(f"\n✗  {message}", "#f87171")

    # ── Serial Monitor ────────────────────────────────────────────────────────

    def _start_monitor(self):
        if self._monitor_worker.isRunning():
            return
        port = self.combo_port.currentData()
        if not port:
            QMessageBox.warning(self, "Xato", "USB port tanlanmagan!")
            return
        baud = int(self.combo_mon_baud.currentText())
        self.monitor_log.clear()
        self._mon_log(f"[Serial Monitor] {port} @ {baud} baud", "#94a3b8")
        self._mon_log("─" * 50, "#1e3a5f")
        self._monitor_worker.start_monitor(port, baud)
        self.btn_mon_start.setEnabled(False)
        self.btn_mon_stop.setEnabled(True)

    def _stop_monitor(self):
        self._monitor_worker.stop_monitor()
        self._monitor_worker.wait(2000)
        self.btn_mon_start.setEnabled(True)
        self.btn_mon_stop.setEnabled(False)
        self._mon_log("[Monitor to'xtatildi]", "#94a3b8")

    def _clear_monitor(self):
        self.monitor_log.clear()

    def _on_monitor_line(self, line: str):
        self._mon_log(line)

    def _on_monitor_error(self, err: str):
        self._mon_log(f"[Xato] {err}", "#f87171")
        self.btn_mon_start.setEnabled(True)
        self.btn_mon_stop.setEnabled(False)

    def _mon_log(self, text: str, color: str = "#86efac"):
        self.monitor_log.moveCursor(QTextCursor.MoveOperation.End)
        self.monitor_log.setTextColor(QColor(color))
        self.monitor_log.insertPlainText(text + "\n")
        self.monitor_log.moveCursor(QTextCursor.MoveOperation.End)

    # ── Close ─────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._flash_worker.cancel()
        self._monitor_worker.stop_monitor()
        if self._flash_worker.isRunning():
            self._flash_worker.wait(3000)
        if self._monitor_worker.isRunning():
            self._monitor_worker.wait(2000)
        event.accept()
