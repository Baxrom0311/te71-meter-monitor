from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[int | None] = mapped_column(Integer)


class Building(Base, TimestampMixin):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    floors: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    entrances_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    utilities: Mapped[list["BuildingUtility"]] = relationship(back_populates="building")
    measurement_points: Mapped[list["MeasurementPoint"]] = relationship(back_populates="building")
    devices: Mapped[list["Device"]] = relationship(back_populates="building")


class BuildingUtility(Base, TimestampMixin):
    __tablename__ = "building_utilities"
    __table_args__ = (UniqueConstraint("building_id", "utility_type", name="uq_building_utility"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), nullable=False)
    utility_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    building: Mapped["Building"] = relationship(back_populates="utilities")
    measurement_points: Mapped[list["MeasurementPoint"]] = relationship(back_populates="utility_module")


class Premise(Base, TimestampMixin):
    __tablename__ = "premises"
    __table_args__ = (Index("idx_premises_building_floor", "building_id", "floor", "number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), nullable=False)
    number: Mapped[str] = mapped_column(String(64), nullable=False)
    floor: Mapped[int | None] = mapped_column(Integer)
    premise_type: Mapped[str] = mapped_column(String(32), default="apartment", nullable=False)


class MeasurementPoint(Base, TimestampMixin):
    __tablename__ = "measurement_points"
    __table_args__ = (
        Index("idx_measurement_points_building_utility", "building_id", "utility_type", "is_active"),
        Index("idx_measurement_points_role", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    building_id: Mapped[int | None] = mapped_column(ForeignKey("buildings.id"))
    utility_module_id: Mapped[int | None] = mapped_column(ForeignKey("building_utilities.id"))
    premise_id: Mapped[int | None] = mapped_column(ForeignKey("premises.id"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_points.id"))
    device_id: Mapped[str | None] = mapped_column(String(128), ForeignKey("devices.id"))

    name: Mapped[str | None] = mapped_column(String(255))
    utility_type: Mapped[str] = mapped_column(String(32), default="electricity", nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    sensor_type: Mapped[str | None] = mapped_column(String(64))
    converter_type: Mapped[str | None] = mapped_column(String(64))
    location_name: Mapped[str | None] = mapped_column(String(255))
    meter_serial: Mapped[str | None] = mapped_column(String(128))
    floor: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    building: Mapped["Building | None"] = relationship(back_populates="measurement_points")
    utility_module: Mapped["BuildingUtility | None"] = relationship(back_populates="measurement_points")
    parent: Mapped["MeasurementPoint | None"] = relationship(remote_side=[id])
    readings: Mapped[list["Reading"]] = relationship(back_populates="measurement_point")


class Device(Base, TimestampMixin):
    __tablename__ = "devices"
    __table_args__ = (
        Index("idx_devices_active_last_seen", "is_active", "last_seen"),
        Index("idx_devices_utility_active", "utility_type", "is_active"),
        Index("idx_devices_building_active", "building_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    building_id: Mapped[int | None] = mapped_column(ForeignKey("buildings.id"))
    point_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_points.id"))

    name: Mapped[str | None] = mapped_column(String(255))
    utility_type: Mapped[str] = mapped_column(String(32), default="electricity", nullable=False)
    device_role: Mapped[str | None] = mapped_column(String(64))
    firmware_mode: Mapped[str] = mapped_column(String(32), default="auto", nullable=False)
    meter_type: Mapped[str | None] = mapped_column(String(64), default="unknown")
    meter_serial: Mapped[str | None] = mapped_column(String(128))
    serial_number: Mapped[str | None] = mapped_column(String(128))
    hardware_version: Mapped[str | None] = mapped_column(String(64))
    software_version: Mapped[str | None] = mapped_column(String(64))
    build_number: Mapped[str | None] = mapped_column(String(64))
    api_token_hash: Mapped[str | None] = mapped_column(String(255))
    token_created_at: Mapped[int | None] = mapped_column(Integer)
    baud_rate: Mapped[int | None] = mapped_column(Integer, default=9600)
    chip_model: Mapped[str | None] = mapped_column(String(64))
    rssi: Mapped[int | None] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(String(64))
    fw_version: Mapped[str | None] = mapped_column(String(64))

    building_text: Mapped[str | None] = mapped_column("building", String(255))
    floor_text: Mapped[str | None] = mapped_column("floor", String(64))
    room: Mapped[str | None] = mapped_column(String(64))
    group_name: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen: Mapped[int | None] = mapped_column(Integer)
    registered: Mapped[int | None] = mapped_column(Integer)

    building: Mapped["Building | None"] = relationship(back_populates="devices")
    readings: Mapped[list["Reading"]] = relationship(back_populates="device")


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        Index("idx_readings_device_ts", "device_id", "ts"),
        Index("idx_readings_point_ts", "point_id", "ts"),
        Index("idx_readings_building_ts", "building_id", "ts"),
        Index("idx_readings_ts", "ts"),
        Index("idx_readings_building_utility_ts", "building_id", "utility_type", "ts"),
        UniqueConstraint("device_id", "reading_id", name="uq_device_reading_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False)
    reading_id: Mapped[str | None] = mapped_column(String(128))
    sequence_no: Mapped[int | None] = mapped_column(Integer)
    building_id: Mapped[int | None] = mapped_column(ForeignKey("buildings.id"))
    point_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_points.id"))
    utility_type: Mapped[str] = mapped_column(String(32), default="electricity", nullable=False)
    sensor_type: Mapped[str | None] = mapped_column(String(64))
    ts: Mapped[int] = mapped_column(Integer, nullable=False)

    voltage_l1: Mapped[float | None] = mapped_column(Float)
    voltage_l2: Mapped[float | None] = mapped_column(Float)
    voltage_l3: Mapped[float | None] = mapped_column(Float)
    current_l1: Mapped[float | None] = mapped_column(Float)
    current_l2: Mapped[float | None] = mapped_column(Float)
    current_l3: Mapped[float | None] = mapped_column(Float)
    power_w: Mapped[float | None] = mapped_column(Float)
    power_var: Mapped[float | None] = mapped_column(Float)
    frequency: Mapped[float | None] = mapped_column(Float)
    pf: Mapped[float | None] = mapped_column(Float)
    energy_kwh: Mapped[float | None] = mapped_column(Float)
    energy_t1: Mapped[float | None] = mapped_column(Float)
    energy_t2: Mapped[float | None] = mapped_column(Float)
    energy_t3: Mapped[float | None] = mapped_column(Float)
    energy_t4: Mapped[float | None] = mapped_column(Float)
    relay_on: Mapped[bool | None] = mapped_column(Boolean)

    pressure_bar: Mapped[float | None] = mapped_column(Float)
    pressure_bottom_bar: Mapped[float | None] = mapped_column(Float)
    pressure_top_bar: Mapped[float | None] = mapped_column(Float)
    flow_rate: Mapped[float | None] = mapped_column(Float)
    volume_m3: Mapped[float | None] = mapped_column(Float)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    leak_detected: Mapped[bool | None] = mapped_column(Boolean)
    valve_open: Mapped[bool | None] = mapped_column(Boolean)
    raw_payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int | None] = mapped_column(Integer)

    device: Mapped["Device"] = relationship(back_populates="readings")
    measurement_point: Mapped["MeasurementPoint | None"] = relationship(back_populates="readings")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("idx_alerts_cleared_ts", "cleared", "ts"),
        Index("idx_alerts_device_kind_ts", "device_id", "kind", "ts"),
        Index("idx_alerts_building_cleared_ts", "building_id", "cleared", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    building_id: Mapped[int | None] = mapped_column(ForeignKey("buildings.id"))
    point_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_points.id"))
    utility_type: Mapped[str] = mapped_column(String(32), default="electricity", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="warning", nullable=False)
    ts: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(String(500))
    cleared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cleared_at: Mapped[int | None] = mapped_column(Integer)


class Command(Base):
    __tablename__ = "commands"
    __table_args__ = (
        Index("idx_commands_device_status", "device_id", "status", "id"),
        Index("idx_commands_expires_status", "expires_at", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    param: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[int | None] = mapped_column(Integer)
    sent: Mapped[int | None] = mapped_column(Integer)
    acked: Mapped[int | None] = mapped_column(Integer)
    ack_result: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)


class Firmware(Base):
    __tablename__ = "firmware"
    __table_args__ = (Index("idx_firmware_active_uploaded", "active", "uploaded"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    hardware_version: Mapped[str | None] = mapped_column(String(64))
    firmware_mode: Mapped[str] = mapped_column(String(32), default="auto", nullable=False)
    device_role: Mapped[str | None] = mapped_column(String(64))
    utility_type: Mapped[str | None] = mapped_column(String(32))
    sensor_type: Mapped[str | None] = mapped_column(String(64))
    converter_type: Mapped[str | None] = mapped_column(String(64))
    size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(128))
    uploaded: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    release_notes: Mapped[str | None] = mapped_column(Text)
    compatibility_notes: Mapped[str | None] = mapped_column(Text)

    compatibilities: Mapped[list["FirmwareCompatibility"]] = relationship(
        back_populates="firmware",
        cascade="all, delete-orphan",
    )


class FirmwareCompatibility(Base):
    __tablename__ = "firmware_compatibilities"
    __table_args__ = (
        Index("idx_fw_compat_lookup", "firmware_mode", "hardware_version", "sensor_type", "converter_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    firmware_id: Mapped[int] = mapped_column(ForeignKey("firmware.id"), nullable=False)
    utility_type: Mapped[str | None] = mapped_column(String(32))
    firmware_mode: Mapped[str | None] = mapped_column(String(32))
    device_role: Mapped[str | None] = mapped_column(String(64))
    hardware_version: Mapped[str | None] = mapped_column(String(64))
    sensor_type: Mapped[str | None] = mapped_column(String(64))
    converter_type: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int | None] = mapped_column(Integer)

    firmware: Mapped["Firmware"] = relationship(back_populates="compatibilities")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[int | None] = mapped_column(Integer)
    last_login: Mapped[int | None] = mapped_column(Integer)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_ts", "ts"),
        Index("idx_audit_logs_action_ts", "action", "ts"),
        Index("idx_audit_logs_entity_ts", "entity_type", "entity_id", "ts"),
        Index("idx_audit_logs_user_ts", "user_id", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer)
    username: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[str | None] = mapped_column(Text)
