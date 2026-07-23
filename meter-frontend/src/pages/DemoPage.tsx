import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Droplets, Flame, Zap, Sprout, Volume2 } from 'lucide-react'

// ── Types ────────────────────────────────────────────────────────────────────

interface DataPoint {
  label: string
  value: number
}

// ── Mock data generators ──────────────────────────────────────────────────────

function noise(seed: number): number {
  return (Math.sin(seed * 127.1 + 13.7) + Math.sin(seed * 74.7 + 5.2)) * 0.5
}

function generateVoltage(): DataPoint[] {
  const now = Date.now()
  return Array.from({ length: 24 }, (_, i) => {
    const ts = now - (23 - i) * 3_600_000
    const h = new Date(ts).getHours()
    const label = new Date(ts).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
    const isPeak = (h >= 7 && h <= 9) || (h >= 18 && h <= 22)
    const base = isPeak ? 211 : 221
    let value = base + noise(i) * 7
    if (i === 5) value = 244.5
    if (i === 14) value = 196.8
    if (i === 21) value = 252.1
    if (i === 3) value = 187.4
    return { label, value: +Math.max(183, Math.min(258, value)).toFixed(1) }
  })
}

function generateWater(): DataPoint[] {
  const now = Date.now()
  return Array.from({ length: 24 }, (_, i) => {
    const ts = now - (23 - i) * 3_600_000
    const h = new Date(ts).getHours()
    const label = new Date(ts).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
    const isPeak = (h >= 6 && h <= 9) || (h >= 18 && h <= 21)
    const base = isPeak ? 2.1 : 3.0
    let value = base + noise(i + 50) * 0.45
    if (i === 7) value = 1.3
    if (i === 19) value = 1.2
    if (i === 11) value = 4.8
    return { label, value: +Math.max(0.4, Math.min(6.0, value)).toFixed(2) }
  })
}

function generateGas(): DataPoint[] {
  const now = Date.now()
  return Array.from({ length: 24 }, (_, i) => {
    const ts = now - (23 - i) * 3_600_000
    const h = new Date(ts).getHours()
    const label = new Date(ts).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
    const isPeak = (h >= 6 && h <= 9) || (h >= 18 && h <= 21)
    const base = isPeak ? 0.013 : 0.022
    let value = base + noise(i + 100) * 0.005
    if (i === 8) value = 0.0075
    if (i === 18) value = 0.0085
    if (i === 22) value = 0.038
    return { label, value: +Math.max(0.001, Math.min(0.062, value)).toFixed(4) }
  })
}

function generateSoil(): DataPoint[] {
  const now = Date.now()
  return Array.from({ length: 24 }, (_, i) => {
    const ts = now - (23 - i) * 3_600_000
    const label = new Date(ts).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
    let value = 48.5 + noise(i + 150) * 12.0
    if (i === 6) value = 82.0
    if (i === 15) value = 18.5
    return { label, value: +Math.max(10.0, Math.min(95.0, value)).toFixed(1) }
  })
}

function generateSound(): DataPoint[] {
  const now = Date.now()
  return Array.from({ length: 24 }, (_, i) => {
    const ts = now - (23 - i) * 3_600_000
    const h = new Date(ts).getHours()
    const label = new Date(ts).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
    const isBusy = (h >= 8 && h <= 19)
    const base = isBusy ? 48.0 : 28.0
    let value = base + noise(i + 200) * 14.0
    if (i === 10) value = 72.5
    if (i === 17) value = 88.2
    return { label, value: +Math.max(0.0, Math.min(100.0, value)).toFixed(1) }
  })
}

// ── Threshold config ──────────────────────────────────────────────────────────

const CHARTS = [
  {
    key: 'electricity',
    label: 'Elektr kuchlanishi',
    unit: 'V',
    icon: Zap,
    color: '#FACC15',
    glow: 'rgba(250,204,21,0.28)',
    bg: 'from-yellow-950/70 to-slate-950',
    border: 'border-yellow-500/25',
    gradientId: 'grad_elec',
    nominal: 220,
    domain: [183, 258] as [number, number],
    dangerLow: 190,
    warnLow: 200,
    warnHigh: 240,
    dangerHigh: 250,
    decimals: 1,
    liveBase: 219.5,
    liveAmp: 2.5,
    getPoints: generateVoltage,
    legendRanges: [
      { label: '< 190 V', color: '#ef4444' },
      { label: '190 – 200 V', color: '#eab308' },
      { label: '200 – 240 V', color: '#22c55e' },
      { label: '240 – 250 V', color: '#eab308' },
      { label: '> 250 V', color: '#ef4444' },
    ],
  },
  {
    key: 'water',
    label: 'Suv bosimi',
    unit: 'bar',
    icon: Droplets,
    color: '#22D3EE',
    glow: 'rgba(34,211,238,0.28)',
    bg: 'from-cyan-950/70 to-slate-950',
    border: 'border-cyan-500/25',
    gradientId: 'grad_water',
    nominal: 2.8,
    domain: [0.4, 6.2] as [number, number],
    dangerLow: 1.0,
    warnLow: 1.5,
    warnHigh: 4.5,
    dangerHigh: 5.5,
    decimals: 2,
    liveBase: 2.85,
    liveAmp: 0.1,
    getPoints: generateWater,
    legendRanges: [
      { label: '< 1.0 bar', color: '#ef4444' },
      { label: '1.0 – 1.5 bar', color: '#eab308' },
      { label: '1.5 – 4.5 bar', color: '#22c55e' },
      { label: '4.5 – 5.5 bar', color: '#eab308' },
      { label: '> 5.5 bar', color: '#ef4444' },
    ],
  },
  {
    key: 'gas',
    label: 'Gaz bosimi',
    unit: 'bar',
    icon: Flame,
    color: '#FB923C',
    glow: 'rgba(251,146,60,0.28)',
    bg: 'from-orange-950/70 to-slate-950',
    border: 'border-orange-500/25',
    gradientId: 'grad_gas',
    nominal: 0.02,
    domain: [0.001, 0.062] as [number, number],
    dangerLow: 0.005,
    warnLow: 0.010,
    warnHigh: 0.035,
    dangerHigh: 0.050,
    decimals: 3,
    liveBase: 0.021,
    liveAmp: 0.002,
    getPoints: generateGas,
    legendRanges: [
      { label: '< 0.005 bar', color: '#ef4444' },
      { label: '0.005 – 0.010 bar', color: '#eab308' },
      { label: '0.010 – 0.035 bar', color: '#22c55e' },
      { label: '0.035 – 0.050 bar', color: '#eab308' },
      { label: '> 0.050 bar', color: '#ef4444' },
    ],
  },
  {
    key: 'soil',
    label: "Yerto'la namligi",
    unit: '%',
    icon: Sprout,
    color: '#34D399',
    glow: 'rgba(52,211,153,0.28)',
    bg: 'from-emerald-950/70 to-slate-950',
    border: 'border-emerald-500/25',
    gradientId: 'grad_soil',
    nominal: 45,
    domain: [0, 100] as [number, number],
    dangerLow: 15,
    warnLow: 25,
    warnHigh: 75,
    dangerHigh: 85,
    decimals: 1,
    liveBase: 48.5,
    liveAmp: 2.0,
    getPoints: generateSoil,
    legendRanges: [
      { label: '< 15 %', color: '#ef4444' },
      { label: '15 – 25 %', color: '#eab308' },
      { label: '25 – 75 %', color: '#22c55e' },
      { label: '75 – 85 %', color: '#eab308' },
      { label: '> 85 %', color: '#ef4444' },
    ],
  },
  {
    key: 'sound',
    label: 'Shovqin darajasi',
    unit: '%',
    icon: Volume2,
    color: '#C084FC',
    glow: 'rgba(192,132,252,0.28)',
    bg: 'from-purple-950/70 to-slate-950',
    border: 'border-purple-500/25',
    gradientId: 'grad_sound',
    nominal: 40,
    domain: [0, 100] as [number, number],
    dangerLow: 5,
    warnLow: 10,
    warnHigh: 70,
    dangerHigh: 85,
    decimals: 1,
    liveBase: 43.2,
    liveAmp: 3.5,
    getPoints: generateSound,
    legendRanges: [
      { label: '< 5 %', color: '#ef4444' },
      { label: '5 – 10 %', color: '#eab308' },
      { label: '10 – 70 %', color: '#22c55e' },
      { label: '70 – 85 %', color: '#eab308' },
      { label: '> 85 %', color: '#ef4444' },
    ],
  },
]

// ── Status helper ─────────────────────────────────────────────────────────────

type StatusLevel = 'normal' | 'warn' | 'danger'

function getStatus(
  value: number,
  cfg: { dangerLow: number; warnLow: number; warnHigh: number; dangerHigh: number },
): StatusLevel {
  if (value <= cfg.dangerLow || value >= cfg.dangerHigh) return 'danger'
  if (value <= cfg.warnLow || value >= cfg.warnHigh) return 'warn'
  return 'normal'
}

const STATUS_LABELS: Record<StatusLevel, string> = {
  normal: 'NORMAL',
  warn: 'EHTIYOT',
  danger: 'XATARLI',
}
const STATUS_COLORS: Record<StatusLevel, string> = {
  normal: '#22c55e',
  warn: '#eab308',
  danger: '#ef4444',
}
const STATUS_BG: Record<StatusLevel, string> = {
  normal: 'rgba(34,197,94,0.12)',
  warn: 'rgba(234,179,8,0.12)',
  danger: 'rgba(239,68,68,0.12)',
}

// ── Clock component ───────────────────────────────────────────────────────────

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="text-right leading-none">
      <div className="text-2xl lg:text-3xl font-mono font-black text-white tabular-nums tracking-tight">
        {now.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
      </div>
      <div className="text-[11px] text-slate-400 mt-1">
        {now.toLocaleDateString('uz-UZ', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function DemoPage() {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 3000)
    return () => clearInterval(id)
  }, [])

  const baseData = useMemo(
    () => CHARTS.map((cfg) => ({ key: cfg.key, points: cfg.getPoints() })),
    [],
  )

  // Animate the last point every tick
  const liveValues = useMemo(
    () =>
      CHARTS.map((cfg) => {
        const live = +(cfg.liveBase + Math.sin(tick * 0.8 + cfg.liveBase) * cfg.liveAmp).toFixed(cfg.decimals)
        return { key: cfg.key, live }
      }),
    [tick],
  )

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-slate-950 text-white select-none">
      {/* ── Header ── */}
      <header className="flex items-center justify-between px-6 py-2.5 border-b border-slate-800/60 bg-slate-950/80 backdrop-blur shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/30 shrink-0">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-extrabold tracking-tight text-white">
                Turar-joy binosi №23
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-blue-500/15 text-blue-400 border border-blue-500/30 tracking-wider">
                DEMO
              </span>
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Xorazm viloyati, Urganch shahri · Yagona 5-in-1 Kommunal Monitoring Ekran
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-400" />
            </span>
            <span className="text-xs font-semibold text-emerald-400">JONLI</span>
          </div>
          <Clock />
        </div>
      </header>

      {/* ── Chart rows ── */}
      <div className="flex-1 flex flex-col overflow-y-auto min-h-0 divide-y divide-slate-800/40">
        {CHARTS.map((cfg, ci) => {
          const Icon = cfg.icon
          const pts = baseData.find((d) => d.key === cfg.key)?.points ?? []
          const liveVal = liveValues.find((v) => v.key === cfg.key)?.live ?? cfg.liveBase

          const chartData: DataPoint[] = pts.map((p, i) =>
            i === pts.length - 1 ? { ...p, value: liveVal } : p,
          )

          const status = getStatus(liveVal, cfg)
          const gradId = cfg.gradientId

          return (
            <div
              key={cfg.key}
              className={`flex-1 flex min-h-[140px] bg-gradient-to-r ${cfg.bg} relative overflow-hidden`}
            >
              {/* Ambient glow */}
              <div
                className="absolute inset-0 pointer-events-none opacity-20 transition-opacity duration-1000"
                style={{
                  background: `radial-gradient(ellipse at 80% 50%, ${cfg.glow}, transparent 70%)`,
                }}
              />

              {/* ── Left stats panel ── */}
              <div className="w-64 lg:w-72 shrink-0 p-3.5 flex flex-col justify-between border-r border-slate-800/40 z-10 bg-slate-950/40 backdrop-blur-sm">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
                        style={{ backgroundColor: `${cfg.color}18`, color: cfg.color }}
                      >
                        <Icon className="w-4 h-4" />
                      </div>
                      <span className="text-xs font-bold text-slate-200 tracking-wide uppercase">
                        {cfg.label}
                      </span>
                    </div>

                    {/* Status badge */}
                    <span
                      className="text-[10px] font-black px-2 py-0.5 rounded-full tracking-wider shadow-sm transition-colors duration-500"
                      style={{
                        color: STATUS_COLORS[status],
                        backgroundColor: STATUS_BG[status],
                        border: `1px solid ${STATUS_COLORS[status]}40`,
                      }}
                    >
                      {STATUS_LABELS[status]}
                    </span>
                  </div>

                  {/* Main live value */}
                  <div className="mt-2 flex items-baseline gap-1.5">
                    <span
                      className="text-2xl lg:text-3xl font-mono font-black tracking-tight tabular-nums transition-all duration-700"
                      style={{ color: cfg.color, textShadow: `0 0 16px ${cfg.glow}` }}
                    >
                      {liveVal.toFixed(cfg.decimals)}
                    </span>
                    <span className="text-xs font-semibold text-slate-400">{cfg.unit}</span>
                  </div>
                </div>

                {/* Legend / Range bar */}
                <div className="space-y-1 mt-2">
                  <div className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">
                    Me'yoriy zonalar:
                  </div>
                  <div className="flex gap-1">
                    {cfg.legendRanges.map((r, ri) => (
                      <div
                        key={ri}
                        className="flex-1 h-1.5 rounded-full transition-all duration-300"
                        style={{ backgroundColor: r.color, opacity: 0.8 }}
                        title={r.label}
                      />
                    ))}
                  </div>
                  <div className="flex justify-between text-[9px] text-slate-400 font-mono">
                    <span>{cfg.domain[0]} {cfg.unit}</span>
                    <span>{cfg.domain[1]} {cfg.unit}</span>
                  </div>
                </div>
              </div>

              {/* ── Chart area ── */}
              <div className="flex-1 min-w-0 p-2 z-10 relative">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 16, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={cfg.color} stopOpacity={0.35} />
                        <stop offset="95%" stopColor={cfg.color} stopOpacity={0.0} />
                      </linearGradient>
                    </defs>

                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />

                    <XAxis
                      dataKey="label"
                      stroke="#475569"
                      tick={{ fill: '#64748b', fontSize: 10 }}
                      tickLine={false}
                      axisLine={{ stroke: '#334155' }}
                    />
                    <YAxis
                      domain={cfg.domain}
                      stroke="#475569"
                      tick={{ fill: '#64748b', fontSize: 10 }}
                      tickLine={false}
                      axisLine={false}
                      width={45}
                    />

                    {/* Zone background overlays */}
                    <ReferenceArea
                      y1={cfg.domain[0]}
                      y2={cfg.dangerLow}
                      fill="#ef4444"
                      fillOpacity={0.06}
                    />
                    <ReferenceArea
                      y1={cfg.dangerLow}
                      y2={cfg.warnLow}
                      fill="#eab308"
                      fillOpacity={0.05}
                    />
                    <ReferenceArea
                      y1={cfg.warnLow}
                      y2={cfg.warnHigh}
                      fill="#22c55e"
                      fillOpacity={0.03}
                    />
                    <ReferenceArea
                      y1={cfg.warnHigh}
                      y2={cfg.dangerHigh}
                      fill="#eab308"
                      fillOpacity={0.05}
                    />
                    <ReferenceArea
                      y1={cfg.dangerHigh}
                      y2={cfg.domain[1]}
                      fill="#ef4444"
                      fillOpacity={0.06}
                    />

                    {/* Reference threshold lines */}
                    <ReferenceLine
                      y={cfg.dangerHigh}
                      stroke="#ef4444"
                      strokeDasharray="2 2"
                      strokeOpacity={0.6}
                    />
                    <ReferenceLine
                      y={cfg.warnHigh}
                      stroke="#eab308"
                      strokeDasharray="2 2"
                      strokeOpacity={0.5}
                    />
                    <ReferenceLine
                      y={cfg.warnLow}
                      stroke="#eab308"
                      strokeDasharray="2 2"
                      strokeOpacity={0.5}
                    />
                    <ReferenceLine
                      y={cfg.dangerLow}
                      stroke="#ef4444"
                      strokeDasharray="2 2"
                      strokeOpacity={0.6}
                    />

                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null
                        const d = payload[0].payload as DataPoint
                        const st = getStatus(d.value, cfg)
                        return (
                          <div className="bg-slate-900/95 border border-slate-700/80 rounded-lg p-2.5 shadow-xl backdrop-blur text-xs font-mono">
                            <div className="text-slate-400 font-sans mb-1">{d.label}</div>
                            <div className="flex items-center gap-2">
                              <span className="font-extrabold text-sm" style={{ color: cfg.color }}>
                                {d.value.toFixed(cfg.decimals)} {cfg.unit}
                              </span>
                              <span
                                className="text-[9px] px-1.5 py-0.5 rounded font-bold"
                                style={{
                                  color: STATUS_COLORS[st],
                                  backgroundColor: STATUS_BG[st],
                                }}
                              >
                                {STATUS_LABELS[st]}
                              </span>
                            </div>
                          </div>
                        )
                      }}
                    />

                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke={cfg.color}
                      strokeWidth={2.5}
                      fill={`url(#${gradId})`}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
