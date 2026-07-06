from typing import Optional

from fastapi import APIRouter, Depends, Query

from core.security import current_token_payload, require_admin
from models.schemas import (
    AlertListResponse,
    AlertNotificationListResponse,
    AlertRuleCreate,
    AlertRuleListResponse,
    AlertRuleMutationResponse,
    AlertRuleUpdate,
    OkResponse,
)
from services import alerts as alert_service
from services import audit

router = APIRouter(prefix="/api")


@router.get("/alerts", response_model=AlertListResponse)
async def get_alerts(
    device_id: Optional[str] = None,
    kind: Optional[str] = None,
    cleared: bool = False,
    limit: int = Query(50, ge=1, le=500),
    _: dict = Depends(current_token_payload),
):
    return await alert_service.get_alerts(device_id, kind, cleared, limit)


@router.get("/alert-notifications", response_model=AlertNotificationListResponse)
async def list_alert_notifications(
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_admin),
):
    return await alert_service.list_alert_notifications(status, limit)


@router.get("/alert-rules", response_model=AlertRuleListResponse)
async def list_alert_rules(
    utility_type: Optional[str] = None,
    building_id: Optional[int] = None,
    enabled: Optional[bool] = None,
    limit: int = Query(200, ge=1, le=500),
    _: dict = Depends(current_token_payload),
):
    return await alert_service.list_alert_rules(utility_type, building_id, enabled, limit)


@router.post("/alert-rules", response_model=AlertRuleMutationResponse)
async def create_alert_rule(body: AlertRuleCreate, admin: dict = Depends(require_admin)):
    result = await alert_service.create_alert_rule(body)
    await audit.record(admin, "alert_rule.create", "alert_rule", result["rule"]["id"], result["rule"])
    return result


@router.put("/alert-rules/{rule_id}", response_model=AlertRuleMutationResponse)
async def update_alert_rule(rule_id: int, body: AlertRuleUpdate, admin: dict = Depends(require_admin)):
    result = await alert_service.update_alert_rule(rule_id, body)
    await audit.record(admin, "alert_rule.update", "alert_rule", rule_id, result["rule"])
    return result


@router.delete("/alert-rules/{rule_id}", response_model=OkResponse)
async def disable_alert_rule(rule_id: int, admin: dict = Depends(require_admin)):
    result = await alert_service.disable_alert_rule(rule_id)
    await audit.record(admin, "alert_rule.disable", "alert_rule", rule_id)
    return result


@router.post("/alerts/{alert_id}/clear", response_model=OkResponse)
async def clear_alert(alert_id: int, admin: dict = Depends(require_admin)):
    result = await alert_service.clear_alert(alert_id)
    await audit.record(admin, "alert.clear", "alert", alert_id)
    return result


@router.post("/alerts/clear-all", response_model=OkResponse)
async def clear_all_alerts(device_id: Optional[str] = None, admin: dict = Depends(require_admin)):
    result = await alert_service.clear_all_alerts(device_id)
    await audit.record(admin, "alert.clear_all", "alert", device_id, {"device_id": device_id})
    return result
