import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import {
  AlertCircle, Zap, Home, Bell, TrendingUp,
  Droplets, Flame, Sprout, Volume2, Activity,
  ArrowRight, Wifi, WifiOff, Clock,
} from 'lucide-react'
import clsx from 'clsx'
import { RootLayout } from '@/components/layout/RootLayout'
import { useSummary, useDevices, useAlerts } from '@/hooks/queries'
import { translations } from '@/i18n/translations'
import { KPISkeletonGrid, TableSkeleton } from '@/components/Skeleton'
import { UtilityChartsPanel } from '@/components/UtilityChartsPanel'

const utilityOverview = [
  { key: 'electricity', label: 'Elektr',    icon: Zap,     accent: 'text-yellow-500', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20', ring: 'ring-yellow-500/30' },
  { key: 'water',       label: 'Suv',       icon: Droplets, accent: 'text-cyan-500',   bg: 'bg-cyan-500/10',   border: 'border-cyan-500/20',   ring: 'ring-cyan-500/30'   },
  { key: 'gas',         label: 'Gaz',       icon: Flame,   accent: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/20', ring: 'ring-orange-500/30' },
  { key: 'soil',        label: "Yerto'la",  icon: Sprout,  accent: 'text-green-500',  bg: 'bg-green-500/10',  border: 'border-green-500/20',  ring: 'ring-green-500/30'  },
  { key: 'sound',       label: 'Ovoz',      icon: Volume2, accent: 'text-purple-500', bg: 'bg-purple-500/10', border: 'border-purple-500/20', ring: 'ring-purple-500/30' },
] as const

export default function DashboardPage() {
  const navigate = useNavigate()
  const { data: summary, isLoading: summaryLoading } = useSummary()
  const { data: devices, isLoading: devicesLoading } = useDevices()
  const { data: alerts } = useAlerts(false, 5)

  const assignedDevices = useMemo(
    () => (devices ?? []).filter((d) => d.building_id !== null).slice(0, 10),
    [devices],
  )

  const utilityStats = useMemo(() => {
    return utilityOverview.map((u) => {
      const rows = (devices ?? []).filter((d) => d.utility_type === u.key)
      return { ...u, total: rows.length, online: rows.filter((d) => d.online).length, offline: rows.filter((d) => !d.online).length }
    })
  }, [devices])

  const onlinePercent = summary?.devices_total
    ? Math.round(((summary.devices_online || 0) / summary.devices_total) * 100)
    : 0

  const criticalAlerts = (alerts ?? []).filter(a => a.severity === 'critical').length

  return (
    <RootLayout>
      <div className="space-y-6">

        {/* ── Hero ── */}
        <section className="relative overflow-hidden rounded-2xl border border-blue-500/15 bg-gradient-to-br from-blue-600/12 via-indigo-500/6 to-emerald-500/8 p-6 sm:p-8 shadow-xl shadow-blue-500/5">
          <div className="absolute inset-0 pointer-events-none bg-dashboard-circuit opacity-40" />
          <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-600 dark:text-emerald-400 mb-4">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                Live utility command center
              </div>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-950 dark:text-gray-100 tracking-tight">
                {translations.dashboard.title}
              </h1>
              <p className="text-gray-500 dark:text-gray-400 mt-2 font-medium text-sm">
                {new Date().toLocaleDateString('uz-UZ', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
              </p>
            </div>

            <div className="grid grid-cols-3 gap-3 min-w-full lg:min-w-[380px]">
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/8 p-4 text-center">
                <Wifi className="w-4 h-4 text-emerald-500 mx-auto mb-1.5" />
                <p className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400">{onlinePercent}%</p>
                <p className="text-[10px] uppercase font-bold text-gray-500 mt-0.5">Online</p>
              </div>
              <div className="rounded-xl border border-red-500/20 bg-red-500/8 p-4 text-center">
                <Bell className="w-4 h-4 text-red-500 mx-auto mb-1.5" />
                <p className="text-2xl font-extrabold text-red-600 dark:text-red-400">{summary?.alerts_active || 0}</p>
                <p className="text-[10px] uppercase font-bold text-gray-500 mt-0.5">Alerts</p>
              </div>
              <div className="rounded-xl border border-blue-500/20 bg-blue-500/8 p-4 text-center">
                <Activity className="w-4 h-4 text-blue-500 mx-auto mb-1.5" />
                <p className="text-2xl font-extrabold text-blue-600 dark:text-blue-400">{summary?.reads_last_hour || 0}</p>
                <p className="text-[10px] uppercase font-bold text-gray-500 mt-0.5">Reads/h</p>
              </div>
            </div>
          </div>
        </section>

        {/* ── KPI Cards ── */}
        {summaryLoading ? (
          <KPISkeletonGrid />
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                title: translations.kpi.totalDevices,
                value: summary?.devices_total || 0,
                sub: `${summary?.devices_online || 0} online`,
                icon: Zap,
                iconBg: 'bg-blue-500/10 border-blue-500/20',
                iconColor: 'text-blue-500',
                valueColor: 'text-gray-950 dark:text-gray-100',
                subColor: 'text-blue-500',
              },
              {
                title: translations.kpi.totalBuildings,
                value: summary?.buildings || 0,
                sub: "Ro'yxatdagi binolar",
                icon: Home,
                iconBg: 'bg-emerald-500/10 border-emerald-500/20',
                iconColor: 'text-emerald-500',
                valueColor: 'text-gray-950 dark:text-gray-100',
                subColor: 'text-emerald-500',
              },
              {
                title: translations.kpi.activeAlerts,
                value: summary?.alerts_active || 0,
                sub: `${criticalAlerts} kritik`,
                icon: AlertCircle,
                iconBg: summary?.alerts_active ? 'bg-red-500/10 border-red-500/20' : 'bg-gray-500/10 border-gray-500/20',
                iconColor: summary?.alerts_active ? 'text-red-500' : 'text-gray-400',
                valueColor: summary?.alerts_active ? 'text-red-600 dark:text-red-400' : 'text-gray-950 dark:text-gray-100',
                subColor: summary?.alerts_active ? 'text-red-400' : 'text-gray-400',
              },
              {
                title: translations.kpi.readingsToday,
                value: summary?.reads_last_hour || 0,
                sub: 'So\'ngi soat',
                icon: TrendingUp,
                iconBg: 'bg-yellow-500/10 border-yellow-500/20',
                iconColor: 'text-yellow-500',
                valueColor: 'text-gray-950 dark:text-gray-100',
                subColor: 'text-yellow-500',
              },
            ].map((card) => {
              const Icon = card.icon
              return (
                <div key={card.title} className="glass-card rounded-xl p-5 shadow flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{card.title}</p>
                    <div className={clsx('p-2 rounded-lg border', card.iconBg)}>
                      <Icon className={clsx('w-4 h-4', card.iconColor)} />
                    </div>
                  </div>
                  <p className={clsx('text-3xl font-extrabold tracking-tight', card.valueColor)}>{card.value}</p>
                  <p className={clsx('text-xs font-semibold', card.subColor)}>{card.sub}</p>
                </div>
              )
            })}
          </div>
        )}

        {/* ── Utility Stats ── */}
        {!devicesLoading && (devices ?? []).length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-bold text-gray-950 dark:text-gray-100">Kommunal qurilmalar</h2>
              <button
                onClick={() => navigate('/devices')}
                className="flex items-center gap-1.5 text-xs font-semibold text-blue-500 hover:text-blue-400 transition"
              >
                Barchasini ko'rish
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
              {utilityStats.map((u) => {
                const Icon = u.icon
                const pct = u.total ? Math.round((u.online / u.total) * 100) : 0
                return (
                  <button
                    key={u.key}
                    onClick={() => navigate(`/devices?utility=${u.key}`)}
                    className={clsx(
                      'glass-card rounded-xl p-4 text-left border hover:ring-2 hover:-translate-y-0.5 transition-all',
                      u.border, u.ring,
                    )}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className={clsx('p-2 rounded-lg border', u.bg, u.border)}>
                        <Icon className={clsx('w-4 h-4', u.accent)} />
                      </div>
                      <span className={clsx('text-xs font-bold', u.accent)}>{pct}%</span>
                    </div>
                    <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">{u.label}</p>
                    <p className="text-2xl font-extrabold text-gray-950 dark:text-gray-100 mt-1">{u.total}</p>
                    <div className="mt-2.5 w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 overflow-hidden">
                      <div
                        className={clsx('h-full rounded-full transition-all', u.online ? u.accent.replace('text-', 'bg-') : 'bg-transparent')}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[11px] font-semibold">
                      <span className="flex items-center gap-1 text-emerald-500"><Wifi className="w-3 h-3" />{u.online}</span>
                      <span className="flex items-center gap-1 text-red-400"><WifiOff className="w-3 h-3" />{u.offline}</span>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* ── Charts ── */}
        <UtilityChartsPanel
          title="Kommunal monitoring grafiklari"
          subtitle="Barcha binolar bo'yicha elektr, suv, gaz, namlik va ovoz — oxirgi 24 soat"
        />

        {/* ── Devices + Alerts ── */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">

          {/* Devices table */}
          <div className="lg:col-span-3 glass-card rounded-xl shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-300 dark:border-gray-800 flex items-center justify-between">
              <h2 className="text-base font-bold text-gray-950 dark:text-gray-100">{translations.devices.title}</h2>
              <button
                onClick={() => navigate('/devices')}
                className="flex items-center gap-1 text-xs font-semibold text-blue-500 hover:text-blue-400 transition"
              >
                Hammasi <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {devicesLoading ? (
              <div className="p-5"><TableSkeleton rows={5} /></div>
            ) : assignedDevices.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-300 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30">
                      <th className="text-left px-5 py-3 text-xs text-gray-500 font-semibold uppercase tracking-wide w-10"></th>
                      <th className="text-left px-5 py-3 text-xs text-gray-500 font-semibold uppercase tracking-wide">Qurilma</th>
                      <th className="text-left px-5 py-3 text-xs text-gray-500 font-semibold uppercase tracking-wide">Tur</th>
                      <th className="text-left px-5 py-3 text-xs text-gray-500 font-semibold uppercase tracking-wide">IP</th>
                      <th className="text-left px-5 py-3 text-xs text-gray-500 font-semibold uppercase tracking-wide">Ko'rilgan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assignedDevices.map((device) => {
                      const utTab = utilityOverview.find(u => u.key === device.utility_type)
                      return (
                        <tr
                          key={device.id}
                          onClick={() => navigate(`/devices/${device.id}`)}
                          className="border-b border-gray-200 dark:border-gray-800 hover:bg-gray-100/30 dark:hover:bg-gray-800/40 transition cursor-pointer"
                        >
                          <td className="px-5 py-3.5">
                            <span className={clsx('inline-block w-2.5 h-2.5 rounded-full', device.online ? 'bg-emerald-400 shadow shadow-emerald-400/50' : 'bg-red-400')} />
                          </td>
                          <td className="px-5 py-3.5">
                            <p className="font-bold text-gray-950 dark:text-gray-100 truncate max-w-[140px]">{device.name ?? device.id}</p>
                            {device.name && <p className="text-[11px] text-gray-400 font-mono truncate">{device.id}</p>}
                          </td>
                          <td className="px-5 py-3.5">
                            <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold border', utTab?.bg, utTab?.border, utTab?.accent)}>
                              {translations.deviceTypes[device.utility_type as keyof typeof translations.deviceTypes] || device.utility_type}
                            </span>
                          </td>
                          <td className="px-5 py-3.5 text-gray-500 dark:text-gray-400 font-mono text-xs">{device.ip || '—'}</td>
                          <td className="px-5 py-3.5 text-gray-500 dark:text-gray-400 text-xs">
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3 shrink-0" />
                              {device.last_seen ? formatDistanceToNow(new Date(device.last_seen * 1000), { addSuffix: false }) : '—'}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-gray-500 dark:text-gray-400 text-sm">
                <Home className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p>Binoga biriktirilgan qurilmalar yo'q</p>
                <button onClick={() => navigate('/devices')} className="mt-3 text-xs text-blue-500 hover:text-blue-400 font-semibold transition">
                  Qurilmalar sahifasiga o'tish →
                </button>
              </div>
            )}
          </div>

          {/* Alerts sidebar */}
          <div className="lg:col-span-2 glass-card rounded-xl shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-300 dark:border-gray-800 flex items-center justify-between">
              <h2 className="text-base font-bold text-gray-950 dark:text-gray-100 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-500" />
                {translations.dashboard.activeAlerts}
              </h2>
              <button
                onClick={() => navigate('/alerts')}
                className="flex items-center gap-1 text-xs font-semibold text-blue-500 hover:text-blue-400 transition"
              >
                Hammasi <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="p-4 space-y-2.5 max-h-[480px] overflow-y-auto">
              {alerts && alerts.length > 0 ? (
                alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={clsx(
                      'rounded-xl border p-3.5 transition',
                      alert.severity === 'critical'
                        ? 'bg-red-500/8 border-red-500/20'
                        : alert.severity === 'warning'
                          ? 'bg-yellow-500/8 border-yellow-500/20'
                          : 'bg-blue-500/8 border-blue-500/20',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <span className={clsx(
                        'text-[11px] font-extrabold uppercase tracking-wide',
                        alert.severity === 'critical' ? 'text-red-500' : alert.severity === 'warning' ? 'text-yellow-500' : 'text-blue-500',
                      )}>
                        {alert.kind}
                      </span>
                      <span className={clsx(
                        'shrink-0 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase',
                        alert.severity === 'critical' ? 'bg-red-500/15 text-red-500' : alert.severity === 'warning' ? 'bg-yellow-500/15 text-yellow-500' : 'bg-blue-500/15 text-blue-500',
                      )}>
                        {alert.severity}
                      </span>
                    </div>
                    <p className="text-sm text-gray-800 dark:text-gray-200 font-medium leading-snug">{alert.message}</p>
                    <p className="text-[11px] text-gray-400 mt-2 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDistanceToNow(new Date(alert.ts * 1000), { addSuffix: true })}
                    </p>
                  </div>
                ))
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                  <Bell className="w-8 h-8 mb-2 opacity-30" />
                  <p className="text-sm">{translations.common.noData}</p>
                </div>
              )}
            </div>
          </div>
        </div>

      </div>
    </RootLayout>
  )
}
