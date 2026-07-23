import { useMemo } from 'react'
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Droplets, Flame, Zap, Sprout, Volume2 } from 'lucide-react'
import { useHourlyStats } from '@/hooks/queries'
import { useTheme } from '@/contexts/ThemeContext'
import { chartTheme } from '@/lib/chartTheme'
import { ChartSkeleton } from '@/components/Skeleton'
import type { HourlyUtilityStat } from '@/types/api'

type UtilityKey = 'electricity' | 'water' | 'gas' | 'soil' | 'sound'

interface UtilityChartsPanelProps {
  buildingId?: number
  title?: string
  subtitle?: string
}

interface BucketRow {
  timestamp: number
  label: string
  pressureSamples: number
  power: number
  energy: number
  pressure: number
  pressureTop: number
  flow: number
  humidity: number
  level: number
}

const utilityCards = [
  {
    key: 'electricity' as const,
    title: 'Elektr sarfi',
    subtitle: "Barcha binolar quvvati yig'indisi",
    unit: 'W / kWh',
    icon: Zap,
    color: '#EAB308',
    fill: 'url(#electricityFill)',
  },
  {
    key: 'water' as const,
    title: 'Suv bosimi',
    subtitle: "Bosim o'rtachasi va flow yig'indisi",
    unit: 'bar / flow',
    icon: Droplets,
    color: '#06B6D4',
    fill: 'url(#waterFill)',
  },
  {
    key: 'gas' as const,
    title: 'Gaz bosimi',
    subtitle: "Bosim o'rtachasi va flow yig'indisi",
    unit: 'bar / flow',
    icon: Flame,
    color: '#F97316',
    fill: 'url(#gasFill)',
  },
  {
    key: 'soil' as const,
    title: "Yerto'la namligi",
    subtitle: 'Namlik foizi (oxirgi 24 soat)',
    unit: '%',
    icon: Sprout,
    color: '#22C55E',
    fill: 'url(#soilFill)',
  },
  {
    key: 'sound' as const,
    title: 'Ovoz darajasi',
    subtitle: 'Ovoz intensivligi (oxirgi 24 soat)',
    unit: '%',
    icon: Volume2,
    color: '#A855F7',
    fill: 'url(#soundFill)',
  },
]

function formatLabel(ts: number) {
  try {
    return new Date(ts * 1000).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return String(ts)
  }
}

function createEmptyRows(): BucketRow[] {
  const now = Math.floor(Date.now() / 1000)
  const currentHour = now - (now % 3600)
  return Array.from({ length: 24 }, (_, index) => {
    const ts = currentHour - (23 - index) * 3600
    return {
      timestamp: ts,
      label: formatLabel(ts),
      pressureSamples: 0,
      power: 0,
      energy: 0,
      pressure: 0,
      pressureTop: 0,
      flow: 0,
      humidity: 0,
      level: 0,
    }
  })
}

function aggregateRows(rows: HourlyUtilityStat[], utilityType: UtilityKey): BucketRow[] {
  const buckets = new Map<number, BucketRow>()

  rows
    .filter((row) => row.utility_type === utilityType)
    .forEach((row) => {
      const samples = Math.max(row.samples || 1, 1)
      const current = buckets.get(row.bucket_ts) ?? {
        timestamp: row.bucket_ts,
        label: formatLabel(row.bucket_ts),
        pressureSamples: 0,
        power: 0,
        energy: 0,
        pressure: 0,
        pressureTop: 0,
        flow: 0,
        humidity: 0,
        level: 0,
      }

      current.power += row.avg_power_w ?? 0
      current.energy += row.max_energy_kwh ?? 0
      current.pressure += (row.avg_pressure_bottom_bar ?? row.avg_pressure_bar ?? 0) * samples
      current.pressureTop += (row.avg_pressure_top_bar ?? 0) * samples
      current.flow += row.avg_flow_rate ?? 0
      current.humidity += (row.avg_humidity ?? 0) * samples
      current.level += (row.avg_level ?? 0) * samples
      current.pressureSamples += samples
      buckets.set(row.bucket_ts, current)
    })

  return Array.from(buckets.values())
    .sort((a, b) => a.timestamp - b.timestamp)
    .map((row) => ({
      ...row,
      power: Number(row.power.toFixed(1)),
      energy: Number(row.energy.toFixed(3)),
      pressure: row.pressureSamples ? Number((row.pressure / row.pressureSamples).toFixed(3)) : 0,
      pressureTop: row.pressureSamples ? Number((row.pressureTop / row.pressureSamples).toFixed(3)) : 0,
      flow: Number(row.flow.toFixed(3)),
      humidity: row.pressureSamples ? Number((row.humidity / row.pressureSamples).toFixed(1)) : 0,
      level: row.pressureSamples ? Number((row.level / row.pressureSamples).toFixed(1)) : 0,
    }))
}

export function UtilityChartsPanel({ buildingId, title = 'Kommunal grafiklar', subtitle = "Elektr, suv, gaz, namlik va ovoz — oxirgi 24 soat" }: UtilityChartsPanelProps) {
  const { isDark } = useTheme()
  const chart = chartTheme(isDark)
  const { data, isLoading, isError } = useHourlyStats(24, buildingId)
  const emptyRows = useMemo(() => createEmptyRows(), [])

  const chartRows = useMemo(() => {
    const stats = data?.stats ?? []
    return {
      electricity: aggregateRows(stats, 'electricity'),
      water: aggregateRows(stats, 'water'),
      gas: aggregateRows(stats, 'gas'),
      soil: aggregateRows(stats, 'soil'),
      sound: aggregateRows(stats, 'sound'),
    }
  }, [data])

  if (isLoading) {
    return (
      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-bold text-gray-950 dark:text-gray-100">{title}</h2>
          <p className="text-sm text-gray-500 dark:text-gray-450">{subtitle}</p>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ChartSkeleton titleWidth="w-36" />
          <ChartSkeleton titleWidth="w-36" />
          <ChartSkeleton titleWidth="w-36" />
          <ChartSkeleton titleWidth="w-36" />
          <ChartSkeleton titleWidth="w-36" />
        </div>
      </section>
    )
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-950 dark:text-gray-100">{title}</h2>
        <p className="text-sm text-gray-500 dark:text-gray-450">{subtitle}</p>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {utilityCards.map((card) => {
          const Icon = card.icon
          const rows = chartRows[card.key]
          const hasData = rows.length > 0
          const displayRows = hasData ? rows : emptyRows
          return (
            <div key={card.key} className="glass-card chart-panel rounded-xl p-4 sm:p-5 shadow">
              <div className="flex items-start justify-between gap-4 mb-5">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="rounded-xl border border-gray-300/60 dark:border-gray-800/70 bg-white/45 dark:bg-gray-950/30 p-2.5">
                    <Icon className="w-5 h-5" style={{ color: card.color }} />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-base font-extrabold text-gray-950 dark:text-gray-100 truncate">{card.title}</h3>
                    <p className="text-xs text-gray-500 dark:text-gray-450">{card.subtitle}</p>
                  </div>
                </div>
                <span className="chart-chip">{card.unit}</span>
              </div>

              <div className="relative">
              {card.key === 'electricity' ? (
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={displayRows}>
                    <defs>
                      <linearGradient id="electricityFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#EAB308" stopOpacity={0.32} />
                        <stop offset="95%" stopColor="#EAB308" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 8" stroke={chart.grid} vertical={false} />
                    <XAxis dataKey="label" stroke={chart.axis} tickLine={false} axisLine={false} fontSize={11} />
                    <YAxis stroke={chart.axis} tickLine={false} axisLine={false} fontSize={11} width={42} />
                    <Tooltip contentStyle={chart.tooltip} labelStyle={{ color: chart.label, fontWeight: 800 }} cursor={chart.cursor} />
                    <Area type="monotone" dataKey="power" name="Jami quvvat (W)" stroke="#EAB308" strokeWidth={2.5} dot={false} fill={card.fill} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : card.key === 'soil' ? (
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={displayRows}>
                    <defs>
                      <linearGradient id="soilFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#22C55E" stopOpacity={0.32} />
                        <stop offset="95%" stopColor="#22C55E" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 8" stroke={chart.grid} vertical={false} />
                    <XAxis dataKey="label" stroke={chart.axis} tickLine={false} axisLine={false} fontSize={11} />
                    <YAxis stroke={chart.axis} tickLine={false} axisLine={false} fontSize={11} width={42} domain={[0, 100]} unit="%" />
                    <Tooltip contentStyle={chart.tooltip} labelStyle={{ color: chart.label, fontWeight: 800 }} cursor={chart.cursor} />
                    <Area type="monotone" dataKey="humidity" name="Namlik (%)" stroke="#22C55E" strokeWidth={2.5} dot={false} fill={card.fill} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : card.key === 'sound' ? (
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={displayRows}>
                    <defs>
                      <linearGradient id="soundFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#A855F7" stopOpacity={0.32} />
                        <stop offset="95%" stopColor="#A855F7" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 8" stroke={chart.grid} vertical={false} />
                    <XAxis dataKey="label" stroke={chart.axis} tickLine={false} axisLine={false} fontSize={11} />
                    <YAxis stroke={chart.axis} tickLine={false} axisLine={false} fontSize={11} width={42} domain={[0, 100]} unit="%" />
                    <Tooltip contentStyle={chart.tooltip} labelStyle={{ color: chart.label, fontWeight: 800 }} cursor={chart.cursor} />
                    <Area type="monotone" dataKey="level" name="Ovoz darajasi (%)" stroke="#A855F7" strokeWidth={2.5} dot={false} fill={card.fill} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={displayRows}>
                    <defs>
                      <linearGradient id={card.key === 'water' ? 'waterFill' : 'gasFill'} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={card.color} stopOpacity={0.22} />
                        <stop offset="95%" stopColor={card.color} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 8" stroke={chart.grid} vertical={false} />
                    <XAxis dataKey="label" stroke={chart.axis} tickLine={false} axisLine={false} fontSize={11} />
                    <YAxis stroke={chart.axis} tickLine={false} axisLine={false} fontSize={11} width={42} />
                    <Tooltip contentStyle={chart.tooltip} labelStyle={{ color: chart.label, fontWeight: 800 }} cursor={chart.cursor} />
                    <Line type="monotone" dataKey="pressure" name={card.key === 'water' ? 'Past bosim (bar)' : 'Bosim (bar)'} stroke={card.color} strokeWidth={2.5} dot={false} />
                    {card.key === 'water' && (
                      <Line type="monotone" dataKey="pressureTop" name="Yuqori bosim (bar)" stroke="#8B5CF6" strokeWidth={2.5} dot={false} />
                    )}
                    <Line type="monotone" dataKey="flow" name="Jami flow" stroke="#10B981" strokeWidth={2.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
              {(!hasData || isError) && (
                <div className="pointer-events-none absolute inset-x-0 top-2 flex justify-center">
                  <span className="rounded-full border border-gray-300/70 bg-white/80 px-3 py-1 text-[11px] font-bold text-gray-500 shadow-sm backdrop-blur dark:border-gray-800 dark:bg-gray-950/75 dark:text-gray-400">
                    {isError ? 'Statistika olinmadi' : "O'lchov kelganda grafik to'ladi"}
                  </span>
                </div>
              )}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
