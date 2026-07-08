import { useState, useMemo } from 'react'
import { TrendingUp, Download, Calendar, Filter } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useEnergyAnalytics, useBuildings } from '@/hooks/queries'
import { translations } from '@/i18n/translations'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { useTheme } from '@/contexts/ThemeContext'
import { chartTheme } from '@/lib/chartTheme'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlock'
import { getApiErrorMessage } from '@/lib/errors'
import { notifySuccess } from '@/lib/toast'

export default function AnalyticsPage() {
  const { data: buildings } = useBuildings()
  const { isDark } = useTheme()
  const chart = chartTheme(isDark)

  // Filters State
  const [buildingId, setBuildingId] = useState<string>('')
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

  // Fetch energy analytics
  const { data: analyticsData, isLoading, isError, error: analyticsError, refetch } = useEnergyAnalytics(granularity, fromTs, toTs, bId)

  // Chart and Table data formatter
  const formattedData = useMemo(() => {
    if (!analyticsData?.data) return []
    return analyticsData.data.map((p) => {
      let label = ''
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

  // CSV Data Export
  const handleExportCSV = () => {
    if (formattedData.length === 0) return
    const headers = ['Vaqt (Timestamp)', 'Sana (Label)', 'Energiya sarfi (kWh)', 'O\'rtacha Quvvat (W)', 'O\'lchovlar soni']
    const csvRows = [headers.join(',')]

    formattedData.forEach((row) => {
      const values = [
        row.timestamp,
        `"${row.label}"`,
        row.energy,
        row.power,
        row.samples,
      ]
      csvRows.push(values.join(','))
    })

    const csvContent = 'data:text/csv;charset=utf-8,' + csvRows.join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `energy_analytics_${buildingId || 'all'}_${granularity}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    notifySuccess('CSV eksport qilindi')
  }

  return (
    <RootLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <TrendingUp className="w-8 h-8 text-blue-500" />
            <h1 className="text-3xl font-bold text-gray-100">Energiya Sarfi Tahlili</h1>
          </div>
          <button
            onClick={handleExportCSV}
            disabled={formattedData.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-200 border border-gray-700 rounded-lg transition text-sm font-semibold shadow-sm"
          >
            <Download className="w-4 h-4" />
            Eksport (CSV)
          </button>
        </div>

        {/* Filter Toolbar */}
        <div className="glass-card rounded-xl p-5 grid grid-cols-1 md:grid-cols-4 gap-4 shadow">
          {/* Building Selector */}
          <div>
            <label className="block text-xs text-gray-500 font-semibold uppercase tracking-wider mb-2">Bino</label>
            <select
              value={buildingId}
              onChange={(e) => setBuildingId(e.target.value)}
              className="w-full px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-gray-100 text-sm focus:outline-none focus:border-blue-500"
            >
              <option value="">Barcha binolar</option>
              {buildings?.map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          </div>

          {/* Granularity Selector */}
          <div>
            <label className="block text-xs text-gray-500 font-semibold uppercase tracking-wider mb-2">Granulyarlik</label>
            <select
              value={granularity}
              onChange={(e) => setGranularity(e.target.value as 'hour' | 'day' | 'month')}
              className="w-full px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-gray-100 text-sm focus:outline-none focus:border-blue-500"
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
              className="w-full px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-gray-100 text-sm focus:outline-none focus:border-blue-500"
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
          <div className="glass-card rounded-xl p-5 flex flex-wrap gap-4 shadow">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-300">Boshlanish:</span>
              <input
                type="date"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
                className="px-3 py-1.5 bg-gray-950 border border-gray-700 rounded-lg text-gray-100 text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-300">Tugash:</span>
              <input
                type="date"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
                className="px-3 py-1.5 bg-gray-950 border border-gray-700 rounded-lg text-gray-100 text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
        )}

        {/* Loading Spinner */}
        {isLoading ? (
          <LoadingBlock title="Tahlil maʼlumotlari yuklanmoqda" />
        ) : isError ? (
          <ErrorBlock message={getApiErrorMessage(analyticsError)} onRetry={() => refetch()} />
        ) : formattedData.length > 0 ? (
          <div className="grid grid-cols-1 gap-6">
            {/* Energy delta chart */}
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
                  <BarChart data={formattedData} barCategoryGap="30%">
                    <CartesianGrid strokeDasharray="4 8" stroke={chart.grid} vertical={false} />
                    <XAxis dataKey="label" stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} width={48} />
                    <Tooltip
                      contentStyle={chart.tooltip}
                      labelStyle={{ color: chart.label, fontWeight: 800 }}
                      cursor={{ fill: isDark ? 'rgba(59,130,246,0.08)' : 'rgba(37,99,235,0.08)' }}
                    />
                    <Legend wrapperStyle={{ color: chart.label, fontSize: 12 }} />
                    <Bar dataKey="energy" name="Energiya (kWh)" fill="#3B82F6" radius={[8, 8, 3, 3]} />
                  </BarChart>
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

            {/* Data table */}
            <div className="glass-card data-table-card rounded-xl overflow-hidden shadow-sm">
              <div className="p-5 border-b border-gray-300 dark:border-gray-800">
                <h3 className="text-lg font-bold text-gray-950 dark:text-gray-100">Tahliliy hisobot jadvali</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
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
                </table>
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
