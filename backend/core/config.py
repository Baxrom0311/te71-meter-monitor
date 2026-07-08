import os
from pathlib import Path

class Settings:
    app_env: str = os.getenv("APP_ENV", "development").lower()
    db_path: Path = Path(os.getenv("DB_PATH", "data/meters.db"))
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://meter:meter_password@localhost:5432/meter_monitor",
    )
    ota_dir: Path = Path(os.getenv("OTA_DIR", "firmware"))
    backup_dir: Path = Path(os.getenv("BACKUP_DIR", "backups"))
    static_dir: Path = Path(os.getenv("STATIC_DIR", "../meter-frontend/dist"))
    backup_keep_days: int = int(os.getenv("BACKUP_KEEP_DAYS", "14"))
    audit_keep_days: int = int(os.getenv("AUDIT_KEEP_DAYS", "180"))

    offline_sec: int = int(os.getenv("OFFLINE_SEC", "120"))
    data_keep_days: int = int(os.getenv("DATA_KEEP_DAYS", "30"))
    public_server_urls: list[str] = [
        item.strip()
        for item in os.getenv("PUBLIC_SERVER_URLS", "").split(",")
        if item.strip()
    ]
    cors_origins: list[str] = [
        item.strip()
        for item in os.getenv("CORS_ORIGINS", "*").split(",")
        if item.strip()
    ]
    trusted_hosts: list[str] = [
        item.strip()
        for item in os.getenv("TRUSTED_HOSTS", "*").split(",")
        if item.strip()
    ]
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    device_rate_limit_per_minute: int = int(os.getenv("DEVICE_RATE_LIMIT_PER_MINUTE", "600"))
    max_request_body_bytes: int = int(os.getenv("MAX_REQUEST_BODY_BYTES", "26214400"))
    telemetry_interval_sec: int = int(os.getenv("TELEMETRY_INTERVAL_SEC", "30"))
    status_interval_sec: int = int(os.getenv("STATUS_INTERVAL_SEC", "60"))
    command_poll_interval_sec: int = int(os.getenv("COMMAND_POLL_INTERVAL_SEC", "10"))
    command_ttl_sec: int = int(os.getenv("COMMAND_TTL_SEC", "3600"))
    command_max_pending_per_device: int = int(os.getenv("COMMAND_MAX_PENDING_PER_DEVICE", "20"))
    ota_batch_process_interval_sec: int = int(os.getenv("OTA_BATCH_PROCESS_INTERVAL_SEC", "60"))
    ota_batch_retry_timeout_sec: int = int(os.getenv("OTA_BATCH_RETRY_TIMEOUT_SEC", "900"))
    ota_batch_max_retries: int = int(os.getenv("OTA_BATCH_MAX_RETRIES", "3"))
    device_api_token: str = os.getenv("DEVICE_API_TOKEN", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    run_inline_workers: bool = os.getenv("RUN_INLINE_WORKERS", "true").lower() in {"1", "true", "yes", "on"}
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = os.getenv("LOG_FORMAT", "text").lower()

    voltage_min: float = float(os.getenv("VOLTAGE_MIN", "195.0"))
    voltage_max: float = float(os.getenv("VOLTAGE_MAX", "253.0"))
    frequency_min: float = float(os.getenv("FREQUENCY_MIN", "49.0"))
    frequency_max: float = float(os.getenv("FREQUENCY_MAX", "51.0"))
    max_voltage: float = float(os.getenv("MAX_VOLTAGE", "500.0"))
    max_current: float = float(os.getenv("MAX_CURRENT", "10000.0"))
    max_pressure_bar: float = float(os.getenv("MAX_PRESSURE_BAR", "100.0"))
    min_temperature_c: float = float(os.getenv("MIN_TEMPERATURE_C", "-80.0"))
    max_temperature_c: float = float(os.getenv("MAX_TEMPERATURE_C", "150.0"))
    water_pressure_min_bar: float = float(os.getenv("WATER_PRESSURE_MIN_BAR", "0.5"))
    water_bottom_pressure_for_top_check_bar: float = float(os.getenv("WATER_BOTTOM_PRESSURE_FOR_TOP_CHECK_BAR", "1.0"))
    gas_pressure_min_bar: float = float(os.getenv("GAS_PRESSURE_MIN_BAR", "0.02"))
    gas_pressure_max_bar: float = float(os.getenv("GAS_PRESSURE_MAX_BAR", "5.0"))
    alert_dedupe_sec: int = int(os.getenv("ALERT_DEDUPE_SEC", "600"))
    alert_escalation_after_sec: int = int(os.getenv("ALERT_ESCALATION_AFTER_SEC", "300"))
    alert_notification_channels: list[str] = [
        item.strip().lower()
        for item in os.getenv("ALERT_NOTIFICATION_CHANNELS", "internal").split(",")
        if item.strip()
    ]
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    alert_webhook_url: str = os.getenv("ALERT_WEBHOOK_URL", "")

    app_name: str = "Meter Monitor"
    app_version: str = "4.0"
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    access_token_ttl_sec: int = int(os.getenv("ACCESS_TOKEN_TTL_SEC", "86400"))
    max_login_attempts: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    login_lock_sec: int = int(os.getenv("LOGIN_LOCK_SEC", "900"))
    min_password_len: int = int(os.getenv("MIN_PASSWORD_LEN", "8"))
    bootstrap_admin_username: str = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    bootstrap_admin_password: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")

    @property
    def is_production(self) -> bool:
        return self.app_env in {"prod", "production"}

    def validate_runtime(self) -> None:
        errors = []
        if self.log_format not in {"json", "text"}:
            errors.append("LOG_FORMAT faqat 'json' yoki 'text' bo'lishi kerak")
        if self.rate_limit_per_minute < 0 or self.device_rate_limit_per_minute < 0:
            errors.append("Rate limit qiymatlari manfiy bo'lmasligi kerak")
        if self.max_request_body_bytes < 0:
            errors.append("MAX_REQUEST_BODY_BYTES manfiy bo'lmasligi kerak")
        if self.command_ttl_sec < 1:
            errors.append("COMMAND_TTL_SEC kamida 1 bo'lishi kerak")
        if self.command_max_pending_per_device < 1:
            errors.append("COMMAND_MAX_PENDING_PER_DEVICE kamida 1 bo'lishi kerak")
        if self.ota_batch_process_interval_sec < 1:
            errors.append("OTA_BATCH_PROCESS_INTERVAL_SEC kamida 1 bo'lishi kerak")
        if self.ota_batch_retry_timeout_sec < 1:
            errors.append("OTA_BATCH_RETRY_TIMEOUT_SEC kamida 1 bo'lishi kerak")
        if self.ota_batch_max_retries < 0:
            errors.append("OTA_BATCH_MAX_RETRIES manfiy bo'lmasligi kerak")
        if self.water_pressure_min_bar < 0 or self.gas_pressure_min_bar < 0:
            errors.append("Bosim minimal qiymatlari manfiy bo'lmasligi kerak")
        if self.gas_pressure_max_bar <= self.gas_pressure_min_bar:
            errors.append("GAS_PRESSURE_MAX_BAR min qiymatdan katta bo'lishi kerak")
        if self.frequency_max <= self.frequency_min:
            errors.append("FREQUENCY_MAX min qiymatdan katta bo'lishi kerak")
        if self.voltage_max <= self.voltage_min:
            errors.append("VOLTAGE_MAX min qiymatdan katta bo'lishi kerak")
        if self.backup_keep_days < 1 or self.audit_keep_days < 1 or self.data_keep_days < 1:
            errors.append("Retention kunlari kamida 1 bo'lishi kerak")
        if self.alert_escalation_after_sec < 0:
            errors.append("ALERT_ESCALATION_AFTER_SEC manfiy bo'lmasligi kerak")
        # SQLite production da ham qo'llab-quvvatlanadi
        # if self.is_production and not self.database_url.startswith(("postgresql+asyncpg://", "postgresql://")):
        #     errors.append("Productionda DATABASE_URL PostgreSQL bo'lishi kerak")
        allowed_channels = {"internal", "telegram", "webhook"}
        invalid_channels = [item for item in self.alert_notification_channels if item not in allowed_channels]
        if invalid_channels:
            errors.append(f"ALERT_NOTIFICATION_CHANNELS noto'g'ri: {', '.join(invalid_channels)}")

        if not self.is_production:
            if errors:
                raise RuntimeError("; ".join(errors))
            return

        insecure_values = {"", "change-me", "change-me-in-production", "change-device-token", "Admin123", "Admin1234"}
        if self.secret_key in insecure_values or len(self.secret_key) < 32:
            errors.append("SECRET_KEY production uchun kuchli va kamida 32 belgili bo'lishi kerak")
        if self.device_api_token in insecure_values or len(self.device_api_token) < 24:
            errors.append("DEVICE_API_TOKEN production uchun kuchli va kamida 24 belgili bo'lishi kerak")
        if self.bootstrap_admin_password and self.bootstrap_admin_password in insecure_values:
            errors.append("BOOTSTRAP_ADMIN_PASSWORD default qiymatda qolmasligi kerak")
        if self.cors_origins == ["*"]:
            errors.append("CORS_ORIGINS productionda '*' bo'lmasligi kerak")
        if self.trusted_hosts == ["*"]:
            errors.append("TRUSTED_HOSTS productionda '*' bo'lmasligi kerak")
        if "telegram" in self.alert_notification_channels and (
            not self.telegram_bot_token or not self.telegram_chat_id
        ):
            errors.append("Telegram alert channel uchun TELEGRAM_BOT_TOKEN va TELEGRAM_CHAT_ID kerak")
        if "webhook" in self.alert_notification_channels and not self.alert_webhook_url:
            errors.append("Webhook alert channel uchun ALERT_WEBHOOK_URL kerak")
        if errors:
            raise RuntimeError("; ".join(errors))


settings = Settings()

for directory in (settings.db_path.parent, settings.ota_dir, settings.backup_dir):
    directory.mkdir(parents=True, exist_ok=True)
