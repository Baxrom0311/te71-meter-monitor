import { useState, useMemo } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { AlertCircle, Trash2, Check, ShieldAlert, Plus, X, ToggleLeft, ToggleRight } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useAlerts, useAlertRules, useBuildings } from '@/hooks/queries'
import { useAuth } from '@/contexts/AuthContext'
import { translations } from '@/i18n/translations'
import { useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import clsx from 'clsx'

export default function AlertsPage() {
  const { data: alerts, isLoading: alertsLoading } = useAlerts()
  const { data: alertRules, isLoading: rulesLoading } = useAlertRules()
  const { data: buildings } = useBuildings()
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()

  // Tab State: 'history' or 'rules'
  const [activeTab, setActiveTab] = useState<'history' | 'rules'>('history')

  const [clearing, setClearing] = useState(false)

  // Rule Modal & Form State
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [kind, setKind] = useState('voltage_high')
  const [utilityType, setUtilityType] = useState('electricity')
  const [buildingId, setBuildingId] = useState('')
  const [minValue, setMinValue] = useState('')
  const [maxValue, setMaxValue] = useState('')
  const [severity, setSeverity] = useState('warning')
  const [message, setMessage] = useState('')
  const [dedupeSec, setDedupeSec] = useState('300')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleClearAlert = async (id: number) => {
    try {
      await apiClient.post(`/api/alerts/${id}/clear`)
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
    } catch (err) {
      console.error('Error clearing alert:', err)
    }
  }

  const handleClearAll = async () => {
    if (!confirm('Haqiqatdan ham barcha ogohlantirishlarni o\'chirmoqchisiz?')) return
    setClearing(true)
    try {
      await apiClient.post('/api/alerts/clear-all')
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
    } catch (err) {
      console.error('Error clearing all alerts:', err)
    } finally {
      setClearing(false)
    }
  }

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      await apiClient.post('/api/alert-rules', {
        kind,
        utility_type: utilityType || null,
        building_id: buildingId ? parseInt(buildingId) : null,
        min_value: minValue ? parseFloat(minValue) : null,
        max_value: maxValue ? parseFloat(maxValue) : null,
        severity,
        dedupe_sec: dedupeSec ? parseInt(dedupeSec) : null,
        message: message || null,
        enabled: true,
      })
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] })
      setIsModalOpen(false)
      // Reset form
      setKind('voltage_high')
      setUtilityType('electricity')
      setBuildingId('')
      setMinValue('')
      setMaxValue('')
      setSeverity('warning')
      setMessage('')
      setDedupeSec('300')
    } catch (err: any) {
      console.error(err)
      setError(err.response?.data?.detail || 'Qoidani yaratishda xatolik yuz berdi')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDeleteRule = async (id: number) => {
    if (!confirm('Haqiqatdan ham ushbu qoidani o\'chirmoqchisiz?')) return
    try {
      await apiClient.delete(`/api/alert-rules/${id}`)
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] })
    } catch (err) {
      console.error('Error deleting rule:', err)
    }
  }

  const handleToggleRule = async (rule: any) => {
    try {
      await apiClient.put(`/api/alert-rules/${rule.id}`, {
        ...rule,
        enabled: !rule.enabled,
      })
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] })
    } catch (err) {
      console.error('Error toggling rule status:', err)
    }
  }

  const activeAlertsCount = alerts?.filter(a => !a.cleared).length ?? 0

  return (
    <RootLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-8 h-8 text-blue-500" />
            <h1 className="text-3xl font-bold text-gray-905 dark:text-gray-100">{translations.alerts.title}</h1>
          </div>
          <div className="flex items-center gap-3">
            {activeTab === 'history' && isAdmin && activeAlertsCount > 0 && (
              <button
                onClick={handleClearAll}
                disabled={clearing}
                className="flex items-center gap-2 px-4 py-2 bg-red-650 hover:bg-red-750 disabled:opacity-50 text-white rounded-lg transition text-sm font-semibold shadow"
              >
                <Trash2 className="w-4 h-4" />
                Barchasini tozalash
              </button>
            )}
            {activeTab === 'rules' && isAdmin && (
              <button
                onClick={() => setIsModalOpen(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-650 text-white rounded-lg transition text-sm font-semibold shadow"
              >
                <Plus className="w-4 h-4" />
                Yangi qoida qo'shish
              </button>
            )}
          </div>
        </div>

        {/* Tab Buttons */}
        <div className="flex border-b border-gray-300 dark:border-gray-800">
          <button
            onClick={() => setActiveTab('history')}
            className={clsx(
              'px-6 py-3 font-semibold text-sm border-b-2 transition duration-200',
              activeTab === 'history'
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200'
            )}
          >
            Ogohlantirishlar jurnali ({alerts?.length ?? 0})
          </button>
          <button
            onClick={() => setActiveTab('rules')}
            className={clsx(
              'px-6 py-3 font-semibold text-sm border-b-2 transition duration-200',
              activeTab === 'rules'
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200'
            )}
          >
            Chegara qoidalari ({alertRules?.length ?? 0})
          </button>
        </div>

        {/* Content Tabs */}
        {activeTab === 'history' ? (
          /* Alerts History Log */
          alertsLoading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          ) : alerts && alerts.length > 0 ? (
            <div className="glass-card rounded-xl overflow-hidden shadow-lg">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-300 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30">
                      <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                        {translations.alerts.severity}
                      </th>
                      <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                        {translations.alerts.kind}
                      </th>
                      <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                        {translations.alerts.message}
                      </th>
                      <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                        {translations.alerts.timestamp}
                      </th>
                      <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                        {translations.alerts.status}
                      </th>
                      {isAdmin && (
                        <th className="text-right px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                          Amallar
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {alerts.map((alert) => (
                      <tr
                        key={alert.id}
                        className="border-b border-gray-300 dark:border-gray-700 hover:bg-gray-100/30 dark:hover:bg-gray-850/30 transition"
                      >
                        <td className="px-6 py-4">
                          <span
                            className={`px-3 py-1 rounded-full text-xs font-semibold ${
                              alert.severity === 'critical'
                                ? 'bg-red-500/10 text-red-600 dark:text-red-400'
                                : alert.severity === 'warning'
                                  ? 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-450'
                                  : 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                            }`}
                          >
                            {alert.severity === 'critical'
                              ? translations.alerts.critical
                              : alert.severity === 'warning'
                                ? translations.alerts.warning
                                : translations.alerts.info}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-900 dark:text-gray-100 font-semibold">{alert.kind}</td>
                        <td className="px-6 py-4 text-gray-750 dark:text-gray-350 max-w-xs truncate">{alert.message ?? '—'}</td>
                        <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                          {formatDistanceToNow(new Date(alert.ts * 1000), {
                            addSuffix: true,
                          })}
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={`px-3 py-1 rounded-full text-xs font-semibold ${
                              alert.cleared
                                ? 'bg-gray-200 dark:bg-gray-500/10 text-gray-700 dark:text-gray-400'
                                : 'bg-orange-500/10 text-orange-600 dark:text-orange-450'
                            }`}
                          >
                            {alert.cleared ? translations.alerts.cleared : translations.alerts.open}
                          </span>
                        </td>
                        {isAdmin && (
                          <td className="px-6 py-4 text-right">
                            {!alert.cleared && (
                              <button
                                onClick={() => handleClearAlert(alert.id)}
                                className="inline-flex items-center gap-1 px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded transition text-xs font-semibold shadow"
                              >
                                <Check className="w-3.5 h-3.5" />
                                Tozalash
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="glass-card rounded-xl p-12 text-center shadow">
              <p className="text-gray-600 dark:text-gray-400 font-medium">{translations.common.noData}</p>
            </div>
          )
        ) : (
          /* Alert Rules Tab */
          rulesLoading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          ) : alertRules && alertRules.length > 0 ? (
            <div className="glass-card rounded-xl overflow-hidden shadow-lg">
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="border-b border-gray-300 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30">
                      <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Qoida turi</th>
                      <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Datchik</th>
                      <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Bino</th>
                      <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Chegaralar</th>
                      <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Daraja</th>
                      <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Holat</th>
                      {isAdmin && <th className="px-6 py-4 text-right text-gray-600 dark:text-gray-400 font-semibold">Amallar</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-300 dark:divide-gray-800 text-gray-700 dark:text-gray-300">
                    {alertRules.map((rule) => {
                      const building = buildings?.find(b => b.id === rule.building_id)
                      return (
                        <tr key={rule.id} className="hover:bg-gray-100/30 dark:hover:bg-gray-850/50 transition">
                          <td className="px-6 py-3.5 font-bold text-gray-950 dark:text-gray-100">{rule.kind}</td>
                          <td className="px-6 py-3.5">
                            {rule.utility_type
                              ? (translations.deviceTypes[rule.utility_type as keyof typeof translations.deviceTypes] || rule.utility_type)
                              : 'Barchasi'}
                          </td>
                          <td className="px-6 py-3.5">{building ? building.name : 'Barcha binolar'}</td>
                          <td className="px-6 py-3.5 font-mono text-gray-600 dark:text-gray-400">
                            {rule.min_value !== null ? `>= ${rule.min_value}` : ''}
                            {rule.min_value !== null && rule.max_value !== null ? ' va ' : ''}
                            {rule.max_value !== null ? `<= ${rule.max_value}` : ''}
                            {rule.min_value === null && rule.max_value === null ? '—' : ''}
                          </td>
                          <td className="px-6 py-3.5">
                            <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${
                              rule.severity === 'critical'
                                ? 'bg-red-500/10 text-red-600 dark:text-red-400'
                                : rule.severity === 'warning'
                                  ? 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-450'
                                  : 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                            }`}>
                              {rule.severity}
                            </span>
                          </td>
                          <td className="px-6 py-3.5">
                            <button
                              onClick={() => isAdmin && handleToggleRule(rule)}
                              disabled={!isAdmin}
                              className="focus:outline-none"
                            >
                              {rule.enabled ? (
                                <ToggleRight className="w-6 h-6 text-green-500" />
                              ) : (
                                <ToggleLeft className="w-6 h-6 text-gray-400 dark:text-gray-500" />
                              )}
                            </button>
                          </td>
                          {isAdmin && (
                            <td className="px-6 py-3.5 text-right">
                              <button
                                onClick={() => handleDeleteRule(rule.id)}
                                className="p-1.5 bg-red-500/10 hover:bg-red-600 text-red-600 dark:text-red-400 hover:text-white rounded transition shadow-sm border border-red-500/20"
                              >
                                <Trash2 className="w-4.5 h-4.5" />
                              </button>
                            </td>
                          )}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="glass-card rounded-xl p-12 text-center shadow">
              <p className="text-gray-600 dark:text-gray-400 font-medium">{translations.common.noData}</p>
              <p className="text-gray-500 dark:text-gray-500 text-sm mt-1">Sizda hali chegara qoidalari sozlanmagan.</p>
            </div>
          )
        )}

        {/* Add Alert Rule Modal */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="glass-card rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl relative animate-modal-pop">
              <button
                onClick={() => setIsModalOpen(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-900 dark:hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>

              <h3 className="text-xl font-bold text-gray-905 dark:text-gray-100 flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-blue-500" />
                Yangi Ogohlantirish Qoidasi
              </h3>

              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                  {error}
                </div>
              )}

              <form onSubmit={handleCreateRule} className="space-y-4 text-sm">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Qoida turi *</label>
                    <select
                      value={kind}
                      onChange={(e) => setKind(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                      <option value="voltage_high">Yuqori kuchlanish</option>
                      <option value="voltage_low">Past kuchlanish</option>
                      <option value="current_high">Yuqori tok kuchi</option>
                      <option value="power_high">Yuqori quvvat</option>
                      <option value="offline">Aloqa uzilishi</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Datchik Turi</label>
                    <select
                      value={utilityType}
                      onChange={(e) => setUtilityType(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                      <option value="electricity">Elektr</option>
                      <option value="water">Suv</option>
                      <option value="gas">Gaz</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Bino filtri</label>
                    <select
                      value={buildingId}
                      onChange={(e) => setBuildingId(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                      <option value="">Barcha binolar</option>
                      {buildings?.map((b) => (
                        <option key={b.id} value={b.id}>{b.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Daraja (Severity)</label>
                    <select
                      value={severity}
                      onChange={(e) => setSeverity(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                      <option value="info">Info</option>
                      <option value="warning">Warning</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Minimal qiymat</label>
                    <input
                      type="number"
                      step="any"
                      value={minValue}
                      onChange={(e) => setMinValue(e.target.value)}
                      placeholder="Masalan: 190"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Maksimal qiymat</label>
                    <input
                      type="number"
                      step="any"
                      value={maxValue}
                      onChange={(e) => setMaxValue(e.target.value)}
                      placeholder="Masalan: 240"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Deduplication (sec)</label>
                    <input
                      type="number"
                      min={0}
                      value={dedupeSec}
                      onChange={(e) => setDedupeSec(e.target.value)}
                      placeholder="Masalan: 300"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Xabar matni *</label>
                  <input
                    type="text"
                    required
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Masalan: Kuchlanish me'yordan oshib ketdi!"
                    className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg transition"
                  >
                    {translations.common.cancel}
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white rounded-lg transition font-medium font-semibold"
                  >
                    {submitting ? 'Saqlanmoqda...' : 'Qoidani saqlash'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </RootLayout>
  )
}
