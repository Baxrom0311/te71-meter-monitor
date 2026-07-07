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
from services import alerts as alert_service
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

        restored = await self.client.post(
            f"/api/backups/restore/{filename}?confirm=RESTORE",
            headers=admin_headers,
        )
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertTrue(restored.json()["ok"])
        self.assertEqual(restored.json()["restored_from"], filename)
        self.assertIn("pre_restore_backup", restored.json())

        audit = await self.client.get("/api/audit-logs?action=backup.restore", headers=admin_headers)
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertEqual(audit.json()["audit_logs"][0]["entity_id"], filename)
        openapi = app.openapi()
        schemas = openapi["components"]["schemas"]
        self.assertIn("BackupCreateResponse", schemas)
        self.assertIn("BackupRestoreResponse", schemas)
        self.assertIn("BackupListResponse", schemas)
        self.assertIn("AlertListResponse", schemas)
        self.assertIn("AlertNotificationListResponse", schemas)
        self.assertIn("AlertRuleMutationResponse", schemas)
        self.assertIn("AuditLogListResponse", schemas)
        self.assertIn("FirmwareListResponse", schemas)
        self.assertIn("FirmwareCheckResponse", schemas)
        self.assertIn("CommandQueuedResponse", schemas)
        restore_schema = openapi["paths"]["/api/backups/restore/{filename}"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(restore_schema["$ref"], "#/components/schemas/BackupRestoreResponse")
        audit_schema = openapi["paths"]["/api/audit-logs"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(audit_schema["$ref"], "#/components/schemas/AuditLogListResponse")
        firmware_schema = openapi["paths"]["/api/ota/list"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(firmware_schema["$ref"], "#/components/schemas/FirmwareListResponse")
        alerts_schema = openapi["paths"]["/api/alerts"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(alerts_schema["$ref"], "#/components/schemas/AlertListResponse")

    async def test_backup_management_api_lifecycle(self) -> None:
        admin_headers = await self._admin_headers()
        unauthenticated = await self.client.get("/api/backups")
        self.assertEqual(unauthenticated.status_code, 401, unauthenticated.text)

        backup_result = await backup.create_backup_once("api-management-test")
        filename = backup_result["filename"]

        listed = await self.client.get("/api/backups", headers=admin_headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        filenames = [item["filename"] for item in listed.json()["backups"]]
        self.assertIn(filename, filenames)

        downloaded = await self.client.get(f"/api/backups/download/{filename}", headers=admin_headers)
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        self.assertGreater(len(downloaded.content), 0)

        created = await self.client.post("/api/backups?reason=api-test", headers=admin_headers)
        cleaned = await self.client.post("/api/backups/cleanup?keep_days=7", headers=admin_headers)

        self.assertEqual(created.status_code, 200, created.text)
        self.assertTrue(created.json()["ok"])
        self.assertIn("filename", created.json())
        self.assertEqual(cleaned.status_code, 200, cleaned.text)
        self.assertTrue(cleaned.json()["ok"])
        self.assertIn("deleted_count", cleaned.json())

        create_audit = await self.client.get("/api/audit-logs?action=backup.create", headers=admin_headers)
        self.assertEqual(create_audit.status_code, 200, create_audit.text)
        self.assertEqual(create_audit.json()["audit_logs"][0]["entity_id"], created.json()["filename"])

        removed = await self.client.delete(f"/api/backups/{filename}", headers=admin_headers)
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertTrue(removed.json()["ok"])
        self.assertEqual(removed.json()["filename"], filename)

        missing_download = await self.client.get(f"/api/backups/download/{filename}", headers=admin_headers)
        self.assertEqual(missing_download.status_code, 404, missing_download.text)

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

        electricity_point = await self.client.post(
            "/api/measurement-points",
            headers=admin_headers,
            json={
                "building_id": building_id,
                "utility_type": "electricity",
                "role": "electricity_main_meter",
                "name": "Main electricity",
            },
        )
        self.assertEqual(electricity_point.status_code, 200, electricity_point.text)
        electricity_register = await self.client.post(
            "/api/register",
            headers={"X-Device-Token": "global-device-token"},
            json={
                "device_id": "esp32-api-electric-01",
                "utility_type": "electricity",
                "device_role": "electricity_node",
                "firmware_mode": "electricity",
                "building_id": building_id,
                "point_id": electricity_point.json()["id"],
            },
        )
        self.assertEqual(electricity_register.status_code, 200, electricity_register.text)
        electric_headers = {"X-Device-Token": "global-device-token"}
        for reading_id, energy_kwh, power_w in [("api-e-1", 100.0, 1200.0), ("api-e-2", 104.5, 1500.0)]:
            energy_reading = await self.client.post(
                "/api/readings",
                headers=electric_headers,
                json={
                    "device_id": "esp32-api-electric-01",
                    "reading_id": reading_id,
                    "utility_type": "electricity",
                    "building_id": building_id,
                    "point_id": electricity_point.json()["id"],
                    "energy_kwh": energy_kwh,
                    "power_w": power_w,
                },
            )
            self.assertEqual(energy_reading.status_code, 200, energy_reading.text)
        energy = await self.client.get(
            f"/api/analytics/energy?from_ts=0&to_ts=9999999999&building_id={building_id}&granularity=day",
            headers=admin_headers,
        )
        self.assertEqual(energy.status_code, 200, energy.text)
        self.assertEqual(energy.json()["data"][0]["energy_kwh_delta"], 4.5)
        energy_summary = await self.client.get("/api/analytics/energy/summary", headers=admin_headers)
        self.assertEqual(energy_summary.status_code, 200, energy_summary.text)
        self.assertGreaterEqual(energy_summary.json()["summary"][0]["total_energy_kwh"], 4.5)

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
        notifications = await self.client.get("/api/alert-notifications?status=pending", headers=admin_headers)
        self.assertEqual(notifications.status_code, 200, notifications.text)
        self.assertEqual(notifications.json()["notifications"][0]["kind"], "water_low_pressure")
        self.assertEqual(notifications.json()["notifications"][0]["status"], "pending")
        original_escalation_after_sec = settings.alert_escalation_after_sec
        settings.alert_escalation_after_sec = 0
        try:
            processed_notifications = await alert_service.process_alert_notifications_once()
            processed_again = await alert_service.process_alert_notifications_once()
        finally:
            settings.alert_escalation_after_sec = original_escalation_after_sec
        self.assertGreaterEqual(processed_notifications["sent"], 1)
        self.assertGreaterEqual(processed_notifications["escalated"], 1)
        self.assertEqual(processed_again["escalated"], 0)
        sent_notifications = await self.client.get("/api/alert-notifications?status=sent", headers=admin_headers)
        self.assertEqual(sent_notifications.status_code, 200, sent_notifications.text)
        self.assertEqual(sent_notifications.json()["notifications"][0]["status"], "sent")
        escalated_notifications = await self.client.get(
            "/api/alert-notifications?status=escalated",
            headers=admin_headers,
        )
        self.assertEqual(escalated_notifications.status_code, 200, escalated_notifications.text)
        self.assertEqual(escalated_notifications.json()["notifications"][0]["status"], "escalated")
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
