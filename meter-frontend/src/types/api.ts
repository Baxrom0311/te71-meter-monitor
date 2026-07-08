// User and Auth
export interface User {
  id: number
  username: string
  role: 'admin' | 'user'
  is_active: boolean
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

// Building — backend returns { buildings: Building[], total?: number } or Building for single
export interface Building {
  id: number
  name: string
  address: string | null
  maps_url: string | null
  latitude: number | null
  longitude: number | null
  floors: number
  entrances_count: number
  description: string | null
  is_active: boolean
  created_at: number
  updated_at: number
}

// Device — backend actual shape
export interface Device {
  id: string
  building_id: number | null
  point_id: number | null
  name: string | null
  utility_type: string
  device_role: string | null
  firmware_mode: string
  meter_type: string | null
  meter_serial: string | null
  software_version: string | null
  chip_model: string | null
  rssi: number | null
  ip: string | null
  fw_version: string | null
  building: string | null
  floor: string | null
  room: string | null
  group_name: string | null
  is_active: boolean
  last_seen: number | null  // Unix timestamp seconds
  registered: number | null
  created_at: number
  updated_at: number
  online: boolean
}

// Reading
export interface Reading {
  id: number
  device_id: string
  ts: number
  utility_type: string
  sensor_type: string | null
  voltage_l1: number | null
  voltage_l2: number | null
  voltage_l3: number | null
  current_l1: number | null
  current_l2: number | null
  current_l3: number | null
  power_w: number | null
  frequency: number | null
  pf: number | null
  energy_kwh: number | null
}

export interface DeviceHistoryResponse {
  device_id?: string
  hours?: number
  total?: number
  readings: Reading[]
}

// Alert
export interface Alert {
  id: number
  device_id: string
  building_id: number | null
  point_id: number | null
  utility_type: string
  severity: 'info' | 'warning' | 'critical'
  kind: string
  value: number | null
  message: string | null
  cleared: boolean
  ts: number
  cleared_at: number | null
}

export interface AlertRule {
  id: number
  kind: string
  utility_type: string | null
  building_id: number | null
  min_value: number | null
  max_value: number | null
  severity: 'info' | 'warning' | 'critical' | string
  message: string | null
  dedupe_sec: number
  enabled: boolean
  created_at?: number | null
  updated_at?: number | null
}

// Summary — real /api/summary response
export interface Summary {
  devices_total: number
  devices_online: number
  devices_offline: number
  alerts_active: number
  reads_last_hour: number
  total_energy_kwh: number
  buildings: number
  measurement_points: number
  ws_clients: number
}

export interface BuildingEnergySummaryItem {
  building_id?: number | null
  building_name: string
  total_energy_kwh?: number | null
  avg_power_w?: number | null
}

export interface BuildingsEnergySummaryResponse {
  summary: BuildingEnergySummaryItem[]
  days: number
}

// Analytics
export interface EnergyPoint {
  bucket_ts: number
  building_id?: number | null
  energy_kwh_delta?: number | null
  energy_kwh_max?: number | null
  avg_power_w?: number | null
  samples?: number
  building_name?: string
}

export interface EnergyAnalytics {
  from_ts: number
  to_ts: number
  granularity: string
  total: number
  data: EnergyPoint[]
}

export interface HourlyUtilityStat {
  id: number
  bucket_ts: number
  building_id: number | null
  point_id: number | null
  device_id: string
  utility_type: string
  samples: number
  avg_voltage_l1: number | null
  avg_power_w: number | null
  max_energy_kwh: number | null
  avg_pressure_bar: number | null
  avg_pressure_bottom_bar: number | null
  avg_pressure_top_bar: number | null
  avg_flow_rate: number | null
  max_volume_m3: number | null
  leak_count: number | null
  created_at: number | null
  updated_at: number | null
}

export interface HourlyUtilityStatsResponse {
  stats: HourlyUtilityStat[]
  hours: number
  total: number
}

// Audit Log
export interface AuditLog {
  id: number
  ts: number
  user_id: number | null
  username: string | null
  action: string
  entity_type: string | null
  entity_id: string | null
  detail: string | null
}

export interface AuditLogListResponse {
  audit_logs: AuditLog[]
  total: number
  page: number
  pages: number
}

// Firmware
export interface Firmware {
  id: number
  filename: string
  version: string
  firmware_mode: string
  utility_type: string | null
  device_role?: string | null
  hardware_version?: string | null
  sensor_type?: string | null
  converter_type?: string | null
  size: number | null
  sha256: string | null
  uploaded: number | null
  active: boolean
  is_stable: boolean
  min_version?: string | null
  rollout_percentage?: number
  notes: string | null
}

export interface OtaBatch {
  id: number
  name: string
  firmware_id: number
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled' | string
  devices_per_hour: number
  scheduled_at: number | null
  started_at: number | null
  completed_at: number | null
  total_devices: number
  success_count: number
  failure_count: number
  skipped_count: number
  created_by_user_id: number | null
  created_by_username: string | null
  progress_percentage: number
  pending_count: number
  created_at: number | null
  updated_at: number | null
}

export interface OtaBatchDevice {
  id: number
  batch_id: number
  device_id: string
  status: string
  notified_at: number | null
  completed_at: number | null
  previous_version: string | null
  error_message: string | null
  retry_count: number
}

export interface OtaBatchDetail extends OtaBatch {
  firmware: Firmware
  devices: OtaBatchDevice[]
}

// WebSocket messages
export interface WebSocketMessage {
  type: 'reading' | 'device_online' | 'device_offline' | 'alert' | 'snapshot' | 'readings_batch'
  device_id?: string
  data?: Record<string, unknown>
}
