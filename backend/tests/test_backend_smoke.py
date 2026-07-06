import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEVICE_API_TOKEN", "global-device-token")
os.environ["DB_PATH"] = tempfile.mktemp(prefix="electr-test-", suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{os.environ['DB_PATH']}"
os.environ["OTA_DIR"] = tempfile.mkdtemp(prefix="electr-test-fw-")

from starlette.datastructures import UploadFile

from core.config import settings
from core.database import init_db
from core.security import decode_access_token
from models.schemas import (
    BuildingCreate,
    DeviceRegister,
    DeviceRole,
    FirmwareMode,
    MeasurementPointCreate,
    UtilityType,
)
from schemas.auth import LoginRequest, UserCreate
from services import audit, auth, platform


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

        token = await platform.rotate_device_token("esp32-water-top-01")
        await platform.verify_device_access("esp32-water-top-01", token["device_token"])

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


if __name__ == "__main__":
    unittest.main()
