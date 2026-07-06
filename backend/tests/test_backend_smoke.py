import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEVICE_API_TOKEN", "global-device-token")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "120")
os.environ.setdefault("DEVICE_RATE_LIMIT_PER_MINUTE", "600")
os.environ["DB_PATH"] = tempfile.mktemp(prefix="electr-test-", suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{os.environ['DB_PATH']}"
os.environ["OTA_DIR"] = tempfile.mkdtemp(prefix="electr-test-fw-")
os.environ["BACKUP_DIR"] = tempfile.mkdtemp(prefix="electr-test-backups-")

from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from core.config import settings
from core.database import init_db
from core.middleware import InMemoryRateLimitMiddleware, RequestContextMiddleware, SecurityHeadersMiddleware
from core.security import decode_access_token
from core.database import SessionLocal
from models.entities import Alert, Building
from models.schemas import (
    BuildingCreate,
    DeviceProvisioningTokenCreate,
    DeviceRegister,
    DeviceRole,
    FirmwareMode,
    MeterReading,
    MeasurementPointCreate,
    UtilityType,
)
from schemas.auth import LoginRequest, UserCreate, UserUpdate
from services import audit, auth, backup, platform


async def _noop_app(scope, receive, send):
    return None


async def _empty_receive():
    return {"type": "http.request", "body": b"", "more_body": False}


def _request(path: str = "/limited") -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"host", b"testserver"), (b"x-request-id", b"req-1")],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        },
        receive=_empty_receive,
    )


async def _ok_response(_: Request):
    return PlainTextResponse("ok")


class BackendSmokeTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        Path(settings.db_path).unlink(missing_ok=True)
        settings.bootstrap_admin_username = "admin"
        settings.bootstrap_admin_password = "Admin1234"
        await init_db()
        await auth.bootstrap_admin()

    async def asyncTearDown(self) -> None:
        Path(settings.db_path).unlink(missing_ok=True)

    async def test_auth_device_token_ota_and_audit_flow(self) -> None:
        login = await auth.login(LoginRequest(username="admin", password="Admin1234"))
        token_payload = decode_access_token(login["access_token"])
        self.assertEqual(token_payload["role"], "admin")
        self.assertNotIn("password_hash", login["user"])

        viewer = await auth.create_user(UserCreate(username="viewer", password="Viewer1234", role="user"))
        self.assertEqual(viewer["role"], "user")
        updated_viewer = await auth.update_user(
            viewer["id"],
            UserUpdate(password="Viewer5678", role="user", is_active=True),
            actor_id=token_payload["sub"],
        )
        self.assertEqual(updated_viewer["username"], "viewer")
        viewer_login = await auth.login(LoginRequest(username="viewer", password="Viewer5678"))
        self.assertEqual(viewer_login["user"]["role"], "user")
        disabled_viewer = await auth.update_user(viewer["id"], UserUpdate(is_active=False), actor_id=token_payload["sub"])
        self.assertFalse(disabled_viewer["is_active"])

        building = await platform.create_building(BuildingCreate(name="Smoke Building", floors=9, entrances_count=1))
        point = await platform.create_measurement_point(
            MeasurementPointCreate(
                building_id=building["id"],
                utility_type=UtilityType.water,
                role="water_pressure_top",
                name="Top water pressure",
                sensor_type="pressure_4_20ma",
                converter_type="ADS1115",
                floor=9,
            )
        )
        await platform.register_device(
            DeviceRegister(
                device_id="esp32-water-top-01",
                utility_type=UtilityType.water,
                device_role=DeviceRole.water_node,
                firmware_mode=FirmwareMode.water,
                hardware_version="HW-1.0",
                software_version="1.0.0",
                building_id=building["id"],
                point_id=point["id"],
            )
        )
        with self.assertRaises(HTTPException):
            await platform.save_reading(
                MeterReading(
                    device_id="esp32-water-top-01",
                    utility_type=UtilityType.water,
                    pressure_bar=-1,
                )
            )

        await platform.save_reading(
            MeterReading(
                device_id="esp32-water-top-01",
                utility_type=UtilityType.water,
                building_id=building["id"],
                point_id=point["id"],
                pressure_bar=0.1,
            )
        )
        await platform.save_reading(
            MeterReading(
                device_id="esp32-water-top-01",
                utility_type=UtilityType.water,
                building_id=building["id"],
                point_id=point["id"],
                pressure_bar=0.1,
            )
        )
        async with SessionLocal() as session:
            low_pressure_alerts = await session.scalar(
                select(func.count()).select_from(Alert).where(Alert.kind == "water_low_pressure")
            )
        self.assertEqual(low_pressure_alerts, 1)
        aggregate = await platform.aggregate_hourly_stats_once(24)
        self.assertGreaterEqual(aggregate["buckets"], 1)
        hourly = await platform.list_hourly_stats(device_id="esp32-water-top-01", hours=24)
        self.assertEqual(hourly["stats"][0]["device_id"], "esp32-water-top-01")
        self.assertGreaterEqual(hourly["stats"][0]["samples"], 2)

        token = await platform.rotate_device_token("esp32-water-top-01")
        await platform.verify_device_access("esp32-water-top-01", token["device_token"])
        with self.assertRaises(HTTPException):
            await platform.verify_device_access("esp32-water-top-01", settings.device_api_token)
        command = await platform.create_command("esp32-water-top-01", "reboot")
        self.assertIn("expires_at", command)
        pending = await platform.pending_commands("esp32-water-top-01")
        self.assertEqual(pending["commands"][0]["attempts"], 1)
        self.assertEqual(pending["commands"][0]["max_attempts"], 3)
        await platform.ack_command(command["cmd_id"], "ok")
        listed = await platform.list_commands("esp32-water-top-01", "acked")
        self.assertEqual(listed["commands"][0]["status"], "acked")
        revoked_token = await platform.revoke_device_token(
            "esp32-water-top-01",
            {"sub": 1, "username": "admin", "role": "admin"},
        )
        self.assertTrue(revoked_token["token_revoked_at"])
        with self.assertRaises(HTTPException):
            await platform.verify_device_access("esp32-water-top-01", token["device_token"])

        old_ttl = settings.command_ttl_sec
        settings.command_ttl_sec = -1
        try:
            expired = await platform.create_command("esp32-water-top-01", "ota_check")
            self.assertEqual((await platform.pending_commands("esp32-water-top-01"))["commands"], [])
            expired_list = await platform.list_commands("esp32-water-top-01", "expired")
            self.assertEqual(expired_list["commands"][0]["id"], expired["cmd_id"])
        finally:
            settings.command_ttl_sec = old_ttl

        mismatch = UploadFile(file=BytesIO(b"bad-firmware"), filename="bad.bin")
        await platform.ota_upload(
            version="9.9.9",
            notes="wrong sensor",
            file=mismatch,
            hardware_version="HW-1.0",
            firmware_mode="water",
            utility_type="water",
            device_role="water_node",
            sensor_type="other_sensor",
            converter_type="ADS1115",
        )

        matching = UploadFile(file=BytesIO(b"good-firmware"), filename="good.bin")
        uploaded = await platform.ota_upload(
            version="1.4.0",
            notes="stable",
            file=matching,
            hardware_version="HW-1.0",
            firmware_mode="water",
            utility_type="water",
            device_role="water_node",
            sensor_type="pressure_4_20ma",
            converter_type="ADS1115",
            description="Top water pressure firmware",
            release_notes="Smoke test release",
            compatibility_notes="ESP32-WROOM + 4-20mA pressure sensor + ADS1115",
        )

        ota = await platform.ota_check("esp32-water-top-01", "1.0.0")
        self.assertTrue(ota["update"])
        self.assertEqual(ota["version"], "1.4.0")
        self.assertEqual(ota["sensor_type"], "pressure_4_20ma")
        self.assertEqual(ota["converter_type"], "ADS1115")
        self.assertIn("device_id=esp32-water-top-01", ota["url"])

        same_version = await platform.ota_check("esp32-water-top-01", "1.4.0")
        self.assertFalse(same_version["update"])

        firmware_list = await platform.ota_list()
        self.assertEqual(len(firmware_list["firmware"]), 2)
        self.assertTrue(firmware_list["firmware"][0]["compatibilities"])

        await audit.record(token_payload, "smoke.audit", "firmware", uploaded["id"])
        logs = await audit.list_logs(10)
        self.assertEqual(logs["audit_logs"][0]["action"], "smoke.audit")
        filtered_logs = await audit.list_logs(limit=10, action="smoke.audit", entity_type="firmware")
        self.assertEqual(filtered_logs["total"], 1)
        self.assertEqual(filtered_logs["audit_logs"][0]["entity_type"], "firmware")
        audit_cleanup = await audit.cleanup_old_logs_once(keep_days=9999)
        self.assertEqual(audit_cleanup["deleted_count"], 0)

        backup_result = await backup.create_backup_once("smoke")
        self.assertTrue(backup_result["ok"])
        self.assertTrue(backup.backup_file_path(backup_result["filename"]).exists())
        self.assertGreater(backup_result["tables"]["devices"], 0)
        backups = backup.list_backups()
        self.assertGreaterEqual(backups["total"], 1)
        cleanup = backup.cleanup_old_backups_once(keep_days=9999)
        self.assertEqual(cleanup["deleted_count"], 0)
        extra = await platform.create_building(BuildingCreate(name="Extra After Backup", floors=1, entrances_count=1))
        restore_result = await backup.restore_backup_once(backup_result["filename"], confirm="RESTORE")
        self.assertTrue(restore_result["ok"])
        self.assertIn("pre_restore_backup", restore_result)
        async with SessionLocal() as session:
            extra_building = await session.get(Building, extra["id"])
        self.assertIsNone(extra_building)
        pre_restore_filename = restore_result["pre_restore_backup"]
        deleted = backup.delete_backup(backup_result["filename"])
        self.assertTrue(deleted["ok"])
        deleted_pre_restore = backup.delete_backup(pre_restore_filename)
        self.assertTrue(deleted_pre_restore["ok"])

    async def test_device_provisioning_token_flow(self) -> None:
        building = await platform.create_building(BuildingCreate(name="Provision Building", floors=12, entrances_count=1))
        point = await platform.create_measurement_point(
            MeasurementPointCreate(
                building_id=building["id"],
                utility_type=UtilityType.gas,
                role="gas_pressure_main",
                name="Main gas pressure",
                sensor_type="pressure_4_20ma",
                converter_type="ADS1115",
            )
        )
        provision = await platform.create_provisioning_token(
            DeviceProvisioningTokenCreate(
                device_id="esp32-gas-main-01",
                building_id=building["id"],
                point_id=point["id"],
                utility_type=UtilityType.gas,
                device_role=DeviceRole.gas_node,
                firmware_mode=FirmwareMode.gas,
                ttl_sec=300,
            ),
            {"sub": 1, "username": "admin", "role": "admin"},
        )
        self.assertIn("provisioning_token", provision)

        register = await platform.register_device(
            DeviceRegister(
                device_id="esp32-gas-main-01",
                provisioning_token=provision["provisioning_token"],
                utility_type=UtilityType.electricity,
                firmware_mode=FirmwareMode.electricity,
                hardware_version="HW-GAS-1",
                software_version="1.0.0",
            )
        )
        self.assertTrue(register["provisioned"])
        self.assertIn("device_token", register)
        await platform.verify_device_access("esp32-gas-main-01", register["device_token"])

        device = await platform.get_device("esp32-gas-main-01")
        self.assertEqual(device["utility_type"], "gas")
        self.assertEqual(device["device_role"], "gas_node")
        self.assertEqual(device["firmware_mode"], "gas")
        self.assertEqual(device["building_id"], building["id"])
        self.assertEqual(device["point_id"], point["id"])

        active = await platform.list_provisioning_tokens(active_only=True)
        self.assertEqual(active["tokens"], [])
        all_tokens = await platform.list_provisioning_tokens(active_only=False)
        self.assertEqual(all_tokens["tokens"][0]["used_by_device_id"], "esp32-gas-main-01")
        self.assertNotIn("token_hash", all_tokens["tokens"][0])

        revoked = await platform.create_provisioning_token(
            DeviceProvisioningTokenCreate(
                device_id="esp32-gas-main-02",
                building_id=building["id"],
                point_id=point["id"],
                utility_type=UtilityType.gas,
                device_role=DeviceRole.gas_node,
                firmware_mode=FirmwareMode.gas,
                ttl_sec=300,
            ),
            {"sub": 1, "username": "admin", "role": "admin"},
        )
        revoke_result = await platform.revoke_provisioning_token(
            revoked["id"],
            {"sub": 1, "username": "admin", "role": "admin"},
        )
        self.assertTrue(revoke_result["token"]["revoked_at"])
        with self.assertRaises(HTTPException):
            await platform.register_device(
                DeviceRegister(
                    device_id="esp32-gas-main-02",
                    provisioning_token=revoked["provisioning_token"],
                    utility_type=UtilityType.gas,
                    firmware_mode=FirmwareMode.gas,
                )
            )

    async def test_readiness_and_middleware_hardening(self) -> None:
        from routers.health import ready

        readiness = await ready()
        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(readiness["checks"]["database"], "ok")
        metrics = await platform.metrics_text()
        self.assertIn("meter_monitor_devices_total", metrics)
        self.assertIn("meter_monitor_open_alerts", metrics)

        old_limit = settings.rate_limit_per_minute
        settings.rate_limit_per_minute = 1
        try:
            context = RequestContextMiddleware(_noop_app)
            context_response = await context.dispatch(_request(), _ok_response)
            self.assertEqual(context_response.headers["X-Request-ID"], "req-1")

            security = SecurityHeadersMiddleware(_noop_app)
            security_response = await security.dispatch(_request(), _ok_response)
            self.assertEqual(security_response.headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(security_response.headers["X-Frame-Options"], "DENY")

            limiter = InMemoryRateLimitMiddleware(_noop_app)
            self.assertTrue(limiter._is_device_path("/api/device-status"))
            self.assertTrue(limiter._is_device_path("/api/readings/batch"))
            self.assertFalse(limiter._is_device_path("/api/devices"))
            first = await limiter.dispatch(_request(), _ok_response)
            second = await limiter.dispatch(_request(), _ok_response)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 429)
        finally:
            settings.rate_limit_per_minute = old_limit

    async def test_production_runtime_validation(self) -> None:
        old_env = settings.app_env
        old_secret = settings.secret_key
        old_device_token = settings.device_api_token
        old_admin_password = settings.bootstrap_admin_password
        old_cors = settings.cors_origins
        old_hosts = settings.trusted_hosts
        try:
            settings.app_env = "production"
            settings.secret_key = "change-me"
            settings.device_api_token = "change-device-token"
            settings.bootstrap_admin_password = "Admin1234"
            settings.cors_origins = ["*"]
            settings.trusted_hosts = ["*"]
            with self.assertRaises(RuntimeError):
                settings.validate_runtime()

            settings.secret_key = "s" * 40
            settings.device_api_token = "d" * 32
            settings.bootstrap_admin_password = "StrongAdmin1234"
            settings.cors_origins = ["https://meter.example.uz"]
            settings.trusted_hosts = ["meter.example.uz"]
            settings.validate_runtime()
        finally:
            settings.app_env = old_env
            settings.secret_key = old_secret
            settings.device_api_token = old_device_token
            settings.bootstrap_admin_password = old_admin_password
            settings.cors_origins = old_cors
            settings.trusted_hosts = old_hosts


if __name__ == "__main__":
    unittest.main()
