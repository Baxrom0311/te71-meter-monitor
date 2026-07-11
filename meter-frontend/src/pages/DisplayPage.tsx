import { useEffect, useState, useCallback } from 'react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine } from 'recharts'
import { Zap, Droplets, Flame, Wifi, WifiOff, RefreshCw } from 'lucide-react'
import { API_BASE_URL } from '@/lib/env'
import type { HourlyUtilityStat } from '@/types/api'

const BASE = API_BASE_URL || window.location.origin

interface DisplayData {
  electricity: HourlyUtilityStat[]
  water: HourlyUtilityStat[]
  gas: HourlyUtilityStat[]
}

interface ChartPoint {
  label: string
  value: number | null
}

function fmt(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
}

function buildPoints(stats: HourlyUtilityStat[], key: keyof HourlyUtilityStat): ChartPoint[] {
  const map = new Map<number, { sum: number; n: number }>()
  for (const s of stats) {
    const v = s[key] as number | null
    if (v == null) continue
    const cur = map.get(s.bucket_ts) ?? { sum: 0, n: 0 }
    cur.sum += v
    cur.n += 1
    map.set(s.bucket_ts, cur)
  }

  const now = Math.floor(Date.now() / 1000)
  const start = now - 24 * 3600
  const points: ChartPoint[] = []

  for (let ts = start - (start % 3600); ts <= now; ts += 3600) {
    const entry = map.get(ts)
    points.push({
      label: fmt(ts),
      value: entry ? Number((entry.sum / entry.n).toFixed(2)) : null,
    })
  }
  return points
}

const CHARTS = [
  {
    key: 'electricity' as const,
    dataKey: 'avg_voltage_l1' as keyof HourlyUtilityStat,
    label: 'Elektr kuchlanishi',
    unit: 'V',
    icon: Zap,
    color: '#FACC15',
    glow: 'rgba(250,204,21,0.35)',
    gradient: ['rgba(250,204,21,0.28)', 'rgba(250,204,21,0)'],
    bg: 'from-yellow-950/60 to-slate-950/80',
    border: 'border-yellow-500/25',
    nominal: 220,
  },
  {
    key: 'water' as const,
    dataKey: 'avg_pressure_bar' as keyof HourlyUtilityStat,
    label: 'Suv bosimi',
    unit: 'bar',
    icon: Droplets,
    color: '#22D3EE',
    glow: 'rgba(34,211,238,0.35)',
    gradient: ['rgba(34,211,238,0.28)', 'rgba(34,211,238,0)'],
    bg: 'from-cyan-950/60 to-slate-950/80',
    border: 'border-cyan-500/25',
    nominal: null,
  },
  {
    key: 'gas' as const,
    dataKey: 'avg_pressure_bar' as keyof HourlyUtilityStat,
    label: 'Gaz bosimi',
    unit: 'bar',
    icon: Flame,
    color: '#FB923C',
    glow: 'rgba(251,146,60,0.35)',
    gradient: ['rgba(251,146,60,0.28)', 'rgba(251,146,60,0)'],
    bg: 'from-orange-950/60 to-slate-950/80',
    border: 'border-orange-500/25',
    nominal: null,
  },
]

function Clock() {
  const [time, setTime] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="text-right">
      <div className="text-3xl font-mono font-bold text-white tabular-nums">
        {time.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
      </div>
      <div className="text-xs text-slate-400 mt-0.5">
        {time.toLocaleDateString('uz-UZ', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })}
      </div>
    </div>
  )
}

function LiveDot({ ok }: { ok: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-xs font-semibold">
      <span className={`relative flex h-2.5 w-2.5`}>
        {ok && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />}
        <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${ok ? 'bg-emerald-400' : 'bg-red-500'}`} />
      </span>
      <span className={ok ? 'text-emerald-400' : 'text-red-400'}>
        {ok ? 'JONLI' : 'UZILDI'}
      </span>
    </span>
  )
}

export default function DisplayPage() {
  const [data, setData] = useState<DisplayData | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  const [online, setOnline] = useState(true)
  const [spinning, setSpinning] = useState(false)

  const fetchData = useCallback(async () => {
    setSpinning(true)
    try {
      const res = await fetch(`${BASE}/api/public/display`)
      if (!res.ok) throw new Error()
      const json: DisplayData = await res.json()
      setData(json)
      setLastUpdate(new Date())
      setOnline(true)
    } catch {
      setOnline(false)
    } finally {
      setTimeout(() => setSpinning(false), 600)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, 30_000)
    return () => clearInterval(id)
  }, [fetchData])

  const charts = CHARTS.map((cfg) => ({
    ...cfg,
    points: data ? buildPoints(data[cfg.key], cfg.dataKey) : [],
    latest: data
      ? (() => {
          const arr = data[cfg.key]
          if (!arr.length) return null
          const sorted = [...arr].sort((a, b) => b.bucket_ts - a.bucket_ts)
          const v = sorted[0][cfg.dataKey] as number | null
          return v != null ? Number(v.toFixed(2)) : null
        })()
      : null,
  }))

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-slate-950 text-white select-none">
      {/* Header */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-slate-800/60 bg-slate-950/80 backdrop-blur shrink-0">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/30">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="text-xl font-extrabold tracking-tight text-white">SmartBino</div>
            <div className="text-xs text-slate-400">Kommunal monitoring tizimi</div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3 text-slate-400">
            <LiveDot ok={online} />
            {lastUpdate && (
              <span className="text-xs hidden sm:block">
                Yangilandi: {lastUpdate.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            )}
            <button onClick={fetchData} className="p-1.5 rounded-lg hover:bg-slate-800 transition-colors">
              <RefreshCw className={`w-4 h-4 ${spinning ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <Clock />
        </div>
      </header>

      {/* Charts — 3 teng qism */}
      <div className="flex-1 grid grid-rows-3 gap-0 overflow-hidden">
        {charts.map((cfg, i) => {
          const Icon = cfg.icon
          const hasData = cfg.points.some((p) => p.value != null)
          const gradId = `grad_${cfg.key}`

          return (
            <div
              key={cfg.key}
              className={`relative flex flex-col bg-gradient-to-r ${cfg.bg} border-b border-slate-800/40 overflow-hidden`}
            >
              {/* Glow */}
              <div
                className="pointer-events-none absolute inset-0 opacity-20"
                style={{ background: `radial-gradient(ellipse 60% 50% at 50% 0%, ${cfg.glow}, transparent)` }}
              />

              {/* Sarlavha */}
              <div className="flex items-center justify-between px-8 pt-4 pb-2 shrink-0 relative z-10">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center`}
                    style={{ background: `${cfg.glow}`, border: `1px solid ${cfg.color}40` }}
                  >
                    <Icon className="w-5 h-5" style={{ color: cfg.color }} />
                  </div>
                  <div>
                    <div className="text-base font-extrabold text-white">{cfg.label}</div>
                    <div className="text-xs text-slate-400">Oxirgi 24 soat</div>
                  </div>
                </div>

                {/* Joriy qiymat */}
                <div className="text-right">
                  <div className="text-4xl font-mono font-black tabular-nums" style={{ color: cfg.color }}>
                    {cfg.latest != null ? cfg.latest : '—'}
                    <span className="text-xl font-bold ml-1.5 text-slate-400">{cfg.unit}</span>
                  </div>
                  {cfg.nominal && (
                    <div className="text-xs text-slate-500">nominal: {cfg.nominal} {cfg.unit}</div>
                  )}
                </div>
              </div>

              {/* Chart */}
              <div className="flex-1 px-4 pb-3 relative z-10 min-h-0">
                {!hasData ? (
                  <div className="h-full flex items-center justify-center">
                    <span className="text-sm text-slate-500">O'lchov ma'lumoti kutilmoqda...</span>
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={cfg.points} margin={{ top: 4, right: 24, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={cfg.color} stopOpacity={0.35} />
                          <stop offset="95%" stopColor={cfg.color} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 8" stroke="rgba(148,163,184,0.08)" vertical={false} />
                      <XAxis
                        dataKey="label"
                        tick={{ fontSize: 11, fill: '#64748b' }}
                        tickLine={false}
                        axisLine={false}
                        interval="preserveStartEnd"
                      />
                      <YAxis
                        tick={{ fontSize: 11, fill: '#64748b' }}
                        tickLine={false}
                        axisLine={false}
                        width={48}
                        tickFormatter={(v) => `${v}`}
                      />
                      <Tooltip
                        contentStyle={{
                          background: '#0f172a',
                          border: `1px solid ${cfg.color}40`,
                          borderRadius: 10,
                          fontSize: 13,
                          color: '#f1f5f9',
                        }}
                        labelStyle={{ color: '#94a3b8', fontWeight: 700, marginBottom: 4 }}
                        formatter={(v) => [`${Number(v ?? 0)} ${cfg.unit}`, cfg.label]}
                        cursor={{ stroke: cfg.color, strokeWidth: 1, strokeOpacity: 0.4 }}
                      />
                      {cfg.nominal && (
                        <ReferenceLine
                          y={cfg.nominal}
                          stroke={cfg.color}
                          strokeDasharray="6 4"
                          strokeOpacity={0.4}
                          label={{ value: `${cfg.nominal}${cfg.unit}`, fill: cfg.color, fontSize: 10, opacity: 0.6 }}
                        />
                      )}
                      <Area
                        type="monotone"
                        dataKey="value"
                        stroke={cfg.color}
                        strokeWidth={2.5}
                        fill={`url(#${gradId})`}
                        dot={false}
                        activeDot={{ r: 4, fill: cfg.color, stroke: '#0f172a', strokeWidth: 2 }}
                        connectNulls
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
