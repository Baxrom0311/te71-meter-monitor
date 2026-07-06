import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEVICE_API_TOKEN", "global-device-token")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "500")
os.environ.setdefault("DEVICE_RATE_LIMIT_PER_MINUTE", "1000")
os.environ["DB_PATH"] = tempfile.mktemp(prefix="electr-api-test-", suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{os.environ['DB_PATH']}"
os.environ["OTA_DIR"] = tempfile.mkdtemp(prefix="electr-api-fw-")
os.environ["BACKUP_DIR"] = tempfile.mkdtemp(prefix="electr-api-backups-")

import httpx

from app import app
from core.config import settings
from core.database import init_db
from routers import api as api_routes
from services import backup
from services.auth import bootstrap_admin


class ApiIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        Path(settings.db_path).unlink(missing_ok=True)
        settings.bootstrap_admin_username = "admin"
        settings.bootstrap_admin_password = "Admin1234"
        await init_db()
        await bootstrap_admin()
        self.transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        Path(settings.db_path).unlink(missing_ok=True)

    async def _admin_headers(self) -> dict[str, str]:
        response = await self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Admin1234"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def test_backup_restore_api_validation_and_audit(self) -> None:
        admin_headers = await self._admin_headers()
        created = await self.client.post(
            "/api/buildings",
            headers=admin_headers,
            json={"name": "Backup API Building", "floors": 3, "entrances_count": 1},
        )
        self.assertEqual(created.status_code, 200, created.text)
        backup_result = await backup.create_backup_once("api-restore-test")
        filename = backup_result["filename"]

        missing_confirm = await self.client.post(
            f"/api/backups/restore/{filename}",
            headers=admin_headers,
        )
        self.assertEqual(missing_confirm.status_code, 400, missing_confirm.text)
        missing_file = await self.client.post(
            "/api/backups/restore/missing.json.gz?confirm=RESTORE",
            headers=admin_headers,
        )
        self.assertEqual(missing_file.status_code, 404, missing_file.text)

        class FakeRestoreTask:
            id = "restore-task-api-test"

        original_delay = api_routes.restore_backup_task.delay
        api_routes.restore_backup_task.delay = lambda restore_filename, confirm: FakeRestoreTask()
        try:
            queued = await self.client.post(
                f"/api/backups/restore/{filename}?confirm=RESTORE",
                headers=admin_headers,
            )
        finally:
            api_routes.restore_backup_task.delay = original_delay
        self.assertEqual(queued.status_code, 200, queued.text)
        self.assertEqual(queued.json()["task_id"], "restore-task-api-test")
        self.assertEqual(queued.json()["status"], "queued")

        audit = await self.client.get("/api/audit-logs?action=backup.restore", headers=admin_headers)
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertEqual(audit.json()["audit_logs"][0]["entity_id"], filename)

    async def test_device_ingestion_ota_commands_and_audit_over_http(self) -> None:
        admin_headers = await self._admin_headers()

        protected = await self.client.get("/api/devices")
        self.assertEqual(protected.status_code, 401)
        self.assertIn("X-Request-ID", protected.headers)

        viewer = await self.client.post(
            "/api/auth/users",
            headers=admin_headers,
            json={"username": "api-viewer", "password": "Viewer1234", "role": "user"},
        )
        self.assertEqual(viewer.status_code, 200, viewer.text)
        viewer_login = await self.client.post(
            "/api/auth/login",
            json={"username": "api-viewer", "password": "Viewer1234"},
        )
        self.assertEqual(viewer_login.status_code, 200, viewer_login.text)
        viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['access_token']}"}
        disabled_viewer = await self.client.put(
            f"/api/auth/users/{viewer.json()['id']}",
            headers=admin_headers,
            json={"is_active": False},
        )
        self.assertEqual(disabled_viewer.status_code, 200, disabled_viewer.text)
        stale_viewer = await self.client.get("/api/buildings", headers=viewer_headers)
        self.assertEqual(stale_viewer.status_code, 401)

        building = await self.client.post(
            "/api/buildings",
            headers=admin_headers,
            json={"name": "API Building", "floors": 9, "entrances_count": 1},
        )
        self.assertEqual(building.status_code, 200, building.text)
        building_id = building.json()["id"]

        invalid_premise = await self.client.post(
            "/api/premises",
            headers=admin_headers,
            json={"building_id": 999999, "number": "1"},
        )
        self.assertEqual(invalid_premise.status_code, 404)
        utility = await self.client.post(
            f"/api/buildings/{building_id}/utilities",
            headers=admin_headers,
            json={"building_id": building_id, "utility_type": "water", "name": "Water"},
        )
        self.assertEqual(utility.status_code, 200, utility.text)
        duplicate_utility = await self.client.post(
            f"/api/buildings/{building_id}/utilities",
            headers=admin_headers,
            json={"building_id": building_id, "utility_type": "water", "name": "Water duplicate"},
        )
        self.assertEqual(duplicate_utility.status_code, 409)

        invalid_point_create = await self.client.post(
            "/api/measurement-points",
            headers=admin_headers,
            json={
                "building_id": 999999,
                "utility_type": "water",
                "role": "water_pressure_top",
                "name": "Invalid point",
            },
        )
        self.assertEqual(invalid_point_create.status_code, 404)

        point = await self.client.post(
            "/api/measurement-points",
            headers=admin_headers,
            json={
                "building_id": building_id,
                "utility_type": "water",
                "role": "water_pressure_top",
                "name": "Top water",
                "sensor_type": "pressure_4_20ma",
                "converter_type": "ADS1115",
                "floor": 9,
            },
        )
        self.assertEqual(point.status_code, 200, point.text)
        point_id = point.json()["id"]
        invalid_point_parent = await self.client.put(
            f"/api/measurement-points/{point_id}",
            headers=admin_headers,
            json={"parent_id": 999999},
        )
        self.assertEqual(invalid_point_parent.status_code, 404)

        provision = await self.client.post(
            "/api/devices/provisioning-tokens",
            headers=admin_headers,
            json={
                "device_id": "esp32-api-water-01",
                "building_id": building_id,
                "point_id": point_id,
                "utility_type": "water",
                "device_role": "water_node",
                "firmware_mode": "water",
                "ttl_sec": 300,
            },
        )
        self.assertEqual(provision.status_code, 200, provision.text)
        self.assertIn("provisioning_token", provision.json())

        register = await self.client.post(
            "/api/register",
            json={
                "device_id": "esp32-api-water-01",
                "provisioning_token": provision.json()["provisioning_token"],
                "utility_type": "water",
                "device_role": "water_node",
                "firmware_mode": "water",
                "hardware_version": "HW-1.0",
                "software_version": "1.0.0",
            },
        )
        self.assertEqual(register.status_code, 200, register.text)
        self.assertTrue(register.json()["provisioned"])
        self.assertIn("device_token", register.json())
        device_headers = {"X-Device-Token": register.json()["device_token"]}

        missing_update = await self.client.put(
            "/api/devices/missing-device",
            headers=admin_headers,
            json={"name": "Missing"},
        )
        self.assertEqual(missing_update.status_code, 404)
        invalid_point_update = await self.client.put(
            "/api/devices/esp32-api-water-01",
            headers=admin_headers,
            json={"point_id": 999999},
        )
        self.assertEqual(invalid_point_update.status_code, 404)

        used_tokens = await self.client.get(
            "/api/devices/provisioning-tokens?active_only=false",
            headers=admin_headers,
        )
        self.assertEqual(used_tokens.status_code, 200, used_tokens.text)
        self.assertEqual(used_tokens.json()["tokens"][0]["used_by_device_id"], "esp32-api-water-01")
        self.assertNotIn("token_hash", used_tokens.json()["tokens"][0])

        revoke_candidate = await self.client.post(
            "/api/devices/provisioning-tokens",
            headers=admin_headers,
            json={
                "device_id": "esp32-api-water-02",
                "building_id": building_id,
                "point_id": point_id,
                "utility_type": "water",
                "device_role": "water_node",
                "firmware_mode": "water",
                "ttl_sec": 300,
            },
        )
        self.assertEqual(revoke_candidate.status_code, 200, revoke_candidate.text)
        revoked = await self.client.delete(
            f"/api/devices/provisioning-tokens/{revoke_candidate.json()['id']}",
            headers=admin_headers,
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertTrue(revoked.json()["token"]["revoked_at"])
        revoked_register = await self.client.post(
            "/api/register",
            json={
                "device_id": "esp32-api-water-02",
                "provisioning_token": revoke_candidate.json()["provisioning_token"],
                "utility_type": "water",
            },
        )
        self.assertEqual(revoked_register.status_code, 401)

        invalid = await self.client.post(
            "/api/readings",
            headers=device_headers,
            json={"device_id": "esp32-api-water-01", "utility_type": "water", "pressure_bar": -1},
        )
        self.assertEqual(invalid.status_code, 422)

        reading = await self.client.post(
            "/api/readings",
            headers=device_headers,
            json={
                "device_id": "esp32-api-water-01",
                "reading_id": "api-r-1",
                "utility_type": "water",
                "building_id": building_id,
                "point_id": point_id,
                "pressure_bar": 0.1,
            },
        )
        self.assertEqual(reading.status_code, 200, reading.text)

        mixed_batch = await self.client.post(
            "/api/readings/batch",
            headers=device_headers,
            json={
                "device_id": "esp32-api-water-01",
                "readings": [
                    {"device_id": "esp32-api-water-01", "utility_type": "water", "pressure_bar": 0.2},
                    {"device_id": "esp32-other-water", "utility_type": "water", "pressure_bar": 0.2},
                ],
            },
        )
        self.assertEqual(mixed_batch.status_code, 403)

        aggregate = await self.client.post("/api/analytics/hourly/aggregate?hours=24", headers=admin_headers)
        self.assertEqual(aggregate.status_code, 200, aggregate.text)
        self.assertGreaterEqual(aggregate.json()["buckets"], 1)
        hourly = await self.client.get(
            "/api/analytics/hourly?device_id=esp32-api-water-01&hours=24",
            headers=admin_headers,
        )
        self.assertEqual(hourly.status_code, 200, hourly.text)
        self.assertEqual(hourly.json()["stats"][0]["device_id"], "esp32-api-water-01")

        alerts = await self.client.get("/api/alerts?kind=water_low_pressure", headers=admin_headers)
        self.assertEqual(alerts.status_code, 200, alerts.text)
        self.assertEqual(alerts.json()["alerts"][0]["kind"], "water_low_pressure")

        alert_rule = await self.client.post(
            "/api/alert-rules",
            headers=admin_headers,
            json={
                "building_id": building_id,
                "utility_type": "water",
                "kind": "water_low_pressure",
                "min_value": 0.2,
                "severity": "critical",
                "message": "Custom low water pressure",
                "dedupe_sec": 0,
            },
        )
        self.assertEqual(alert_rule.status_code, 200, alert_rule.text)
        rule_id = alert_rule.json()["rule"]["id"]
        cleared_existing_alerts = await self.client.post(
            "/api/alerts/clear-all?device_id=esp32-api-water-01",
            headers=admin_headers,
        )
        self.assertEqual(cleared_existing_alerts.status_code, 200, cleared_existing_alerts.text)
        rule_reading = await self.client.post(
            "/api/readings",
            headers=device_headers,
            json={
                "device_id": "esp32-api-water-01",
                "reading_id": "api-r-rule-1",
                "utility_type": "water",
                "building_id": building_id,
                "point_id": point_id,
                "pressure_bar": 0.15,
            },
        )
        self.assertEqual(rule_reading.status_code, 200, rule_reading.text)
        rule_alerts = await self.client.get("/api/alerts?kind=water_low_pressure", headers=admin_headers)
        self.assertEqual(rule_alerts.status_code, 200, rule_alerts.text)
        self.assertEqual(rule_alerts.json()["alerts"][0]["severity"], "critical")
        self.assertEqual(rule_alerts.json()["alerts"][0]["message"], "Custom low water pressure")
        listed_rules = await self.client.get("/api/alert-rules?utility_type=water", headers=admin_headers)
        self.assertEqual(listed_rules.status_code, 200, listed_rules.text)
        self.assertGreaterEqual(listed_rules.json()["total"], 1)
        disabled_rule = await self.client.delete(f"/api/alert-rules/{rule_id}", headers=admin_headers)
        self.assertEqual(disabled_rule.status_code, 200, disabled_rule.text)

        command = await self.client.post(
            "/api/devices/esp32-api-water-01/commands",
            headers=admin_headers,
            json={"action": "reboot"},
        )
        self.assertEqual(command.status_code, 200, command.text)
        command_id = command.json()["cmd_id"]

        missing_command = await self.client.post(
            "/api/devices/missing-device/commands",
            headers=admin_headers,
            json={"action": "reboot"},
        )
        self.assertEqual(missing_command.status_code, 404)

        pending = await self.client.get("/api/commands/esp32-api-water-01", headers=device_headers)
        self.assertEqual(pending.status_code, 200, pending.text)
        self.assertEqual(pending.json()["commands"][0]["id"], command_id)

        ack = await self.client.post(f"/api/commands/{command_id}/ack?result=ok", headers=device_headers)
        self.assertEqual(ack.status_code, 200, ack.text)

        ota_upload = await self.client.post(
            "/api/ota/upload",
            headers=admin_headers,
            data={
                "version": "2.0.0",
                "hardware_version": "HW-1.0",
                "firmware_mode": "water",
                "utility_type": "water",
                "device_role": "water_node",
                "sensor_type": "pressure_4_20ma",
                "converter_type": "ADS1115",
                "description": "API integration firmware",
            },
            files={"file": ("water.bin", b"firmware-bytes", "application/octet-stream")},
        )
        self.assertEqual(ota_upload.status_code, 200, ota_upload.text)

        ota_check = await self.client.get(
            "/api/ota/check/esp32-api-water-01?current_version=1.0.0",
            headers=device_headers,
        )
        self.assertEqual(ota_check.status_code, 200, ota_check.text)
        self.assertTrue(ota_check.json()["update"])
        self.assertEqual(ota_check.json()["version"], "2.0.0")
        ota_download = await self.client.get(ota_check.json()["url"], headers=device_headers)
        self.assertEqual(ota_download.status_code, 200, ota_download.text)
        self.assertEqual(ota_download.content, b"firmware-bytes")
        ota_report = await self.client.post(
            "/api/ota/report",
            headers=device_headers,
            json={
                "device_id": "esp32-api-water-01",
                "firmware_id": ota_upload.json()["id"],
                "from_version": "1.0.0",
                "target_version": "2.0.0",
                "status": "success",
                "message": "installed",
            },
        )
        self.assertEqual(ota_report.status_code, 200, ota_report.text)
        ota_events = await self.client.get(
            "/api/ota/events?device_id=esp32-api-water-01",
            headers=admin_headers,
        )
        self.assertEqual(ota_events.status_code, 200, ota_events.text)
        self.assertEqual(ota_events.json()["events"][0]["status"], "success")
        updated_device = await self.client.get("/api/devices/esp32-api-water-01", headers=admin_headers)
        self.assertEqual(updated_device.json()["software_version"], "2.0.0")

        audit = await self.client.get("/api/audit-logs?action=ota.upload", headers=admin_headers)
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertGreaterEqual(audit.json()["total"], 1)

        metrics = await self.client.get("/metrics")
        self.assertEqual(metrics.status_code, 200, metrics.text)
        self.assertIn("meter_monitor_devices_total", metrics.text)

        global_config = await self.client.get(
            "/api/device-config/esp32-api-water-01",
            headers={"X-Device-Token": settings.device_api_token},
        )
        self.assertEqual(global_config.status_code, 401)

        token_revoke = await self.client.delete(
            "/api/devices/esp32-api-water-01/token",
            headers=admin_headers,
        )
        self.assertEqual(token_revoke.status_code, 200, token_revoke.text)
        self.assertTrue(token_revoke.json()["token_revoked_at"])
        revoked_config = await self.client.get("/api/device-config/esp32-api-water-01", headers=device_headers)
        self.assertEqual(revoked_config.status_code, 401)


if __name__ == "__main__":
    unittest.main()
