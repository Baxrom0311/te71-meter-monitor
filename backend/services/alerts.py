from fastapi import HTTPException
from sqlalchemy import and_, inspect, or_, select, update

from core.config import settings
from core.database import SessionLocal
from core.time import now_ts
from models.entities import Alert, AlertNotification, AlertRule, Building
from models.schemas import AlertRuleCreate, AlertRuleUpdate, MeterReading
from repositories.alerts import AlertNotificationRepository, AlertRepository, AlertRuleRepository
from services.websocket import ws_manager

ALERT_RULE_KINDS = {
    "undervoltage",
    "overvoltage",
    "frequency",
    "water_low_pressure",
    "water_not_reaching_top",
    "gas_pressure",
    "gas_leak",
}


def _as_dict(obj) -> dict:
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs}


def _validate_alert_rule_values(kind: str, min_value: float | None, max_value: float | None) -> None:
    if kind not in ALERT_RULE_KINDS:
        raise HTTPException(422, "Alert rule turi noto'g'ri")
    if min_value is not None and max_value is not None and min_value > max_value:
        raise HTTPException(422, "min_value max_value dan katta bo'lmasligi kerak")
    if kind in {"undervoltage", "water_low_pressure"} and min_value is None:
        raise HTTPException(422, "Bu rule uchun min_value kerak")
    if kind == "overvoltage" and max_value is None:
        raise HTTPException(422, "Bu rule uchun max_value kerak")
    if kind in {"frequency", "gas_pressure"} and min_value is None and max_value is None:
        raise HTTPException(422, "Bu rule uchun min_value yoki max_value kerak")


async def _alert_rules_for_reading(session, reading: MeterReading) -> dict[str, AlertRule]:
    stmt = select(AlertRule).where(
        and_(
            AlertRule.enabled.is_(True),
            AlertRule.kind.in_(ALERT_RULE_KINDS),
            or_(AlertRule.utility_type.is_(None), AlertRule.utility_type == str(reading.utility_type)),
        )
    )
    if reading.building_id is not None:
        stmt = stmt.where(or_(AlertRule.building_id.is_(None), AlertRule.building_id == reading.building_id))
    else:
        stmt = stmt.where(AlertRule.building_id.is_(None))
    rows = (await session.scalars(stmt)).all()
    selected: dict[str, AlertRule] = {}
    selected_score: dict[str, int] = {}
    for row in rows:
        score = 0
        if row.utility_type:
            score += 1
        if row.building_id is not None:
            score += 2
        if score >= selected_score.get(row.kind, -1):
            selected[row.kind] = row
            selected_score[row.kind] = score
    return selected


def _rule_min(rule: AlertRule | None, fallback: float) -> float:
    return fallback if rule is None or rule.min_value is None else rule.min_value


def _rule_max(rule: AlertRule | None, fallback: float) -> float:
    return fallback if rule is None or rule.max_value is None else rule.max_value


def _rule_severity(rule: AlertRule | None, fallback: str) -> str:
    return fallback if rule is None else rule.severity


def _rule_message(rule: AlertRule | None, fallback: str) -> str:
    return fallback if rule is None or not rule.message else rule.message


def _rule_dedupe_sec(rule: AlertRule | None) -> int:
    return settings.alert_dedupe_sec if rule is None or rule.dedupe_sec is None else rule.dedupe_sec


def _queue_alert(alerts: list[tuple[Alert, int]], alert: Alert, rule: AlertRule | None) -> None:
    alerts.append((alert, _rule_dedupe_sec(rule)))


def _notification_for_alert(alert: Alert, ts: int) -> AlertNotification:
    return AlertNotification(
        alert_id=alert.id,
        device_id=alert.device_id,
        building_id=alert.building_id,
        point_id=alert.point_id,
        utility_type=alert.utility_type,
        severity=alert.severity,
        kind=alert.kind,
        channel="internal",
        status="pending",
        message=alert.message,
        created_at=ts,
    )


async def check_alerts(session, reading: MeterReading) -> None:
    ts = now_ts()
    alerts: list[tuple[Alert, int]] = []
    rules = await _alert_rules_for_reading(session, reading)
    if reading.utility_type == "electricity":
        for phase, voltage in [("L1", reading.voltage_l1), ("L2", reading.voltage_l2), ("L3", reading.voltage_l3)]:
            if voltage is None:
                continue
            undervoltage_min = _rule_min(rules.get("undervoltage"), settings.voltage_min)
            overvoltage_max = _rule_max(rules.get("overvoltage"), settings.voltage_max)
            if voltage < undervoltage_min or voltage > overvoltage_max:
                kind = "overvoltage" if voltage > overvoltage_max else "undervoltage"
                rule = rules.get(kind)
                _queue_alert(
                    alerts,
                    Alert(
                        device_id=reading.device_id,
                        building_id=reading.building_id,
                        point_id=reading.point_id,
                        utility_type=reading.utility_type,
                        severity=_rule_severity(rule, "warning"),
                        ts=ts,
                        kind=kind,
                        value=voltage,
                        message=_rule_message(rule, f"{phase}: {voltage:.1f}V"),
                    ),
                    rule,
                )
        frequency_rule = rules.get("frequency")
        frequency_min = _rule_min(frequency_rule, settings.frequency_min)
        frequency_max = _rule_max(frequency_rule, settings.frequency_max)
        if reading.frequency and (reading.frequency < frequency_min or reading.frequency > frequency_max):
            _queue_alert(
                alerts,
                Alert(
                    device_id=reading.device_id,
                    building_id=reading.building_id,
                    point_id=reading.point_id,
                    utility_type=reading.utility_type,
                    severity=_rule_severity(frequency_rule, "warning"),
                    ts=ts,
                    kind="frequency",
                    value=reading.frequency,
                    message=_rule_message(frequency_rule, f"Chastota: {reading.frequency:.2f}Hz"),
                ),
                frequency_rule,
            )
    elif reading.utility_type == "water":
        pressure = reading.pressure_bar
        water_low_rule = rules.get("water_low_pressure")
        water_pressure_min = _rule_min(water_low_rule, settings.water_pressure_min_bar)
        if pressure is not None and pressure < water_pressure_min:
            _queue_alert(
                alerts,
                Alert(
                    device_id=reading.device_id,
                    building_id=reading.building_id,
                    point_id=reading.point_id,
                    utility_type="water",
                    severity=_rule_severity(water_low_rule, "warning"),
                    ts=ts,
                    kind="water_low_pressure",
                    value=pressure,
                    message=_rule_message(water_low_rule, f"Suv bosimi past: {pressure:.2f} bar"),
                ),
                water_low_rule,
            )
        if reading.pressure_bottom_bar is not None and reading.pressure_top_bar is not None:
            water_top_rule = rules.get("water_not_reaching_top")
            top_pressure_min = _rule_min(water_top_rule, settings.water_pressure_min_bar)
            bottom_pressure_min = _rule_max(water_top_rule, settings.water_bottom_pressure_for_top_check_bar)
            if reading.pressure_bottom_bar > bottom_pressure_min and reading.pressure_top_bar < top_pressure_min:
                _queue_alert(
                    alerts,
                    Alert(
                        device_id=reading.device_id,
                        building_id=reading.building_id,
                        point_id=reading.point_id,
                        utility_type="water",
                        severity=_rule_severity(water_top_rule, "critical"),
                        ts=ts,
                        kind="water_not_reaching_top",
                        value=reading.pressure_top_bar,
                        message=_rule_message(water_top_rule, "Pastda bosim bor, yuqorida suv bosimi past"),
                    ),
                    water_top_rule,
                )
    elif reading.utility_type == "gas":
        gas_pressure_rule = rules.get("gas_pressure")
        gas_pressure_min = _rule_min(gas_pressure_rule, settings.gas_pressure_min_bar)
        gas_pressure_max = _rule_max(gas_pressure_rule, settings.gas_pressure_max_bar)
        if reading.pressure_bar is not None and (
            reading.pressure_bar < gas_pressure_min or reading.pressure_bar > gas_pressure_max
        ):
            _queue_alert(
                alerts,
                Alert(
                    device_id=reading.device_id,
                    building_id=reading.building_id,
                    point_id=reading.point_id,
                    utility_type="gas",
                    severity=_rule_severity(gas_pressure_rule, "critical"),
                    ts=ts,
                    kind="gas_pressure",
                    value=reading.pressure_bar,
                    message=_rule_message(
                        gas_pressure_rule,
                        f"Gaz bosimi normadan tashqari: {reading.pressure_bar:.3f} bar",
                    ),
                ),
                gas_pressure_rule,
            )
        if reading.leak_detected:
            gas_leak_rule = rules.get("gas_leak")
            _queue_alert(
                alerts,
                Alert(
                    device_id=reading.device_id,
                    building_id=reading.building_id,
                    point_id=reading.point_id,
                    utility_type="gas",
                    severity=_rule_severity(gas_leak_rule, "critical"),
                    ts=ts,
                    kind="gas_leak",
                    message=_rule_message(gas_leak_rule, "Gaz sizishi aniqlandi"),
                ),
                gas_leak_rule,
            )

    for alert, dedupe_sec in alerts:
        recent = await session.scalar(
            select(Alert.id).where(
                and_(
                    Alert.device_id == alert.device_id,
                    Alert.kind == alert.kind,
                    Alert.cleared.is_(False),
                    Alert.ts > ts - dedupe_sec,
                )
            )
        )
        if recent:
            continue
        session.add(alert)
        await session.flush()
        if alert.severity == "critical":
            session.add(_notification_for_alert(alert, ts))
        await ws_manager.broadcast(
            {
                "type": "alert",
                "kind": alert.kind,
                "severity": alert.severity,
                "utility_type": alert.utility_type,
                "device_id": alert.device_id,
                "message": alert.message,
            }
        )


async def get_alerts(device_id: str | None, kind: str | None, cleared: bool, limit: int) -> dict:
    async with SessionLocal() as session:
        rows = await AlertRepository(session).list_filtered(device_id, kind, cleared, limit)
    return {"alerts": [_as_dict(row) for row in rows]}


async def list_alert_notifications(status: str | None = None, limit: int = 100) -> dict:
    async with SessionLocal() as session:
        rows = await AlertNotificationRepository(session).list_filtered(status, limit)
    return {"notifications": [_as_dict(row) for row in rows], "total": len(rows)}


async def dispatch_pending_notifications_once(limit: int = 100) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        rows = await AlertNotificationRepository(session).pending(limit)
        for row in rows:
            row.status = "sent"
            row.sent_at = ts
        await session.commit()
    for row in rows:
        await ws_manager.broadcast(
            {
                "type": "alert_notification",
                "status": "sent",
                "severity": row.severity,
                "kind": row.kind,
                "device_id": row.device_id,
                "message": row.message,
            }
        )
    return {"sent": len(rows)}


async def escalate_open_alerts_once(limit: int = 100) -> dict:
    ts = now_ts()
    cutoff = ts - settings.alert_escalation_after_sec
    created: list[AlertNotification] = []
    async with SessionLocal() as session:
        notification_repo = AlertNotificationRepository(session)
        alerts = (
            await session.scalars(
                select(Alert)
                .where(
                    and_(
                        Alert.cleared.is_(False),
                        Alert.severity == "critical",
                        Alert.ts <= cutoff,
                    )
                )
                .order_by(Alert.ts)
                .limit(limit)
            )
        ).all()
        for alert in alerts:
            if await notification_repo.has_escalation(alert.id):
                continue
            notification = AlertNotification(
                alert_id=alert.id,
                device_id=alert.device_id,
                building_id=alert.building_id,
                point_id=alert.point_id,
                utility_type=alert.utility_type,
                severity=alert.severity,
                kind=alert.kind,
                channel="internal",
                status="escalated",
                message=f"ESCALATED: {alert.message}" if alert.message else "ESCALATED",
                created_at=ts,
                sent_at=ts,
            )
            session.add(notification)
            created.append(notification)
        await session.commit()
    for row in created:
        await ws_manager.broadcast(
            {
                "type": "alert_notification",
                "status": "escalated",
                "severity": row.severity,
                "kind": row.kind,
                "device_id": row.device_id,
                "message": row.message,
            }
        )
    return {"escalated": len(created)}


async def process_alert_notifications_once(limit: int = 100) -> dict:
    sent = await dispatch_pending_notifications_once(limit)
    escalated = await escalate_open_alerts_once(limit)
    return {"ok": True, **sent, **escalated}


async def list_alert_rules(
    utility_type: str | None = None,
    building_id: int | None = None,
    enabled: bool | None = None,
    limit: int = 200,
) -> dict:
    async with SessionLocal() as session:
        rows = await AlertRuleRepository(session).list_filtered(utility_type, building_id, enabled, limit)
    return {"rules": [_as_dict(row) for row in rows], "total": len(rows), "allowed_kinds": sorted(ALERT_RULE_KINDS)}


async def create_alert_rule(body: AlertRuleCreate) -> dict:
    kind = body.kind.strip().lower()
    _validate_alert_rule_values(kind, body.min_value, body.max_value)
    ts = now_ts()
    async with SessionLocal() as session:
        if body.building_id is not None and not await session.get(Building, body.building_id):
            raise HTTPException(404, "Dom topilmadi")
        rule = AlertRule(
            building_id=body.building_id,
            utility_type=str(body.utility_type) if body.utility_type else None,
            kind=kind,
            min_value=body.min_value,
            max_value=body.max_value,
            severity=body.severity,
            dedupe_sec=body.dedupe_sec,
            message=body.message,
            enabled=body.enabled,
            created_at=ts,
            updated_at=ts,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
    return {"ok": True, "rule": _as_dict(rule)}


async def update_alert_rule(rule_id: int, body: AlertRuleUpdate) -> dict:
    async with SessionLocal() as session:
        rule = await session.get(AlertRule, rule_id)
        if not rule:
            raise HTTPException(404, "Alert rule topilmadi")
        data = body.model_dump(exclude_unset=True)
        if "kind" in data and data["kind"] is not None:
            data["kind"] = data["kind"].strip().lower()
        if "utility_type" in data and data["utility_type"] is not None:
            data["utility_type"] = str(data["utility_type"])
        if data.get("building_id") is not None and not await session.get(Building, data["building_id"]):
            raise HTTPException(404, "Dom topilmadi")
        next_kind = data.get("kind", rule.kind)
        next_min = data.get("min_value", rule.min_value)
        next_max = data.get("max_value", rule.max_value)
        _validate_alert_rule_values(next_kind, next_min, next_max)
        for key, value in data.items():
            setattr(rule, key, value)
        rule.updated_at = now_ts()
        await session.commit()
        await session.refresh(rule)
    return {"ok": True, "rule": _as_dict(rule)}


async def disable_alert_rule(rule_id: int) -> dict:
    async with SessionLocal() as session:
        rule = await session.get(AlertRule, rule_id)
        if not rule:
            raise HTTPException(404, "Alert rule topilmadi")
        rule.enabled = False
        rule.updated_at = now_ts()
        await session.commit()
    return {"ok": True}


async def clear_alert(alert_id: int) -> dict:
    async with SessionLocal() as session:
        alert = await session.get(Alert, alert_id)
        if alert:
            alert.cleared = True
            alert.cleared_at = now_ts()
            await session.commit()
    return {"ok": True}


async def clear_all_alerts(device_id: str | None) -> dict:
    values = {"cleared": True, "cleared_at": now_ts()}
    stmt = update(Alert).values(**values)
    if device_id:
        stmt = stmt.where(Alert.device_id == device_id)
    async with SessionLocal() as session:
        await session.execute(stmt)
        await session.commit()
    return {"ok": True}
