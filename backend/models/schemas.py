from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class UtilityType(StrEnum):
    electricity = "electricity"
    water = "water"
    gas = "gas"


class MeasurementRole(StrEnum):
    electricity_main_meter = "electricity_main_meter"
    water_pressure_bottom = "water_pressure_bottom"
    water_pressure_top = "water_pressure_top"
    gas_pressure_main = "gas_pressure_main"
    water_flow = "water_flow"
    gas_flow = "gas_flow"
    gas_leak = "gas_leak"


class DeviceRole(StrEnum):
    electricity_node = "electricity_node"
    water_node = "water_node"
    gas_node = "gas_node"


class FirmwareMode(StrEnum):
    electricity = "electricity"
    water = "water"
    gas = "gas"
    auto = "auto"


class BuildingUtilityStatus(StrEnum):
    active = "active"
    disabled = "disabled"
    maintenance = "maintenance"


class BuildingCreate(BaseModel):
    name: str
    address: Optional[str] = None
    floors: int = Field(1, ge=1)
    entrances_count: int = Field(1, ge=1)
    description: Optional[str] = None


class BuildingUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    floors: Optional[int] = Field(None, ge=1)
    entrances_count: Optional[int] = Field(None, ge=1)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class BuildingUtilityCreate(BaseModel):
    building_id: int
    utility_type: UtilityType
    name: Optional[str] = None
    status: BuildingUtilityStatus = BuildingUtilityStatus.active


class BuildingUtilityUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[BuildingUtilityStatus] = None


class BuildingDefaultProvision(BaseModel):
    electricity_device_id: Optional[str] = None
    water_device_id: Optional[str] = None
    gas_device_id: Optional[str] = None
    top_floor: Optional[int] = None


class PremiseCreate(BaseModel):
    building_id: int
    number: str
    floor: Optional[int] = None
    premise_type: str = "apartment"


class MeasurementPointCreate(BaseModel):
    name: Optional[str] = None
    utility_type: UtilityType = UtilityType.electricity
    role: MeasurementRole = MeasurementRole.electricity_main_meter
    sensor_type: Optional[str] = None
    converter_type: Optional[str] = None
    location_name: Optional[str] = None
    building_id: Optional[int] = None
    utility_module_id: Optional[int] = None
    premise_id: Optional[int] = None
    parent_id: Optional[int] = None
    device_id: Optional[str] = None
    meter_serial: Optional[str] = None
    floor: Optional[int] = None


class MeasurementPointUpdate(BaseModel):
    name: Optional[str] = None
    utility_type: Optional[UtilityType] = None
    role: Optional[MeasurementRole] = None
    sensor_type: Optional[str] = None
    converter_type: Optional[str] = None
    location_name: Optional[str] = None
    building_id: Optional[int] = None
    utility_module_id: Optional[int] = None
    premise_id: Optional[int] = None
    parent_id: Optional[int] = None
    device_id: Optional[str] = None
    meter_serial: Optional[str] = None
    floor: Optional[int] = None
    is_active: Optional[bool] = None


class MeasurementPointDeviceBind(BaseModel):
    device_id: str


class DeviceRegister(BaseModel):
    device_id: str
    provisioning_token: Optional[str] = None
    name: Optional[str] = None
    utility_type: UtilityType = UtilityType.electricity
    device_role: Optional[DeviceRole] = None
    firmware_mode: FirmwareMode = FirmwareMode.auto
    meter_type: Optional[str] = "unknown"
    meter_serial: Optional[str] = None
    serial_number: Optional[str] = None
    hardware_version: Optional[str] = None
    software_version: Optional[str] = None
    build_number: Optional[str] = None
    baud_rate: Optional[int] = 9600
    chip_model: Optional[str] = None
    rssi: Optional[int] = None
    fw_version: Optional[str] = None
    ip: Optional[str] = None
    building_id: Optional[int] = None
    point_id: Optional[int] = None


class DeviceProvisioningTokenCreate(BaseModel):
    device_id: Optional[str] = None
    building_id: Optional[int] = None
    point_id: Optional[int] = None
    utility_type: Optional[UtilityType] = None
    device_role: Optional[DeviceRole] = None
    firmware_mode: Optional[FirmwareMode] = None
    ttl_sec: int = Field(86400, ge=60, le=2592000)


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    room: Optional[str] = None
    group_name: Optional[str] = None
    utility_type: Optional[UtilityType] = None
    device_role: Optional[DeviceRole] = None
    firmware_mode: Optional[FirmwareMode] = None
    hardware_version: Optional[str] = None
    software_version: Optional[str] = None
    build_number: Optional[str] = None
    building_id: Optional[int] = None
    point_id: Optional[int] = None
    is_active: Optional[bool] = None


class DeviceTokenResponse(BaseModel):
    device_id: str
    device_token: str
    token_type: str = "device"


class OtaInstallReport(BaseModel):
    device_id: str
    firmware_id: Optional[int] = None
    from_version: Optional[str] = None
    target_version: Optional[str] = None
    status: str = Field(..., pattern="^(started|success|failed|rolled_back)$")
    message: Optional[str] = None


class FirmwareCompatibilityResponse(BaseModel):
    id: int
    firmware_id: int
    utility_type: Optional[str] = None
    firmware_mode: Optional[str] = None
    device_role: Optional[str] = None
    hardware_version: Optional[str] = None
    sensor_type: Optional[str] = None
    converter_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[int] = None


class FirmwareResponse(BaseModel):
    id: int
    filename: str
    version: str
    hardware_version: Optional[str] = None
    firmware_mode: str
    device_role: Optional[str] = None
    utility_type: Optional[str] = None
    sensor_type: Optional[str] = None
    converter_type: Optional[str] = None
    size: Optional[int] = None
    sha256: Optional[str] = None
    uploaded: Optional[int] = None
    active: bool
    notes: Optional[str] = None
    description: Optional[str] = None
    release_notes: Optional[str] = None
    compatibility_notes: Optional[str] = None
    compatibilities: list[FirmwareCompatibilityResponse] = Field(default_factory=list)
    url: str


class FirmwareUploadResponse(FirmwareResponse):
    ok: bool


class FirmwareListResponse(BaseModel):
    firmware: list[FirmwareResponse]


class FirmwareCheckResponse(BaseModel):
    update: bool
    id: Optional[int] = None
    filename: Optional[str] = None
    version: Optional[str] = None
    hardware_version: Optional[str] = None
    firmware_mode: Optional[str] = None
    device_role: Optional[str] = None
    utility_type: Optional[str] = None
    sensor_type: Optional[str] = None
    converter_type: Optional[str] = None
    size: Optional[int] = None
    sha256: Optional[str] = None
    uploaded: Optional[int] = None
    active: Optional[bool] = None
    notes: Optional[str] = None
    description: Optional[str] = None
    release_notes: Optional[str] = None
    compatibility_notes: Optional[str] = None
    compatibilities: list[FirmwareCompatibilityResponse] = Field(default_factory=list)
    url: Optional[str] = None


class FirmwareInstallEventResponse(BaseModel):
    id: int
    device_id: str
    firmware_id: Optional[int] = None
    from_version: Optional[str] = None
    target_version: Optional[str] = None
    status: str
    message: Optional[str] = None
    ts: int
    created_at: Optional[int] = None


class FirmwareInstallEventListResponse(BaseModel):
    events: list[FirmwareInstallEventResponse]
    total: int


class OtaReportResponse(BaseModel):
    ok: bool
    id: int
    ts: int


class AlertRuleCreate(BaseModel):
    kind: str
    utility_type: Optional[UtilityType] = None
    building_id: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    severity: str = Field("warning", pattern="^(info|warning|critical)$")
    dedupe_sec: Optional[int] = Field(None, ge=0, le=86400)
    message: Optional[str] = None
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    kind: Optional[str] = None
    utility_type: Optional[UtilityType] = None
    building_id: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    severity: Optional[str] = Field(None, pattern="^(info|warning|critical)$")
    dedupe_sec: Optional[int] = Field(None, ge=0, le=86400)
    message: Optional[str] = None
    enabled: Optional[bool] = None


class AlertResponse(BaseModel):
    id: int
    device_id: str
    building_id: Optional[int] = None
    point_id: Optional[int] = None
    utility_type: str
    severity: str
    ts: int
    kind: str
    value: Optional[float] = None
    message: Optional[str] = None
    cleared: bool
    cleared_at: Optional[int] = None


class AlertListResponse(BaseModel):
    alerts: list[AlertResponse]


class AlertNotificationResponse(BaseModel):
    id: int
    alert_id: Optional[int] = None
    device_id: str
    building_id: Optional[int] = None
    point_id: Optional[int] = None
    utility_type: str
    severity: str
    kind: str
    channel: str
    status: str
    message: Optional[str] = None
    created_at: int
    sent_at: Optional[int] = None


class AlertNotificationListResponse(BaseModel):
    notifications: list[AlertNotificationResponse]
    total: int


class AlertRuleResponse(BaseModel):
    id: int
    building_id: Optional[int] = None
    utility_type: Optional[str] = None
    kind: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    severity: str
    dedupe_sec: Optional[int] = None
    message: Optional[str] = None
    enabled: bool
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


class AlertRuleListResponse(BaseModel):
    rules: list[AlertRuleResponse]
    total: int
    allowed_kinds: list[str]


class AlertRuleMutationResponse(BaseModel):
    ok: bool
    rule: AlertRuleResponse


class OkResponse(BaseModel):
    ok: bool


class AuditLogResponse(BaseModel):
    id: int
    ts: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    detail: Optional[str] = None


class AuditLogListResponse(BaseModel):
    audit_logs: list[AuditLogResponse]
    total: int
    page: int
    pages: int


class MeterReading(BaseModel):
    device_id: str
    reading_id: Optional[str] = None
    sequence_no: Optional[int] = None
    building_id: Optional[int] = None
    point_id: Optional[int] = None
    utility_type: UtilityType = UtilityType.electricity
    sensor_type: Optional[str] = None
    fw_version: Optional[str] = None
    software_version: Optional[str] = None
    hardware_version: Optional[str] = None

    voltage_l1: Optional[float] = None
    voltage_l2: Optional[float] = None
    voltage_l3: Optional[float] = None
    current_l1: Optional[float] = None
    current_l2: Optional[float] = None
    current_l3: Optional[float] = None
    power_w: Optional[float] = None
    power_var: Optional[float] = None
    frequency: Optional[float] = None
    pf: Optional[float] = None
    energy_kwh: Optional[float] = None
    energy_t1: Optional[float] = None
    energy_t2: Optional[float] = None
    energy_t3: Optional[float] = None
    energy_t4: Optional[float] = None
    relay_on: Optional[bool] = None

    pressure_bar: Optional[float] = None
    pressure_bottom_bar: Optional[float] = None
    pressure_top_bar: Optional[float] = None
    flow_rate: Optional[float] = None
    volume_m3: Optional[float] = None
    temperature_c: Optional[float] = None
    leak_detected: Optional[bool] = None
    valve_open: Optional[bool] = None


class MeterReadingBatch(BaseModel):
    device_id: Optional[str] = None
    readings: list[MeterReading]


class DeviceStatus(BaseModel):
    device_id: str
    ip: Optional[str] = None
    rssi: Optional[int] = None
    online: bool = True
    hardware_version: Optional[str] = None
    software_version: Optional[str] = None
    firmware_mode: Optional[FirmwareMode] = None
    build_number: Optional[str] = None


class RelayCommand(BaseModel):
    action: str


class CommandCreate(BaseModel):
    action: str
    params: Optional[dict] = None


class CommandQueuedResponse(BaseModel):
    ok: bool
    cmd_id: int
    expires_at: Optional[int] = None


class TaskQueuedResponse(BaseModel):
    ok: bool
    task_id: str
    status: str


class BackupInfo(BaseModel):
    filename: str
    size: int
    created_at: int


class BackupListResponse(BaseModel):
    backups: list[BackupInfo]
    total: int
    keep_days: int


class BackupTaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


class BackupDeleteResponse(BaseModel):
    ok: bool
    filename: str
    size: int


class FirmwareCompatibilityCreate(BaseModel):
    utility_type: Optional[UtilityType] = None
    firmware_mode: Optional[FirmwareMode] = None
    device_role: Optional[DeviceRole] = None
    hardware_version: Optional[str] = None
    sensor_type: Optional[str] = None
    converter_type: Optional[str] = None
    notes: Optional[str] = None
