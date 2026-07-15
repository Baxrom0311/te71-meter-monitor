import { useState, useMemo } from 'react'
import * as XLSX from 'xlsx'
import { TrendingUp, Download, Calendar, FileSpreadsheet, Filter, Printer } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useEnergyAnalytics, useBuildings, useHourlyStats } from '@/hooks/queries'
import { translations } from '@/i18n/translations'
import { BarChart, Bar, AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { useTheme } from '@/contexts/ThemeContext'
import { chartTheme } from '@/lib/chartTheme'
import { EmptyBlock, ErrorBlock } from '@/components/StateBlock'
import { getApiErrorMessage } from '@/lib/errors'
import { notifySuccess } from '@/lib/toast'
import { ChartSkeleton, TableSkeleton } from '@/components/Skeleton'

export default function AnalyticsPage() {
  const { data: buildings } = useBuildings()
  const { isDark } = useTheme()
  const chart = chartTheme(isDark)

  // Filters State
  const [buildingId, setBuildingId] = useState<string>('')
  const [utilityType, setUtilityType] = useState<'all' | 'electricity' | 'water' | 'gas'>('all')
  const [granularity, setGranularity] = useState<'hour' | 'day' | 'month'>('day')
  const [dateRange, setDateRange] = useState<string>('7d')

  // Date picker states
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')

  // Calculate timestamps based on date range selection
  const { fromTs, toTs } = useMemo(() => {
    const now = Math.floor(Date.now() / 1000)
    let start = now - 7 * 24 * 60 * 60 // Default 7 days
    if (dateRange === '24h') {
      start = now - 24 * 60 * 60
    } else if (dateRange === '30d') {
      start = now - 30 * 24 * 60 * 60
    } else if (dateRange === 'custom') {
      const sDate = customStart ? new Date(customStart).getTime() / 1000 : now - 7 * 24 * 60 * 60
      const eDate = customEnd ? new Date(customEnd).getTime() / 1000 : now
      return { fromTs: Math.floor(sDate), toTs: Math.floor(eDate) }
    }
    return { fromTs: start, toTs: now }
  }, [dateRange, customStart, customEnd])

  const bId = buildingId ? parseInt(buildingId) : undefined
  const hourlyHours = dateRange === '24h' ? 24 : dateRange === '30d' ? 720 : 168

  // Fetch energy analytics
  const { data: analyticsData, isLoading, isError, error: analyticsError, refetch } = useEnergyAnalytics(granularity, fromTs, toTs, bId)
  const { data: hourlyStats, isLoading: hourlyLoading, isError: hourlyIsError, error: hourlyError, refetch: refetchHourly } = useHourlyStats(hourlyHours, bId, utilityType)

  // Chart and Table data formatter
  const formattedData = useMemo(() => {
    if (!analyticsData?.data) return []
    return analyticsData.data.map((p) => {
      let label: string
      try {
        const d = new Date(p.bucket_ts * 1000)
        if (granularity === 'hour') {
          label = d.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
        } else if (granularity === 'day') {
          label = d.toLocaleDateString('uz-UZ', { month: 'short', day: 'numeric' })
        } else {
          label = d.toLocaleDateString('uz-UZ', { year: 'numeric', month: 'short' })
        }
      } catch {
        label = p.bucket_ts.toString()
      }

      return {
        timestamp: p.bucket_ts,
        label,
        energy: p.energy_kwh_delta ?? 0,
        power: p.avg_power_w ?? 0,
        samples: p.samples ?? 0,
      }
    })
  }, [analyticsData, granularity])

  const hourlyChartData = useMemo(() => {
    if (!hourlyStats?.stats) return []
    const buckets = new Map<number, {
      bucket_ts: number
      label: string
      voltage: number
      power: number
      pressure: number
      pressureTop: number
      flow: number
      volume: number
      samples: number
    }>()

    ;[...hourlyStats.stats].reverse().forEach((row) => {
      const current = buckets.get(row.bucket_ts) ?? {
        bucket_ts: row.bucket_ts,
        label: new Date(row.bucket_ts * 1000).toLocaleString('uz-UZ', { month: 'short', day: 'numeric', hour: '2-digit' }),
        voltage: 0,
        power: 0,
        pressure: 0,
        pressureTop: 0,
        flow: 0,
        volume: 0,
        samples: 0,
      }
      const samples = Math.max(row.samples || 1, 1)
      current.voltage += (row.avg_voltage_l1 ?? 0) * samples
      current.power += (row.avg_power_w ?? 0) * samples
      current.pressure += (row.avg_pressure_bottom_bar ?? row.avg_pressure_bar ?? 0) * samples
      current.pressureTop += (row.avg_pressure_top_bar ?? 0) * samples
      current.flow += (row.avg_flow_rate ?? 0) * samples
      current.volume = Math.max(current.volume, row.max_volume_m3 ?? 0)
      current.samples += samples
      buckets.set(row.bucket_ts, current)
    })

    return Array.from(buckets.values()).map((row) => ({
      ...row,
      voltage: row.samples ? Number((row.voltage / row.samples).toFixed(2)) : 0,
      power: row.samples ? Number((row.power / row.samples).toFixed(1)) : 0,
      pressure: row.samples ? Number((row.pressure / row.samples).toFixed(3)) : 0,
      pressureTop: row.samples ? Number((row.pressureTop / row.samples).toFixed(3)) : 0,
      flow: row.samples ? Number((row.flow / row.samples).toFixed(3)) : 0,
      volume: Number(row.volume.toFixed(3)),
    }))
  }, [hourlyStats])

  // CSV Data Export (Dynamic based on selected utility type)
  const handleExportCSV = () => {
    let headers: string[] = []
    let rows: any[] = []

    if (utilityType === 'electricity') {
      headers = ['Vaqt (Timestamp)', 'Sana (Label)', 'Energiya sarfi (kWh)', 'O\'rtacha Quvvat (W)', 'Kuchlanish L1 (V)', 'O\'lchovlar soni']
      rows = hourlyChartData.map(row => {
        const energyRow = formattedData.find(e => Math.abs(e.timestamp - row.bucket_ts) < 1800)
        return [
          row.bucket_ts,
          `"${row.label}"`,
          energyRow ? energyRow.energy.toFixed(2) : '0.00',
          row.power.toFixed(1),
          row.voltage.toFixed(1),
          row.samples
        ]
      })
    } else if (utilityType === 'water') {
      headers = ['Vaqt (Timestamp)', 'Sana (Label)', 'Pastki bosim (bar)', 'Yuqori bosim (bar)', 'Oqim (L/min)', 'Jami hajm (m³)', 'O\'lchovlar soni']
      rows = hourlyChartData.map(row => [
        row.bucket_ts,
        `"${row.label}"`,
        row.pressure.toFixed(3),
        row.pressureTop.toFixed(3),
        row.flow.toFixed(3),
        row.volume.toFixed(3),
        row.samples
      ])
    } else if (utilityType === 'gas') {
      headers = ['Vaqt (Timestamp)', 'Sana (Label)', 'Bosim (bar)', 'Oqim (m³/soat)', 'Jami hajm (m³)', 'O\'lchovlar soni']
      rows = hourlyChartData.map(row => [
        row.bucket_ts,
        `"${row.label}"`,
        row.pressure.toFixed(3),
        row.flow.toFixed(3),
        row.volume.toFixed(3),
        row.samples
      ])
    } else {
      headers = ['Vaqt (Timestamp)', 'Sana (Label)', 'Quvvat (W)', 'Kuchlanish (V)', 'Suv pastki bosim (bar)', 'Suv yuqori bosim (bar)', 'Suv/Gaz oqimi', 'Jami hajm (m³)', 'O\'lchovlar soni']
      rows = hourlyChartData.map(row => [
        row.bucket_ts,
        `"${row.label}"`,
        row.power.toFixed(1),
        row.voltage.toFixed(1),
        row.pressure.toFixed(3),
        row.pressureTop.toFixed(3),
        row.flow.toFixed(3),
        row.volume.toFixed(3),
        row.samples
      ])
    }

    if (rows.length === 0) return
    const csvRows = [headers.join(',')]
    rows.forEach(values => {
      csvRows.push(values.join(','))
    })

    const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + csvRows.join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `analytics_report_${buildingId || 'all'}_${utilityType}_${dateRange}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    notifySuccess('CSV hisoboti muvaffaqiyatli eksport qilindi')
  }

  // Excel Export
  const handleExportExcel = () => {
    const buildingName = buildingId
      ? (buildings?.find(b => b.id.toString() === buildingId)?.name ?? buildingId)
      : 'Barcha binolar'
    const utilLabel = utilityType === 'all' ? 'Barchasi' : utilityType === 'electricity' ? 'Elektr' : utilityType === 'water' ? 'Suv' : 'Gaz'

    const wb = XLSX.utils.book_new()

    // Sheet 1: Energy/Main analytics
    if (formattedData.length > 0 && (utilityType === 'electricity' || utilityType === 'all')) {
      const energySheet = [
        ['METER MONITOR — Elektr sarfi tahlili'],
        [`Bino: ${buildingName}`, `Muddat: ${dateRange}`, `Granularity: ${granularity}`],
        [],
        ['Sana / Vaqt', 'Energiya sarfi (kWh)', "O'rtacha yuklama (W)", "O'lchovlar soni"],
        ...formattedData.map(r => [r.label, r.energy, r.power, r.samples]),
        [],
        ['JAMI:', formattedData.reduce((s, r) => s + r.energy, 0).toFixed(2) + ' kWh'],
        ['O\'RTACHA:', (formattedData.reduce((s, r) => s + r.power, 0) / (formattedData.length || 1)).toFixed(1) + ' W'],
        ['MAX:', Math.max(...formattedData.map(r => r.energy)).toFixed(2) + ' kWh'],
      ]
      const ws = XLSX.utils.aoa_to_sheet(energySheet)
      ws['!cols'] = [{ wch: 22 }, { wch: 20 }, { wch: 20 }, { wch: 16 }]
      XLSX.utils.book_append_sheet(wb, ws, 'Elektr sarfi')
    }

    // Sheet 2: Hourly utility stats
    if (hourlyChartData.length > 0) {
      let headers: string[]
      let dataRows: (string | number)[][]
      if (utilityType === 'electricity' || utilityType === 'all') {
        headers = ['Sana / Vaqt', 'Kuchlanish L1 (V)', "O'rtacha quvvat (W)", "O'lchovlar soni"]
        dataRows = hourlyChartData.map(r => [r.label, r.voltage, r.power, r.samples])
      } else if (utilityType === 'water') {
        headers = ['Sana / Vaqt', 'Pastki bosim (bar)', 'Yuqori bosim (bar)', 'Oqim (L/min)', 'Jami hajm (m³)', "O'lchovlar soni"]
        dataRows = hourlyChartData.map(r => [r.label, r.pressure, r.pressureTop, r.flow, r.volume, r.samples])
      } else {
        headers = ['Sana / Vaqt', 'Bosim (bar)', 'Oqim (m³/h)', 'Jami hajm (m³)', "O'lchovlar soni"]
        dataRows = hourlyChartData.map(r => [r.label, r.pressure, r.flow, r.volume, r.samples])
      }
      const ws2 = XLSX.utils.aoa_to_sheet([
        [`METER MONITOR — ${utilLabel} monitoring`],
        [`Bino: ${buildingName}`, `Muddat: ${dateRange}`],
        [],
        headers,
        ...dataRows,
      ])
      ws2['!cols'] = headers.map((_, i) => ({ wch: i === 0 ? 22 : 18 }))
      XLSX.utils.book_append_sheet(wb, ws2, `${utilLabel} monitoring`)
    }

    XLSX.writeFile(wb, `meter_monitor_${buildingId || 'all'}_${utilityType}_${dateRange}.xlsx`)
    notifySuccess('Excel hisoboti muvaffaqiyatli eksport qilindi')
  }

  // Summary stats
  const summaryStats = useMemo(() => {
    if (utilityType === 'electricity' || utilityType === 'all') {
      if (formattedData.length === 0) return null
      const total = formattedData.reduce((s, r) => s + r.energy, 0)
      const avgPower = formattedData.reduce((s, r) => s + r.power, 0) / formattedData.length
      const maxEnergy = Math.max(...formattedData.map(r => r.energy))
      const minEnergy = Math.min(...formattedData.filter(r => r.energy > 0).map(r => r.energy))
      return [
        { label: 'Jami sarflangan', value: total.toFixed(2), unit: 'kWh', color: 'text-blue-400' },
        { label: "O'rtacha quvvat", value: avgPower.toFixed(1), unit: 'W', color: 'text-green-400' },
        { label: 'Eng yuqori', value: maxEnergy.toFixed(2), unit: 'kWh', color: 'text-red-400' },
        { label: 'Eng past', value: minEnergy.toFixed(2), unit: 'kWh', color: 'text-yellow-400' },
      ]
    } else if (utilityType === 'water') {
      if (hourlyChartData.length === 0) return null
      const maxVol = Math.max(...hourlyChartData.map(r => r.volume))
      const avgPressure = hourlyChartData.reduce((s, r) => s + r.pressure, 0) / hourlyChartData.length
      const avgFlow = hourlyChartData.reduce((s, r) => s + r.flow, 0) / hourlyChartData.length
      return [
        { label: 'Jami hajm', value: maxVol.toFixed(2), unit: 'm³', color: 'text-cyan-400' },
        { label: "O'rtacha oqim", value: avgFlow.toFixed(3), unit: 'L/min', color: 'text-blue-400' },
        { label: "O'rtacha bosim", value: avgPressure.toFixed(3), unit: 'bar', color: 'text-purple-400' },
        { label: "O'lchovlar", value: hourlyChartData.reduce((s, r) => s + r.samples, 0).toString(), unit: 'ta', color: 'text-gray-400' },
      ]
    } else if (utilityType === 'gas') {
      if (hourlyChartData.length === 0) return null
      const maxVol = Math.max(...hourlyChartData.map(r => r.volume))
      const avgFlow = hourlyChartData.reduce((s, r) => s + r.flow, 0) / hourlyChartData.length
      const avgPressure = hourlyChartData.reduce((s, r) => s + r.pressure, 0) / hourlyChartData.length
      return [
        { label: 'Jami hajm', value: maxVol.toFixed(2), unit: 'm³', color: 'text-amber-400' },
        { label: "O'rtacha oqim", value: avgFlow.toFixed(3), unit: 'm³/h', color: 'text-orange-400' },
        { label: "O'rtacha bosim", value: avgPressure.toFixed(3), unit: 'bar', color: 'text-red-400' },
        { label: "O'lchovlar", value: hourlyChartData.reduce((s, r) => s + r.samples, 0).toString(), unit: 'ta', color: 'text-gray-400' },
      ]
    }
    return null
  }, [formattedData, hourlyChartData, utilityType])

  return (
    <RootLayout>
      <div className="space-y-6">
        {/* Print Only Header */}
        <div className="hidden print-header">
          <h1>METER MONITOR — KOMMUNAL HISOBOT</h1>
          <div className="text-sm text-gray-800 mt-2 flex justify-between">
            <span><strong>Bino:</strong> {buildingId ? buildings?.find(b => b.id.toString() === buildingId)?.name : 'Barcha binolar'}</span>
            <span><strong>Sana:</strong> {new Date().toLocaleDateString('uz-UZ')}</span>
            <span><strong>Kommunal filtr:</strong> {utilityType === 'all' ? 'Barchasi' : utilityType === 'electricity' ? 'Elektr' : utilityType === 'water' ? 'Suv' : 'Gaz'}</span>
          </div>
        </div>

        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 no-print">
          <div className="flex items-center gap-3">
            <TrendingUp className="w-8 h-8 text-blue-500" />
            <h1 className="text-3xl font-bold text-gray-100">Kommunal Sarf Tahlili</h1>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => window.print()}
              disabled={hourlyChartData.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition text-sm font-semibold shadow-sm"
            >
              <Printer className="w-4 h-4" />
              PDF
            </button>
            <button
              onClick={handleExportCSV}
              disabled={hourlyChartData.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-200 border border-gray-700 rounded-lg transition text-sm font-semibold shadow-sm"
            >
              <Download className="w-4 h-4" />
              CSV
            </button>
            <button
              onClick={handleExportExcel}
              disabled={formattedData.length === 0 && hourlyChartData.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 text-white rounded-lg transition text-sm font-semibold shadow-sm"
            >
              <FileSpreadsheet className="w-4 h-4" />
              Excel
            </button>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="glass-card rounded-xl p-5 grid grid-cols-1 md:grid-cols-5 gap-4 shadow no-print">
          {/* Building Selector */}
          <div>
            <label className="block text-xs text-gray-500 font-semibold uppercase tracking-wider mb-2">Bino</label>
            <select
              value={buildingId}
              onChange={(e) => setBuildingId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg glass-input text-sm focus:outline-none"
            >
              <option value="">Barcha binolar</option>
              {buildings?.map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-500 font-semibold uppercase tracking-wider mb-2">Kommunal tur</label>
            <select
              value={utilityType}
              onChange={(e) => setUtilityType(e.target.value as 'all' | 'electricity' | 'water' | 'gas')}
              className="w-full px-3 py-2 rounded-lg glass-input text-sm focus:outline-none"
            >
              <option value="all">Barchasi</option>
              <option value="electricity">Elektr</option>
              <option value="water">Suv</option>
              <option value="gas">Gaz</option>
            </select>
          </div>

          {/* Granularity Selector */}
          <div>
            <label className="block text-xs text-gray-500 font-semibold uppercase tracking-wider mb-2">Granulyarlik</label>
            <select
              value={granularity}
              onChange={(e) => setGranularity(e.target.value as 'hour' | 'day' | 'month')}
              className="w-full px-3 py-2 rounded-lg glass-input text-sm focus:outline-none"
            >
              <option value="hour">Soatlik</option>
              <option value="day">Kunlik</option>
              <option value="month">Oylik</option>
            </select>
          </div>

          {/* Quick Date Range */}
          <div>
            <label className="block text-xs text-gray-500 font-semibold uppercase tracking-wider mb-2">Sana oralig'i</label>
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="w-full px-3 py-2 rounded-lg glass-input text-sm focus:outline-none"
            >
              <option value="24h">Oxirgi 24 soat</option>
              <option value="7d">Oxirgi 7 kun</option>
              <option value="30d">Oxirgi 30 kun</option>
              <option value="custom">Boshqa muddat...</option>
            </select>
          </div>

          {/* Info pill */}
          <div className="flex items-center justify-center p-3 bg-blue-500/5 border border-blue-500/10 rounded-lg text-xs text-blue-400">
            <Filter className="w-4 h-4 mr-2 shrink-0" />
            Sarflarni tahlil qilish uchun mos parametrlarni tanlang.
          </div>
        </div>

        {/* Custom Dates (Conditional) */}
        {dateRange === 'custom' && (
          <div className="glass-card rounded-xl p-5 flex flex-wrap gap-4 shadow no-print">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-300">Boshlanish:</span>
              <input
                type="date"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
                className="px-3 py-1.5 rounded-lg glass-input text-sm focus:outline-none"
              />
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-300">Tugash:</span>
              <input
                type="date"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
                className="px-3 py-1.5 rounded-lg glass-input text-sm focus:outline-none"
              />
            </div>
          </div>
        )}

        {/* Loading */}
        {isLoading ? (
          <div className="grid grid-cols-1 gap-6">
            <ChartSkeleton />
            <ChartSkeleton titleWidth="w-52" />
            <TableSkeleton rows={6} />
          </div>
        ) : isError ? (
          <ErrorBlock message={getApiErrorMessage(analyticsError)} onRetry={() => refetch()} />
        ) : formattedData.length > 0 ? (
          <div className="grid grid-cols-1 gap-6">
            {/* Summary Stats Cards */}
            {summaryStats && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 no-print">
                {summaryStats.map((stat, i) => (
                  <div key={i} className="glass-card rounded-xl p-4 shadow-sm flex flex-col justify-between">
                    <span className="text-xs text-gray-500 dark:text-gray-400 font-semibold uppercase tracking-wider">{stat.label}</span>
                    <div className="mt-2 flex items-baseline gap-1">
                      <span className={`text-2xl font-bold font-mono ${stat.color}`}>{stat.value}</span>
                      <span className="text-xs text-gray-550 dark:text-gray-450 font-medium">{stat.unit}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Energy delta chart (AreaChart) */}
            <div className="glass-card chart-panel rounded-xl p-6 shadow-sm space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-bold text-gray-950 dark:text-gray-100">KWh Sarfi</h2>
                  <p className="text-xs text-gray-500 dark:text-gray-450 mt-1">Tanlangan interval bo'yicha energiya delta</p>
                </div>
                <span className="chart-chip">energy</span>
              </div>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={formattedData}>
                    <defs>
                      <linearGradient id="colorEnergy" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.4}/>
                        <stop offset="95%" stopColor="#3B82F6" stopOpacity={0.0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 8" stroke={chart.grid} vertical={false} />
                    <XAxis dataKey="label" stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} width={48} />
                    <Tooltip
                      contentStyle={chart.tooltip}
                      labelStyle={{ color: chart.label, fontSpread: '800' }}
                      cursor={chart.cursor}
                    />
                    <Legend wrapperStyle={{ color: chart.label, fontSize: 12 }} />
                    <Area type="monotone" dataKey="energy" name="Energiya (kWh)" stroke="#3B82F6" strokeWidth={3} fillOpacity={1} fill="url(#colorEnergy)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Average Power chart */}
            <div className="glass-card chart-panel rounded-xl p-6 shadow-sm space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-bold text-gray-950 dark:text-gray-100">O'rtacha yuklama quvvati</h2>
                  <p className="text-xs text-gray-500 dark:text-gray-450 mt-1">Power W trend chizig'i</p>
                </div>
                <span className="chart-chip">power</span>
              </div>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={formattedData}>
                    <CartesianGrid strokeDasharray="4 8" stroke={chart.grid} vertical={false} />
                    <XAxis dataKey="label" stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} width={48} />
                    <Tooltip
                      contentStyle={chart.tooltip}
                      labelStyle={{ color: chart.label, fontWeight: 800 }}
                      cursor={chart.cursor}
                    />
                    <Legend wrapperStyle={{ color: chart.label, fontSize: 12 }} />
                    <Line type="monotone" dataKey="power" name="Quvvat (W)" stroke="#10B981" strokeWidth={3} dot={false} activeDot={{ r: 6, strokeWidth: 2, stroke: '#fff' }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {hourlyLoading ? (
              <ChartSkeleton titleWidth="w-56" />
            ) : hourlyIsError ? (
              <ErrorBlock
                title="Utility statistikasi olinmadi"
                message={getApiErrorMessage(hourlyError)}
                onRetry={() => refetchHourly()}
              />
            ) : hourlyChartData.length > 0 ? (
              <div className="glass-card chart-panel rounded-xl p-6 shadow-sm space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-bold text-gray-950 dark:text-gray-100">Multi-series utility monitoring</h2>
                    <p className="text-xs text-gray-500 dark:text-gray-450 mt-1">Elektr, suv va gaz ko‘rsatkichlari bir grafikda</p>
                  </div>
                  <span className="chart-chip">{utilityType === 'all' ? 'all' : utilityType}</span>
                </div>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={hourlyChartData}>
                      <CartesianGrid strokeDasharray="4 8" stroke={chart.grid} vertical={false} />
                      <XAxis dataKey="label" stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} />
                      <YAxis stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} width={48} />
                      <Tooltip contentStyle={chart.tooltip} labelStyle={{ color: chart.label, fontWeight: 800 }} cursor={chart.cursor} />
                      <Legend wrapperStyle={{ color: chart.label, fontSize: 12 }} />
                      {(utilityType === 'all' || utilityType === 'electricity') && (
                        <>
                          <Line type="monotone" dataKey="voltage" name="Voltage L1 (V)" stroke="#3B82F6" strokeWidth={2.5} dot={false} />
                          <Line type="monotone" dataKey="power" name="Power (W)" stroke="#10B981" strokeWidth={2.5} dot={false} />
                        </>
                      )}
                      {(utilityType === 'all' || utilityType === 'water') && (
                        <>
                          <Line type="monotone" dataKey="pressure" name="Pastki bosim (bar)" stroke="#06B6D4" strokeWidth={2.5} dot={false} />
                          <Line type="monotone" dataKey="pressureTop" name="Yuqori bosim (bar)" stroke="#8B5CF6" strokeWidth={2.5} dot={false} />
                          <Line type="monotone" dataKey="flow" name="Suv oqimi (L/min)" stroke="#3B82F6" strokeWidth={2.5} dot={false} />
                          <Line type="monotone" dataKey="volume" name="Suv hajmi (m³)" stroke="#EC4899" strokeWidth={2.5} dot={false} />
                        </>
                      )}
                      {(utilityType === 'all' || utilityType === 'gas') && (
                        <>
                          <Line type="monotone" dataKey="pressure" name="Gaz bosimi (bar)" stroke="#06B6D4" strokeWidth={2.5} dot={false} />
                          <Line type="monotone" dataKey="flow" name="Gaz oqimi (m³/h)" stroke="#F59E0B" strokeWidth={2.5} dot={false} />
                          <Line type="monotone" dataKey="volume" name="Gaz hajmi (m³)" stroke="#10B981" strokeWidth={2.5} dot={false} />
                        </>
                      )}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <EmptyBlock title="Utility statistikasi yo‘q" message="Tanlangan filtr uchun hourly statistika topilmadi." />
            )}

            {/* Data table */}
            <div className="glass-card data-table-card rounded-xl overflow-hidden shadow-sm">
              <div className="p-5 border-b border-gray-300 dark:border-gray-800 flex justify-between items-center">
                <h3 className="text-lg font-bold text-gray-950 dark:text-gray-100">Tahliliy hisobot jadvali</h3>
                <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">Jami: {utilityType === 'water' || utilityType === 'gas' ? hourlyChartData.length : formattedData.length} ta yozuv</span>
              </div>
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-sm text-left">
                  {utilityType === 'electricity' || utilityType === 'all' ? (
                    <>
                      <thead>
                        <tr className="border-b border-gray-350 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30 text-gray-655 dark:text-gray-400 font-semibold">
                          <th className="px-6 py-4">Sana / Vaqt</th>
                          <th className="px-6 py-4 text-right">Sarflangan Energiya (kWh)</th>
                          <th className="px-6 py-4 text-right">O'rtacha yuklama (W)</th>
                          <th className="px-6 py-4 text-right">O'lchovlar soni</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-300 dark:divide-gray-800 text-gray-750 dark:text-gray-300">
                        {formattedData.map((row, idx) => (
                          <tr key={idx} className="hover:bg-gray-100/30 dark:hover:bg-gray-850/40 transition">
                            <td className="px-6 py-3.5 font-semibold text-gray-850 dark:text-gray-150">{row.label}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-blue-650 dark:text-blue-400 font-bold">{row.energy.toFixed(2)}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-green-650 dark:text-green-400 font-bold">{row.power.toFixed(1)}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-gray-600 dark:text-gray-450">{row.samples}</td>
                          </tr>
                        ))}
                      </tbody>
                    </>
                  ) : utilityType === 'water' ? (
                    <>
                      <thead>
                        <tr className="border-b border-gray-350 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30 text-gray-655 dark:text-gray-400 font-semibold">
                          <th className="px-6 py-4">Sana / Vaqt</th>
                          <th className="px-6 py-4 text-right">Pastki bosim (bar)</th>
                          <th className="px-6 py-4 text-right">Yuqori bosim (bar)</th>
                          <th className="px-6 py-4 text-right">Suv oqimi (L/min)</th>
                          <th className="px-6 py-4 text-right">Jami hajm (m³)</th>
                          <th className="px-6 py-4 text-right">O'lchovlar soni</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-300 dark:divide-gray-800 text-gray-750 dark:text-gray-300">
                        {hourlyChartData.map((row, idx) => (
                          <tr key={idx} className="hover:bg-gray-100/30 dark:hover:bg-gray-850/40 transition">
                            <td className="px-6 py-3.5 font-semibold text-gray-850 dark:text-gray-150">{row.label}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-cyan-600 dark:text-cyan-400 font-bold">{row.pressure.toFixed(3)}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-purple-600 dark:text-purple-400 font-bold">{row.pressureTop.toFixed(3)}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-blue-600 dark:text-blue-400 font-bold">{row.flow.toFixed(3)}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-pink-650 dark:text-pink-400 font-bold">{row.volume.toFixed(3)}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-gray-650 dark:text-gray-450">{row.samples}</td>
                          </tr>
                        ))}
                      </tbody>
                    </>
                  ) : (
                    <>
                      <thead>
                        <tr className="border-b border-gray-350 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30 text-gray-655 dark:text-gray-400 font-semibold">
                          <th className="px-6 py-4">Sana / Vaqt</th>
                          <th className="px-6 py-4 text-right">Gaz bosimi (bar)</th>
                          <th className="px-6 py-4 text-right">Gaz oqimi (m³/h)</th>
                          <th className="px-6 py-4 text-right">Jami hajm (m³)</th>
                          <th className="px-6 py-4 text-right">O'lchovlar soni</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-300 dark:divide-gray-800 text-gray-750 dark:text-gray-300">
                        {hourlyChartData.map((row, idx) => (
                          <tr key={idx} className="hover:bg-gray-100/30 dark:hover:bg-gray-850/40 transition">
                            <td className="px-6 py-3.5 font-semibold text-gray-850 dark:text-gray-150">{row.label}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-cyan-600 dark:text-cyan-400 font-bold">{row.pressure.toFixed(3)}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-amber-600 dark:text-amber-400 font-bold">{row.flow.toFixed(3)}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-emerald-600 dark:text-emerald-450 font-bold">{row.volume.toFixed(3)}</td>
                            <td className="px-6 py-3.5 text-right font-mono text-gray-650 dark:text-gray-450">{row.samples}</td>
                          </tr>
                        ))}
                      </tbody>
                    </>
                  )}
                </table>
              </div>
              <div className="md:hidden mobile-card-list p-3">
                {utilityType === 'electricity' || utilityType === 'all'
                  ? formattedData.map((row) => (
                      <div key={row.timestamp} className="mobile-data-card">
                        <p className="font-bold text-gray-950 dark:text-gray-100">{row.label}</p>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Energiya</span>
                          <span className="mobile-data-value font-mono">{row.energy.toFixed(2)} kWh</span>
                        </div>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Quvvat</span>
                          <span className="mobile-data-value font-mono">{row.power.toFixed(1)} W</span>
                        </div>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Samples</span>
                          <span className="mobile-data-value font-mono">{row.samples}</span>
                        </div>
                      </div>
                    ))
                  : utilityType === 'water'
                  ? hourlyChartData.map((row) => (
                      <div key={row.bucket_ts} className="mobile-data-card">
                        <p className="font-bold text-gray-950 dark:text-gray-100">{row.label}</p>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Pastki bosim</span>
                          <span className="mobile-data-value font-mono">{row.pressure.toFixed(3)} bar</span>
                        </div>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Yuqori bosim</span>
                          <span className="mobile-data-value font-mono">{row.pressureTop.toFixed(3)} bar</span>
                        </div>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Oqim</span>
                          <span className="mobile-data-value font-mono">{row.flow.toFixed(3)} L/min</span>
                        </div>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Hajm</span>
                          <span className="mobile-data-value font-mono">{row.volume.toFixed(3)} m³</span>
                        </div>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Samples</span>
                          <span className="mobile-data-value font-mono">{row.samples}</span>
                        </div>
                      </div>
                    ))
                  : hourlyChartData.map((row) => (
                      <div key={row.bucket_ts} className="mobile-data-card">
                        <p className="font-bold text-gray-950 dark:text-gray-100">{row.label}</p>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Bosim</span>
                          <span className="mobile-data-value font-mono">{row.pressure.toFixed(3)} bar</span>
                        </div>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Oqim</span>
                          <span className="mobile-data-value font-mono">{row.flow.toFixed(3)} m³/h</span>
                        </div>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Hajm</span>
                          <span className="mobile-data-value font-mono">{row.volume.toFixed(3)} m³</span>
                        </div>
                        <div className="mobile-data-row">
                          <span className="mobile-data-label">Samples</span>
                          <span className="mobile-data-value font-mono">{row.samples}</span>
                        </div>
                      </div>
                    ))}
              </div>
            </div>
          </div>
        ) : (
          <EmptyBlock title={translations.common.noData} message="Ushbu sana oralig‘ida o‘lchovlar topilmadi" />
        )}
      </div>
    </RootLayout>
  )
}
