import os
from pathlib import Path


class Settings:
    db_path: Path = Path(os.getenv("DB_PATH", "data/meters.db"))
    database_url: str = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    ota_dir: Path = Path(os.getenv("OTA_DIR", "firmware"))
    static_dir: Path = Path(os.getenv("STATIC_DIR", "../frontend"))

    offline_sec: int = int(os.getenv("OFFLINE_SEC", "120"))
    data_keep_days: int = int(os.getenv("DATA_KEEP_DAYS", "30"))
    public_server_urls: list[str] = [
        item.strip()
        for item in os.getenv("PUBLIC_SERVER_URLS", "").split(",")
        if item.strip()
    ]
    telemetry_interval_sec: int = int(os.getenv("TELEMETRY_INTERVAL_SEC", "30"))
    status_interval_sec: int = int(os.getenv("STATUS_INTERVAL_SEC", "60"))
    command_poll_interval_sec: int = int(os.getenv("COMMAND_POLL_INTERVAL_SEC", "10"))
    device_api_token: str = os.getenv("DEVICE_API_TOKEN", "")

    voltage_min: float = float(os.getenv("VOLTAGE_MIN", "195.0"))
    voltage_max: float = float(os.getenv("VOLTAGE_MAX", "253.0"))
    frequency_min: float = float(os.getenv("FREQUENCY_MIN", "49.0"))
    frequency_max: float = float(os.getenv("FREQUENCY_MAX", "51.0"))

    app_name: str = "Meter Monitor"
    app_version: str = "4.0"
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    access_token_ttl_sec: int = int(os.getenv("ACCESS_TOKEN_TTL_SEC", "86400"))
    max_login_attempts: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    login_lock_sec: int = int(os.getenv("LOGIN_LOCK_SEC", "900"))
    min_password_len: int = int(os.getenv("MIN_PASSWORD_LEN", "8"))
    bootstrap_admin_username: str = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    bootstrap_admin_password: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")


settings = Settings()

for directory in (settings.db_path.parent, settings.ota_dir):
    directory.mkdir(parents=True, exist_ok=True)
