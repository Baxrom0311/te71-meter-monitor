from celery import Celery

from core.config import settings


celery_app = Celery(
    "meter_monitor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["tasks.maintenance", "tasks.backup", "tasks.ota"],
)

celery_app.conf.update(
    timezone="Asia/Samarkand",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "detect-offline-devices-every-minute": {
            "task": "maintenance.detect_offline_devices",
            "schedule": 60.0,
        },
        "cleanup-old-data-daily": {
            "task": "maintenance.cleanup_old_data",
            "schedule": 86400.0,
        },
        "expire-commands-every-minute": {
            "task": "maintenance.expire_commands",
            "schedule": 60.0,
        },
        "process-alert-notifications-every-minute": {
            "task": "maintenance.process_alert_notifications",
            "schedule": 60.0,
        },
        "process-ota-batches": {
            "task": "ota.process_due_batches",
            "schedule": float(settings.ota_batch_process_interval_sec),
        },
        "aggregate-hourly-stats-hourly": {
            "task": "maintenance.aggregate_hourly_stats",
            "schedule": 3600.0,
            "args": (48,),
        },
        "cleanup-old-backups-daily": {
            "task": "backup.cleanup_old",
            "schedule": 86400.0,
        },
        "cleanup-old-audit-logs-daily": {
            "task": "maintenance.cleanup_old_audit_logs",
            "schedule": 86400.0,
        },
    },
)
