import { useMemo, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { AreaChart, Area, BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { AlertCircle, Zap, Home, Bell, TrendingUp, PlusCircle, X, Droplets, Flame } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { KPICard } from '@/components/KPICard'
import { useTheme } from '@/contexts/ThemeContext'
import { useSummary, useEnergyAnalytics, useDevices, useAlerts, useWebSocket, useEnergySummary, useBuildings } from '@/hooks/queries'
import { translations } from '@/i18n/translations'
import { Device, WebSocketMessage } from '@/types/api'
import apiClient from '@/lib/api'
import { chartTheme } from '@/lib/chartTheme'
import { EmptyBlock } from '@/components/StateBlock'
import { notifySuccess } from '@/lib/toast'
import { ChartSkeleton, KPISkeletonGrid, TableSkeleton } from '@/components/Skeleton'

const utilityOverview = [
  { key: 'electricity', label: 'Elektr', icon: Zap, accent: 'text-yellow-500', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20' },
  { key: 'water', label: 'Suv', icon: Droplets, accent: 'text-cyan-500', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20' },
  { key: 'gas', label: 'Gaz', icon: Flame, accent: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
] as const

export default function DashboardPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { isDark } = useTheme()
  const chart = chartTheme(isDark)
  const { data: summary, isLoading: summaryLoading } = useSummary()
  const { data: devices, isLoading: devicesLoading } = useDevices()
  const { data: buildings } = useBuildings()
  const { data: energyData, isLoading: energyLoading } = useEnergyAnalytics('hour',
    Math.floor((Date.now() - 24 * 60 * 60 * 1000) / 1000),
    Math.floor(Date.now() / 1000)
  )
  const { data: alerts } = useAlerts(false, 5)
  const { data: energySummary, isLoading: energySummaryLoading } = useEnergySummary(30)
  const wsMessage = useWebSocket()
  const [deviceStates, setDeviceStates] = useState<Record<string, boolean>>({})
  const [deviceToAssign, setDeviceToAssign] = useState<Device | null>(null)
  const [assignName, setAssignName] = useState('')
  const [assignBuildingId, setAssignBuildingId] = useState<number | ''>('')

  const assignMutation = useMutation({
    mutationFn: async ({ deviceId, name, buildingId }: { deviceId: string; name: string; buildingId: number }) => {
      await apiClient.put(`/api/devices/${deviceId}`, { name, building_id: buildingId })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
      notifySuccess('Qurilma biriktirildi')
      setDeviceToAssign(null)
    },
  })

  // Handle WebSocket updates
  useEffect(() => {
    if (!wsMessage) return

    if (wsMessage.type === 'device_online' || wsMessage.type === 'device_offline') {
      const deviceId = wsMessage.device_id
      if (deviceId) {
        setDeviceStates((prev) => ({
          ...prev,
          [deviceId]: wsMessage.type === 'device_online',
        }))
      }
    }
  }, [wsMessage])

  const updatedDevices = useMemo(() => {
    if (!devices) return []
    return devices.map((device) => ({
      ...device,
      online: device.id in deviceStates ? deviceStates[device.id] : device.online,
    }))
  }, [devices, deviceStates])

  const unassignedDevices = useMemo(
    () => updatedDevices.filter((d) => d.building_id === null),
    [updatedDevices]
  )

  const assignedDevices = useMemo(
    () => updatedDevices.filter((d) => d.building_id !== null).slice(0, 10),
    [updatedDevices]
  )

  const utilityStats = useMemo(() => {
    return utilityOverview.map((utility) => {
      const rows = updatedDevices.filter((device) => device.utility_type === utility.key)
      return {
        ...utility,
        total: rows.length,
        online: rows.filter((device) => device.online).length,
        offline: rows.filter((device) => !device.online).length,
      }
    })
  }, [updatedDevices])

  const onlinePercent = summary?.devices_total
    ? Math.round(((summary.devices_online || 0) / summary.devices_total) * 100)
    : 0

  // Chart data: convert EnergyPoints to recharts format
  const chartData = useMemo(() => {
    if (!energyData?.data) return []
    return energyData.data.map((p) => ({
      timestamp: p.bucket_ts * 1000,
      value: p.energy_kwh_delta ?? p.energy_kwh_max ?? 0,
    }))
  }, [energyData])

  return (
    <RootLayout>
      <div className="space-y-8">
        <section className="relative overflow-hidden rounded-2xl border border-blue-500/15 bg-gradient-to-br from-blue-600/12 via-emerald-500/8 to-transparent p-5 sm:p-6 shadow-2xl shadow-blue-500/5">
          <div className="absolute inset-0 pointer-events-none bg-dashboard-circuit opacity-50" />
          <div className="relative z-10 flex flex-col lg:flex-row lg:items-end justify-between gap-5">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/20 bg-blue-500/10 px-3 py-1 text-xs font-bold text-blue-600 dark:text-blue-400 mb-4">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                Live utility command center
              </div>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-950 dark:text-gray-100">{translations.dashboard.title}</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-2 font-medium">
                {new Date().toLocaleDateString('uz-UZ', {
                  weekday: 'long',
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                })}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:gap-3 min-w-full lg:min-w-[420px]">
              <div className="rounded-xl border border-gray-300/60 dark:border-gray-800/70 bg-white/45 dark:bg-gray-950/30 p-3">
                <p className="text-[10px] uppercase font-bold text-gray-500">Online</p>
                <p className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400">{onlinePercent}%</p>
              </div>
              <div className="rounded-xl border border-gray-300/60 dark:border-gray-800/70 bg-white/45 dark:bg-gray-950/30 p-3">
                <p className="text-[10px] uppercase font-bold text-gray-500">Alerts</p>
                <p className="text-2xl font-extrabold text-red-600 dark:text-red-400">{summary?.alerts_active || 0}</p>
              </div>
              <div className="rounded-xl border border-gray-300/60 dark:border-gray-800/70 bg-white/45 dark:bg-gray-950/30 p-3">
                <p className="text-[10px] uppercase font-bold text-gray-500">Reads/h</p>
                <p className="text-2xl font-extrabold text-blue-600 dark:text-blue-400">{summary?.reads_last_hour || 0}</p>
              </div>
            </div>
          </div>
        </section>

        {/* Unassigned Devices Banner */}
        {unassignedDevices.length > 0 && (
          <div className="glass-card rounded-xl p-5 border border-yellow-500/30 bg-yellow-550/5 dark:bg-yellow-500/5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <PlusCircle className="w-5 h-5 text-yellow-500 dark:text-yellow-400" />
                <h2 className="text-base font-semibold text-yellow-600 dark:text-yellow-300">
                  Yangi qurilmalar — binoga biriktirilmagan ({unassignedDevices.length})
                </h2>
              </div>
            </div>
            <div className="space-y-2">
              {unassignedDevices.map((device) => (
                <div
                  key={device.id}
                  className="flex items-center justify-between bg-white/50 dark:bg-gray-900/50 rounded-lg px-4 py-3 border border-gray-300 dark:border-gray-700/50"
                >
                  <div className="flex items-center gap-3 text-sm min-w-0">
                    <span
                      className={`shrink-0 w-2 h-2 rounded-full ${device.online ? 'bg-green-500' : 'bg-gray-450'}`}
                    />
                    <div className="min-w-0">
                      <p className="text-gray-950 dark:text-gray-100 font-bold truncate">{device.id}</p>
                      <p className="text-gray-600 dark:text-gray-400 text-xs">
                        {device.meter_serial ? `Serial: ${device.meter_serial}` : device.meter_type || 'Noma\'lum tur'}
                        {device.ip ? ` · IP: ${device.ip}` : ''}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      setDeviceToAssign(device)
                      setAssignName(device.meter_serial || device.id)
                      setAssignBuildingId('')
                    }}
                    className="shrink-0 ml-4 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition"
                  >
                    Binoga biriktirish
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Assign Device Modal */}
        {deviceToAssign && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
            <div className="w-full max-w-md glass-card rounded-2xl p-6 shadow-2xl border border-gray-700">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-lg font-bold text-gray-100">Qurilmani binoga biriktirish</h3>
                <button
                  onClick={() => setDeviceToAssign(null)}
                  className="p-1.5 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-gray-100 transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="mb-4 p-3 rounded-lg bg-gray-100/60 dark:bg-gray-800/50 text-sm text-gray-700 dark:text-gray-400 space-y-1">
                <p><span className="text-gray-950 dark:text-gray-300 font-semibold">ID:</span> {deviceToAssign.id}</p>
                {deviceToAssign.meter_serial && (
                  <p><span className="text-gray-950 dark:text-gray-300 font-semibold">Serial:</span> {deviceToAssign.meter_serial}</p>
                )}
                <p><span className="text-gray-950 dark:text-gray-300 font-semibold">Tur:</span> {deviceToAssign.meter_type || deviceToAssign.utility_type}</p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Qurilma nomi</label>
                  <input
                    type="text"
                    value={assignName}
                    onChange={(e) => setAssignName(e.target.value)}
                    placeholder="Masalan: 3-qavat, 12-xona"
                    className="w-full px-3 py-2.5 rounded-lg glass-input text-sm focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-750 dark:text-gray-300 mb-1.5">Bino</label>
                  <select
                    value={assignBuildingId}
                    onChange={(e) => setAssignBuildingId(e.target.value ? Number(e.target.value) : '')}
                    className="w-full px-3 py-2.5 rounded-lg glass-input text-sm focus:outline-none"
                  >
                    <option value="" className="text-gray-900 dark:text-gray-150">— Binoni tanlang —</option>
                    {buildings?.map((b) => (
                      <option key={b.id} value={b.id} className="text-gray-900 dark:text-gray-150">{b.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              {assignMutation.isError && (
                <p className="mt-3 text-xs text-red-400">Xato yuz berdi. Qaytadan urinib ko'ring.</p>
              )}

              <div className="mt-5 flex gap-3">
                <button
                  onClick={() => setDeviceToAssign(null)}
                  className="flex-1 px-4 py-2.5 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 text-sm font-medium transition"
                >
                  Bekor
                </button>
                <button
                  onClick={() => {
                    if (!assignBuildingId || !assignName.trim()) return
                    assignMutation.mutate({
                      deviceId: deviceToAssign.id,
                      name: assignName.trim(),
                      buildingId: assignBuildingId as number,
                    })
                  }}
                  disabled={!assignBuildingId || !assignName.trim() || assignMutation.isPending}
                  className="flex-1 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold transition flex items-center justify-center gap-2"
                >
                  {assignMutation.isPending && (
                    <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent" />
                  )}
                  Saqlash
                </button>
              </div>
            </div>
          </div>
        )}

        {/* KPI Cards */}
        {summaryLoading ? (
          <KPISkeletonGrid />
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <KPICard
              title={translations.kpi.totalDevices}
              value={summary?.devices_total || 0}
              icon={<Zap className="w-5 h-5" />}
              subtitle={`${summary?.devices_online || 0} ${translations.dashboard.online}`}
              color="primary"
            />
            <KPICard
              title={translations.kpi.totalBuildings}
              value={summary?.buildings || 0}
              icon={<Home className="w-5 h-5" />}
              color="green"
            />
            <KPICard
              title={translations.kpi.activeAlerts}
              value={summary?.alerts_active || 0}
              icon={<Bell className="w-5 h-5" />}
              subtitle={`${0} ${translations.alerts.critical}`}
              color={summary?.alerts_active && summary.alerts_active > 0 ? 'red' : 'green'}
            />
            <KPICard
              title={translations.kpi.readingsToday}
              value={summary?.reads_last_hour || 0}
              icon={<TrendingUp className="w-5 h-5" />}
              color="yellow"
            />
          </div>
        )}

        {!devicesLoading && updatedDevices.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {utilityStats.map((utility) => {
              const Icon = utility.icon
              return (
                <button
                  key={utility.key}
                  onClick={() => navigate(`/devices?utility=${utility.key}`)}
                  className="glass-card rounded-xl p-4 text-left border hover:border-blue-500/35 hover:-translate-y-0.5 transition"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-bold text-gray-950 dark:text-gray-100">{utility.label} qurilmalari</p>
                      <p className="text-2xl font-extrabold text-gray-950 dark:text-gray-100 mt-1">{utility.total}</p>
                    </div>
                    <div className={`p-2.5 rounded-lg border ${utility.bg} ${utility.border}`}>
                      <Icon className={`w-5 h-5 ${utility.accent}`} />
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded-lg bg-green-500/10 px-2 py-1.5 text-green-600 dark:text-green-400 font-bold">
                      {utility.online} online
                    </div>
                    <div className="rounded-lg bg-red-500/10 px-2 py-1.5 text-red-600 dark:text-red-400 font-bold">
                      {utility.offline} offline
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Energy Chart */}
          {energyLoading ? (
            <ChartSkeleton titleWidth="w-36" />
          ) : (
          <div className="glass-card chart-panel rounded-xl p-4 sm:p-6 shadow">
            <div className="flex items-start justify-between gap-4 mb-6">
              <div>
                <h2 className="text-xl font-semibold text-gray-950 dark:text-gray-100">{translations.dashboard.energy}</h2>
                <p className="text-xs text-gray-500 dark:text-gray-450 mt-1">Oxirgi 24 soatlik energiya dinamikasi</p>
              </div>
              <span className="chart-chip">kWh</span>
            </div>
            {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.34} />
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="4 8" stroke={chart.grid} vertical={false} />
                <XAxis
                  dataKey="timestamp"
                  stroke={chart.axis}
                  tickLine={false}
                  axisLine={false}
                  fontSize={11}
                  tickFormatter={(value) => {
                    try {
                      return new Date(value).toLocaleTimeString('uz-UZ', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    } catch {
                      return value
                    }
                  }}
                />
                <YAxis stroke={chart.axis} tickLine={false} axisLine={false} fontSize={11} width={42} />
                <Tooltip
                  contentStyle={chart.tooltip}
                  labelStyle={{ color: chart.label, fontWeight: 800 }}
                  cursor={chart.cursor}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#3B82F6"
                  strokeWidth={3}
                  dot={false}
                  activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
                  fillOpacity={1}
                  fill="url(#colorValue)"
                />
              </AreaChart>
            </ResponsiveContainer>
            ) : (
              <EmptyBlock title="Grafik maʼlumoti yo‘q" message="Oxirgi 24 soat uchun energiya ko‘rsatkichlari topilmadi." />
            )}
          </div>
          )}

          {/* Building Wise Energy Summary Chart */}
          {energySummaryLoading ? (
            <ChartSkeleton titleWidth="w-44" />
          ) : (
          <div className="glass-card chart-panel rounded-xl p-4 sm:p-6 shadow">
            <div className="flex items-start justify-between gap-4 mb-6">
              <div>
                <h2 className="text-xl font-semibold text-gray-950 dark:text-gray-100">Binolar bo'yicha sarf</h2>
                <p className="text-xs text-gray-500 dark:text-gray-450 mt-1">Oxirgi 30 kunlik taqqoslash</p>
              </div>
              <span className="chart-chip">30 kun</span>
            </div>
            {energySummary?.summary && energySummary.summary.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={energySummary.summary} barCategoryGap="26%">
                  <CartesianGrid strokeDasharray="4 8" stroke={chart.grid} vertical={false} />
                  <XAxis dataKey="building_name" stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} width={42} />
                  <Tooltip
                    contentStyle={chart.tooltip}
                    labelStyle={{ color: chart.label, fontWeight: 800 }}
                    cursor={{ fill: isDark ? 'rgba(59,130,246,0.08)' : 'rgba(37,99,235,0.08)' }}
                  />
                  <Bar dataKey="total_energy_kwh" name="Sarf (kWh)" fill="#10B981" radius={[8, 8, 3, 3]}>
                    {energySummary.summary.map((_, idx) => (
                      <Cell key={`cell-${idx}`} fill={idx % 2 === 0 ? '#10B981' : '#3B82F6'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyBlock title="Taqqoslash maʼlumoti yo‘q" message="Tahliliy taqqoslash uchun maʼlumot yetarli emas." />
            )}
          </div>
          )}
        </div>

        {/* Devices Table & Alerts Sidebar */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Devices Table */}
          <div className="lg:col-span-2">
            <div className="glass-card rounded-xl p-6 shadow">
              <h2 className="text-xl font-semibold text-gray-950 dark:text-gray-100 mb-6">{translations.devices.title}</h2>

              {devicesLoading ? (
                <TableSkeleton rows={5} />
              ) : assignedDevices && assignedDevices.length > 0 ? (
                <>
                <div className="hidden sm:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-300 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30">
                        <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 font-semibold">
                          {translations.devices.status}
                        </th>
                        <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 font-semibold">
                          {translations.devices.id}
                        </th>
                        <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 font-semibold">
                          {translations.devices.type}
                        </th>
                        <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 font-semibold">
                          {translations.devices.ip}
                        </th>
                        <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 font-semibold">
                          {translations.devices.lastSeen}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {assignedDevices.map((device) => (
                        <tr
                          key={device.id}
                          onClick={() => navigate(`/devices/${device.id}`)}
                          className="border-b border-gray-300 dark:border-gray-750 hover:bg-gray-100/30 dark:hover:bg-gray-800/50 transition cursor-pointer"
                        >
                          <td className="px-4 py-3">
                            <span
                              className={`inline-block w-2.5 h-2.5 rounded-full ${
                                device.online ? 'bg-green-500' : 'bg-red-500'
                              }`}
                            />
                          </td>
                          <td className="px-4 py-3 text-gray-950 dark:text-gray-100 font-bold">{device.id}</td>
                          <td className="px-4 py-3 text-gray-700 dark:text-gray-350">
                            {translations.deviceTypes[device.utility_type as keyof typeof translations.deviceTypes] || device.utility_type}
                          </td>
                          <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{device.ip || '—'}</td>
                          <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                            {device.last_seen
                              ? formatDistanceToNow(new Date(device.last_seen * 1000), {
                                  addSuffix: false,
                                })
                              : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="sm:hidden mobile-card-list">
                  {assignedDevices.map((device) => (
                    <button
                      key={device.id}
                      onClick={() => navigate(`/devices/${device.id}`)}
                      className="mobile-data-card text-left"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-bold text-gray-950 dark:text-gray-100 truncate">{device.name ?? device.id}</p>
                          <p className="text-xs text-gray-500 font-mono truncate">{device.id}</p>
                        </div>
                        <span className={`shrink-0 mt-1 h-2.5 w-2.5 rounded-full ${device.online ? 'bg-green-500' : 'bg-red-500'}`} />
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">{translations.devices.type}</span>
                        <span className="mobile-data-value">
                          {translations.deviceTypes[device.utility_type as keyof typeof translations.deviceTypes] || device.utility_type}
                        </span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">{translations.devices.ip}</span>
                        <span className="mobile-data-value font-mono">{device.ip || '—'}</span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">{translations.devices.lastSeen}</span>
                        <span className="mobile-data-value">
                          {device.last_seen
                            ? formatDistanceToNow(new Date(device.last_seen * 1000), { addSuffix: false })
                            : '—'}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
                </>
              ) : (
                <EmptyBlock
                  title={translations.common.noData}
                  message={
                    unassignedDevices.length > 0
                      ? 'Binoga biriktirilgan qurilmalar yo‘q — yuqoridagi qurilmalarni biriktiring'
                      : 'Hozircha qurilmalar mavjud emas.'
                  }
                />
              )}
            </div>
          </div>

          {/* Alerts Sidebar */}
          <div className="glass-card rounded-xl p-6 shadow">
            <h2 className="text-xl font-semibold text-gray-950 dark:text-gray-100 mb-6 flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-blue-500" />
              {translations.dashboard.activeAlerts}
            </h2>

            {alerts && alerts.length > 0 ? (
              <div className="space-y-3">
                {alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={`p-3 rounded-lg border ${
                      alert.severity === 'critical'
                        ? 'bg-red-500/10 border-red-500/20'
                        : alert.severity === 'warning'
                          ? 'bg-yellow-500/10 border-yellow-500/20'
                          : 'bg-blue-500/10 border-blue-500/20'
                    }`}
                  >
                    <p
                      className={`text-xs font-bold mb-1 ${
                        alert.severity === 'critical'
                          ? 'text-red-550 dark:text-red-400'
                          : alert.severity === 'warning'
                            ? 'text-yellow-600 dark:text-yellow-400'
                            : 'text-blue-600 dark:text-blue-400'
                      }`}
                    >
                      {alert.kind}
                    </p>
                    <p className="text-sm text-gray-800 dark:text-gray-300 font-medium">{alert.message}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-450 mt-2 font-mono">
                      {formatDistanceToNow(new Date(alert.ts * 1000), {
                        addSuffix: true,
                      })}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex justify-center py-8 text-gray-500 dark:text-gray-400 text-sm italic">
                {translations.common.noData}
              </div>
            )}
          </div>
        </div>
      </div>
    </RootLayout>
  )
}
