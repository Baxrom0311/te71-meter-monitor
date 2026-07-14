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
import { Droplets, Flame, Zap } from 'lucide-react'

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
    // Insert one warning-high and one warning-low to show zones
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
      <div className="text-3xl font-mono font-black text-white tabular-nums tracking-tight">
        {now.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
      </div>
      <div className="text-xs text-slate-400 mt-1">
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800/60 bg-slate-950/80 backdrop-blur shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center justify-center w-11 h-11 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/30 shrink-0">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-extrabold tracking-tight text-white">
                Turar-joy binosi №23
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-blue-500/15 text-blue-400 border border-blue-500/30 tracking-wider">
                DEMO
              </span>
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              Toshkent shahri, Chilonzor tumani · Kommunal monitoring tizimi
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Live indicator */}
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
      <div className="flex-1 flex flex-col overflow-hidden">
        {CHARTS.map((cfg, ci) => {
          const Icon = cfg.icon
          const pts = baseData.find((d) => d.key === cfg.key)?.points ?? []
          const liveVal = liveValues.find((v) => v.key === cfg.key)?.live ?? cfg.liveBase

          // Replace last data point with animated live value
          const chartData: DataPoint[] = pts.map((p, i) =>
            i === pts.length - 1 ? { ...p, value: liveVal } : p,
          )

          const status = getStatus(liveVal, cfg)
          const gradId = cfg.gradientId
          const isLast = ci === CHARTS.length - 1

          return (
            <div
              key={cfg.key}
              className={`flex-1 flex min-h-0 bg-gradient-to-r ${cfg.bg} ${
                isLast ? '' : 'border-b border-slate-800/50'
              } relative overflow-hidden`}
            >
              {/* Ambient glow */}
              <div
                className="pointer-events-none absolute inset-0 opacity-15"
                style={{
                  background: `radial-gradient(ellipse 55% 80% at 8% 50%, ${cfg.glow}, transparent)`,
                }}
              />

              {/* ── Left status panel ── */}
              <div className="w-52 shrink-0 flex flex-col justify-center px-5 gap-3 relative z-10">
                {/* Icon + label */}
                <div className="flex items-center gap-2.5">
                  <div
                    className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
                    style={{ background: cfg.glow, border: `1px solid ${cfg.color}35` }}
                  >
                    <Icon className="w-4.5 h-4.5" style={{ color: cfg.color }} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-extrabold text-white leading-tight">{cfg.label}</p>
                    <p className="text-[10px] text-slate-500 leading-none mt-0.5">Oxirgi 24 soat</p>
                  </div>
                </div>

                {/* Live value */}
                <div>
                  <div
                    className="text-4xl font-mono font-black tabular-nums leading-none transition-all duration-700"
                    style={{ color: STATUS_COLORS[status] }}
                  >
                    {liveVal.toFixed(cfg.decimals)}
                    <span className="text-lg font-bold ml-1 text-slate-400">{cfg.unit}</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1">
                    nominal: {cfg.nominal} {cfg.unit}
                  </div>
                </div>

                {/* Status badge */}
                <div
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-black tracking-wider w-fit"
                  style={{
                    background: STATUS_BG[status],
                    border: `1px solid ${STATUS_COLORS[status]}35`,
                    color: STATUS_COLORS[status],
                  }}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ background: STATUS_COLORS[status] }}
                  />
                  {STATUS_LABELS[status]}
                </div>

                {/* Threshold legend */}
                <div className="space-y-0.5 mt-1">
                  {cfg.legendRanges.map((r) => (
                    <div key={r.label} className="flex items-center gap-1.5">
                      <span
                        className="w-2 h-2 rounded-sm shrink-0"
                        style={{ background: r.color, opacity: 0.75 }}
                      />
                      <span className="text-[9px] text-slate-500 leading-none">{r.label}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* ── Chart ── */}
              <div className="flex-1 min-w-0 py-3 pr-5 relative z-10">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 6, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={cfg.color} stopOpacity={0.32} />
                        <stop offset="95%" stopColor={cfg.color} stopOpacity={0} />
                      </linearGradient>
                    </defs>

                    <CartesianGrid
                      strokeDasharray="3 8"
                      stroke="rgba(148,163,184,0.07)"
                      vertical={false}
                    />

                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 10, fill: '#475569' }}
                      tickLine={false}
                      axisLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      domain={cfg.domain}
                      tick={{ fontSize: 10, fill: '#475569' }}
                      tickLine={false}
                      axisLine={false}
                      width={52}
                      tickFormatter={(v: number) =>
                        cfg.decimals >= 3 ? v.toFixed(3) : String(v)
                      }
                    />

                    <Tooltip
                      contentStyle={{
                        background: '#0f172a',
                        border: `1px solid ${cfg.color}40`,
                        borderRadius: 10,
                        fontSize: 12,
                        color: '#f1f5f9',
                      }}
                      labelStyle={{ color: '#94a3b8', fontWeight: 700, marginBottom: 4 }}
                      formatter={(v) => [`${Number(v ?? 0).toFixed(cfg.decimals)} ${cfg.unit}`, cfg.label]}
                      cursor={{ stroke: cfg.color, strokeWidth: 1, strokeOpacity: 0.35 }}
                    />

                    {/* ── Reference zones: danger (red) ── */}
                    <ReferenceArea
                      y1={cfg.domain[0]}
                      y2={cfg.dangerLow}
                      fill="rgba(239,68,68,0.13)"
                      stroke="none"
                    />
                    <ReferenceArea
                      y1={cfg.dangerHigh}
                      y2={cfg.domain[1]}
                      fill="rgba(239,68,68,0.13)"
                      stroke="none"
                    />

                    {/* ── Reference zones: warning (yellow) ── */}
                    <ReferenceArea
                      y1={cfg.dangerLow}
                      y2={cfg.warnLow}
                      fill="rgba(234,179,8,0.10)"
                      stroke="none"
                    />
                    <ReferenceArea
                      y1={cfg.warnHigh}
                      y2={cfg.dangerHigh}
                      fill="rgba(234,179,8,0.10)"
                      stroke="none"
                    />

                    {/* ── Threshold lines ── */}
                    <ReferenceLine
                      y={cfg.dangerLow}
                      stroke="#ef4444"
                      strokeDasharray="4 4"
                      strokeOpacity={0.55}
                      strokeWidth={1.5}
                    />
                    <ReferenceLine
                      y={cfg.dangerHigh}
                      stroke="#ef4444"
                      strokeDasharray="4 4"
                      strokeOpacity={0.55}
                      strokeWidth={1.5}
                    />
                    <ReferenceLine
                      y={cfg.warnLow}
                      stroke="#eab308"
                      strokeDasharray="5 4"
                      strokeOpacity={0.5}
                      strokeWidth={1}
                    />
                    <ReferenceLine
                      y={cfg.warnHigh}
                      stroke="#eab308"
                      strokeDasharray="5 4"
                      strokeOpacity={0.5}
                      strokeWidth={1}
                    />

                    {/* ── Nominal line ── */}
                    <ReferenceLine
                      y={cfg.nominal}
                      stroke={cfg.color}
                      strokeDasharray="6 4"
                      strokeOpacity={0.35}
                      strokeWidth={1.5}
                      label={{
                        value: `${cfg.nominal}${cfg.unit}`,
                        fill: cfg.color,
                        fontSize: 9,
                        opacity: 0.5,
                        position: 'insideTopRight',
                      }}
                    />

                    {/* ── Data area ── */}
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke={cfg.color}
                      strokeWidth={2.5}
                      fill={`url(#${gradId})`}
                      dot={false}
                      activeDot={{ r: 4, fill: cfg.color, stroke: '#0f172a', strokeWidth: 2 }}
                      connectNulls
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )
        })}
      </div>

      {/* ── Footer ── */}
      <footer className="px-6 py-1.5 border-t border-slate-800/50 flex items-center justify-between shrink-0">
        <span className="text-[10px] text-slate-600">
          SmartBino · Demo rejim · Haqiqiy ma'lumotlar emas
        </span>
        <div className="flex items-center gap-4">
          {CHARTS.map((cfg) => {
            const liveVal = liveValues.find((v) => v.key === cfg.key)?.live ?? cfg.liveBase
            const status = getStatus(liveVal, cfg)
            const Icon = cfg.icon
            return (
              <div key={cfg.key} className="flex items-center gap-1.5">
                <Icon className="w-3 h-3" style={{ color: cfg.color, opacity: 0.7 }} />
                <span
                  className="text-[10px] font-bold"
                  style={{ color: STATUS_COLORS[status] }}
                >
                  {STATUS_LABELS[status]}
                </span>
              </div>
            )
          })}
        </div>
      </footer>
    </div>
  )
}
