import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, RefreshCw, Power, ToggleLeft, ToggleRight, Zap, Info, Clock, Thermometer } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useDeviceById, useDeviceLatest, useDeviceHistory } from '@/hooks/queries'
import { translations } from '@/i18n/translations'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { useTheme } from '@/contexts/ThemeContext'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import apiClient from '@/lib/api'
import { chartTheme } from '@/lib/chartTheme'
import { getApiErrorMessage } from '@/lib/errors'
import { notifySuccess } from '@/lib/toast'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlock'
import { ConfirmDialog } from '@/components/ConfirmDialog'

type PendingCommand =
  | { type: 'reboot' }
  | { type: 'relay'; action: 'on' | 'off' }
  | { type: 'status' }

export default function DeviceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const { isDark } = useTheme()
  const chart = chartTheme(isDark)
  const queryClient = useQueryClient()
  const {
    data: device,
    isLoading,
    isError,
    error: deviceQueryError,
    refetch,
  } = useDeviceById(id || '')
  const { data: latestReading } = useDeviceLatest(id || '')
  const { data: historyData } = useDeviceHistory(id || '', 24)

  const [loadingAction, setLoadingAction] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [pendingCommand, setPendingCommand] = useState<PendingCommand | null>(null)

  if (!id) return <div className="text-red-400 p-8">{translations.common.error}</div>

  const handleReboot = async () => {
    setLoadingAction('reboot')
    setMsg(null)
    try {
      await apiClient.post(`/api/devices/${id}/reboot`)
      notifySuccess('Reboot buyrug‘i yuborildi')
    } catch (err: any) {
      console.error(err)
      setMsg(getApiErrorMessage(err))
    } finally {
      setLoadingAction(null)
    }
  }

  const handleRelay = async (action: 'on' | 'off') => {
    setLoadingAction(`relay-${action}`)
    setMsg(null)
    try {
      await apiClient.post(`/api/devices/${id}/relay`, { action })
      notifySuccess(`Releni ${action === 'on' ? 'yoqish' : 'o‘chirish'} buyrug‘i yuborildi`)
    } catch (err: any) {
      console.error(err)
      setMsg(getApiErrorMessage(err))
    } finally {
      setLoadingAction(null)
    }
  }

  const handleToggleStatus = async () => {
    if (!device) return
    setLoadingAction('status')
    setMsg(null)
    try {
      const nextStatus = !device.is_active
      await apiClient.put(`/api/devices/${id}`, {
        is_active: nextStatus,
        name: device.name || null,
        utility_type: device.utility_type,
      })
      queryClient.invalidateQueries({ queryKey: ['device', id] })
      notifySuccess(`Qurilma statusi ${nextStatus ? 'faollashtirildi' : 'faolsizlantirildi'}`)
    } catch (err: any) {
      console.error(err)
      setMsg(getApiErrorMessage(err))
    } finally {
      setLoadingAction(null)
    }
  }

  const executePendingCommand = () => {
    if (!pendingCommand) return
    if (pendingCommand.type === 'reboot') {
      handleReboot()
    } else if (pendingCommand.type === 'relay') {
      handleRelay(pendingCommand.action)
    } else {
      handleToggleStatus()
    }
    setPendingCommand(null)
  }

  // Chart data: convert historical readings to Recharts format
  const chartData = useMemo(() => {
    if (!historyData?.readings) return []
    // Show older readings first
    return [...historyData.readings]
      .reverse()
      .map((r) => ({
        timestamp: new Date(r.ts * 1000).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' }),
        power: r.power_w ?? 0,
        voltage: r.voltage_l1 ?? 0,
      }))
  }, [historyData])

  return (
    <RootLayout>
      <div className="space-y-6">
        {/* Back Button */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-150 transition text-sm font-semibold"
        >
          <ArrowLeft className="w-4 h-4" />
          {translations.common.back}
        </button>

        {/* Status notification */}
        {msg && (
          <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-sm text-blue-400">
            {msg}
          </div>
        )}

        {/* Device Details */}
        {isLoading ? (
          <LoadingBlock title="Qurilma yuklanmoqda..." message="Qurilma holati va so‘nggi telemetriya olinmoqda." />
        ) : isError ? (
          <ErrorBlock
            title="Qurilma maʼlumotlari olinmadi"
            message={getApiErrorMessage(deviceQueryError)}
            onRetry={() => refetch()}
          />
        ) : device ? (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Main Info */}
              <div className="lg:col-span-2 glass-card rounded-xl p-6 space-y-6 shadow">
                <div className="flex items-center gap-4">
                  <span
                    className={`w-3.5 h-3.5 rounded-full shadow-sm ${
                      device.online ? 'bg-green-500 animate-pulse' : 'bg-red-500'
                    }`}
                  />
                  <h1 className="text-3xl font-bold text-gray-950 dark:text-gray-100">{device.name ?? device.id}</h1>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-6 text-sm">
                  <div>
                    <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">{translations.devices.type}</p>
                    <p className="text-gray-900 dark:text-gray-100 font-semibold">
                      {translations.deviceTypes[device.utility_type as keyof typeof translations.deviceTypes] || device.utility_type}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">{translations.devices.ip}</p>
                    <p className="text-gray-800 dark:text-gray-100 font-mono font-medium">{device.ip ?? '—'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">{translations.devices.firmware}</p>
                    <p className="text-gray-800 dark:text-gray-100 font-mono font-medium">{device.fw_version ?? '—'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">{translations.devices.status}</p>
                    <p className={`font-bold ${device.online ? 'text-green-500' : 'text-red-550'}`}>
                      {device.online ? translations.devices.online : translations.devices.offline}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">{translations.devices.lastSeen}</p>
                    <p className="text-gray-850 dark:text-gray-100 font-semibold">
                      {device.last_seen
                        ? new Date(device.last_seen * 1000).toLocaleString('uz-UZ')
                        : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">Tizim Faolligi</p>
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      device.is_active ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-550'
                    }`}>
                      {device.is_active ? 'Faol' : 'Faol emas'}
                    </span>
                  </div>
                  {device.meter_serial && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">Hisoblagich Seriali</p>
                      <p className="text-gray-900 dark:text-gray-100 font-bold">{device.meter_serial}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Admin Controls Panel */}
              <div className="glass-card rounded-xl p-6 space-y-4 shadow">
                <h3 className="text-lg font-bold text-gray-950 dark:text-gray-100 border-b border-gray-300 dark:border-gray-800 pb-2">Boshqaruv paneli</h3>
                {isAdmin ? (
                  <div className="flex flex-col gap-3">
                    {/* Reboot Button */}
                    <button
                      onClick={() => setPendingCommand({ type: 'reboot' })}
                      disabled={loadingAction !== null}
                      className="flex items-center justify-center gap-2 px-4 py-2.5 bg-yellow-600 hover:bg-yellow-700 disabled:opacity-50 text-white rounded-lg transition text-sm font-semibold shadow-sm"
                    >
                      <RefreshCw className={`w-4 h-4 ${loadingAction === 'reboot' ? 'animate-spin' : ''}`} />
                      Qurilmani reboot qilish
                    </button>

                    {/* Relay Controls */}
                    <div className="grid grid-cols-2 gap-2 mt-1">
                      <button
                        onClick={() => setPendingCommand({ type: 'relay', action: 'on' })}
                        disabled={loadingAction !== null}
                        className="flex items-center justify-center gap-1.5 px-3 py-2.5 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg transition text-xs font-semibold shadow-sm"
                      >
                        <Power className="w-3.5 h-3.5" />
                        Rele ON
                      </button>
                      <button
                        onClick={() => setPendingCommand({ type: 'relay', action: 'off' })}
                        disabled={loadingAction !== null}
                        className="flex items-center justify-center gap-1.5 px-3 py-2.5 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg transition text-xs font-semibold shadow-sm"
                      >
                        <Power className="w-3.5 h-3.5" />
                        Rele OFF
                      </button>
                    </div>

                    {/* Toggle Active Status */}
                    <button
                      onClick={() => setPendingCommand({ type: 'status' })}
                      disabled={loadingAction !== null}
                      className="flex items-center justify-center gap-2 px-4 py-2.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-850 dark:hover:bg-gray-750 text-gray-700 dark:text-gray-200 rounded-lg transition text-sm font-semibold border border-gray-300 dark:border-gray-700 mt-1 shadow-sm"
                    >
                      {device.is_active ? (
                        <>
                          <ToggleLeft className="w-5 h-5 text-red-500" />
                          Faolsizlantirish
                        </>
                      ) : (
                        <>
                          <ToggleRight className="w-5 h-5 text-green-500" />
                          Faollashtirish
                        </>
                      )}
                    </button>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 italic">Boshqaruv amallari faqat administratorlar uchun ruxsat etilgan.</p>
                )}
              </div>
            </div>

            {/* Real-time Telemetry Values */}
            <div className="space-y-4">
              <h3 className="text-xl font-bold text-gray-950 dark:text-gray-100 flex items-center gap-2">
                <Zap className="w-5 h-5 text-blue-500" />
                Real-vaqtdagi ko'rsatkichlar
              </h3>
              {latestReading ? (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                  {latestReading.voltage_l1 !== undefined && latestReading.voltage_l1 !== null && (
                    <div className="glass-card border border-gray-300 dark:border-gray-800 rounded-2xl p-4 flex flex-col justify-between shadow-sm">
                      <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold">Kuchlanish L1</span>
                      <span className="text-2xl font-extrabold text-blue-650 dark:text-blue-400 mt-2 font-mono">{latestReading.voltage_l1} <span className="text-sm font-normal text-gray-500">V</span></span>
                    </div>
                  )}
                  {latestReading.current_l1 !== undefined && latestReading.current_l1 !== null && (
                    <div className="glass-card border border-gray-300 dark:border-gray-800 rounded-2xl p-4 flex flex-col justify-between shadow-sm">
                      <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold">Tok kuchi L1</span>
                      <span className="text-2xl font-extrabold text-yellow-650 dark:text-yellow-450 mt-2 font-mono">{latestReading.current_l1} <span className="text-sm font-normal text-gray-500">A</span></span>
                    </div>
                  )}
                  {latestReading.power_w !== undefined && latestReading.power_w !== null && (
                    <div className="glass-card border border-gray-300 dark:border-gray-800 rounded-2xl p-4 flex flex-col justify-between shadow-sm col-span-2 md:col-span-1">
                      <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold">Faol Quvvat</span>
                      <span className="text-2xl font-extrabold text-green-650 dark:text-green-450 mt-2 font-mono">{latestReading.power_w} <span className="text-sm font-normal text-gray-500">W</span></span>
                    </div>
                  )}
                  {latestReading.energy_kwh !== undefined && latestReading.energy_kwh !== null && (
                    <div className="glass-card border border-gray-300 dark:border-gray-800 rounded-2xl p-4 flex flex-col justify-between shadow-sm">
                      <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold">Jami Energiya</span>
                      <span className="text-2xl font-extrabold text-purple-650 dark:text-purple-450 mt-2 font-mono">{latestReading.energy_kwh} <span className="text-sm font-normal text-gray-500">kWh</span></span>
                    </div>
                  )}
                  {latestReading.frequency !== undefined && latestReading.frequency !== null && (
                    <div className="glass-card border border-gray-300 dark:border-gray-800 rounded-2xl p-4 flex flex-col justify-between shadow-sm">
                      <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold">Chastota</span>
                      <span className="text-2xl font-extrabold text-cyan-650 dark:text-cyan-400 mt-2 font-mono">{latestReading.frequency} <span className="text-sm font-normal text-gray-500">Hz</span></span>
                    </div>
                  )}
                  {latestReading.pf !== undefined && latestReading.pf !== null && (
                    <div className="glass-card border border-gray-300 dark:border-gray-800 rounded-2xl p-4 flex flex-col justify-between shadow-sm">
                      <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold">Power Factor</span>
                      <span className="text-2xl font-extrabold text-orange-650 dark:text-orange-400 mt-2 font-mono">{latestReading.pf}</span>
                    </div>
                  )}
                </div>
              ) : (
                <EmptyBlock
                  title="Ko‘rsatkich kelmagan"
                  message="Qurilmadan hali hech qanday ko‘rsatkich kelib tushmagan."
                />
              )}
            </div>

            {/* Historical chart */}
            {chartData.length > 0 && (
              <div className="glass-card chart-panel rounded-2xl p-6 shadow-sm space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-bold text-gray-950 dark:text-gray-100 flex items-center gap-2">
                      <Clock className="w-5 h-5 text-blue-500" />
                      Quvvat grafigi
                    </h3>
                    <p className="text-xs text-gray-500 dark:text-gray-450 mt-1">Oxirgi 24 soatdagi Power W o'zgarishi</p>
                  </div>
                  <span className="chart-chip">24 soat</span>
                </div>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                      <defs>
                        <linearGradient id="powerGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10B981" stopOpacity={0.2} />
                          <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="4 8" stroke={chart.grid} vertical={false} />
                      <XAxis dataKey="timestamp" stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} />
                      <YAxis stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} width={46} />
                      <Tooltip
                        contentStyle={chart.tooltip}
                        labelStyle={{ color: chart.label, fontWeight: 800 }}
                        cursor={chart.cursor}
                      />
                      <Area type="monotone" dataKey="power" stroke="#10B981" fillOpacity={1} fill="url(#powerGrad)" strokeWidth={3} dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Historical table */}
            {historyData?.readings && historyData.readings.length > 0 && (
              <div className="glass-card data-table-card rounded-2xl overflow-hidden shadow-sm">
                <div className="p-5 border-b border-gray-300 dark:border-gray-800">
                  <h3 className="text-lg font-bold text-gray-950 dark:text-gray-100">O'lchovlar jurnali (Oxirgi 10 ta ko'rsatkich)</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead>
                      <tr className="border-b border-gray-350 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30 text-gray-655 dark:text-gray-400">
                        <th className="px-6 py-4 font-semibold">Vaqt</th>
                        <th className="px-6 py-4 font-semibold">Kuchlanish (V)</th>
                        <th className="px-6 py-4 font-semibold">Tok kuchi (A)</th>
                        <th className="px-6 py-4 font-semibold">Quvvat (W)</th>
                        <th className="px-6 py-4 font-semibold">Energiya (kWh)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-300 dark:divide-gray-850 text-gray-750 dark:text-gray-300">
                      {historyData.readings.slice(0, 10).map((r) => (
                        <tr key={r.id} className="hover:bg-gray-100/30 dark:hover:bg-gray-850/30 transition">
                          <td className="px-6 py-3.5 font-semibold text-gray-850 dark:text-gray-150">{new Date(r.ts * 1000).toLocaleString('uz-UZ')}</td>
                          <td className="px-6 py-3.5 font-mono">{r.voltage_l1 ?? '—'}</td>
                          <td className="px-6 py-3.5 font-mono">{r.current_l1 ?? '—'}</td>
                          <td className="px-6 py-3.5 font-mono text-green-650 dark:text-green-400 font-bold">{r.power_w ?? '—'}</td>
                          <td className="px-6 py-3.5 font-mono text-purple-650 dark:text-purple-400 font-bold">{r.energy_kwh ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        ) : (
          <EmptyBlock title="Qurilma topilmadi" message={translations.common.noData} />
        )}
      </div>
      <ConfirmDialog
        open={pendingCommand !== null}
        title={
          pendingCommand?.type === 'reboot'
            ? 'Qurilmani reboot qilish'
            : pendingCommand?.type === 'relay'
              ? `Releni ${pendingCommand.action === 'on' ? 'yoqish' : 'o‘chirish'}`
              : 'Qurilma statusini o‘zgartirish'
        }
        message={
          pendingCommand?.type === 'reboot'
            ? 'Bu buyruq ESP32 qurilmasini qayta yuklaydi. Amalni davom ettirasizmi?'
            : pendingCommand?.type === 'relay'
              ? 'Bu buyruq qurilma relesiga darhol yuboriladi. Amalni tasdiqlang.'
              : 'Qurilmaning faol/faol emas holati o‘zgartiriladi.'
        }
        confirmLabel="Buyruq yuborish"
        tone={pendingCommand?.type === 'relay' && pendingCommand.action === 'off' ? 'danger' : 'default'}
        pending={loadingAction !== null}
        onConfirm={executePendingCommand}
        onCancel={() => setPendingCommand(null)}
      />
    </RootLayout>
  )
}
