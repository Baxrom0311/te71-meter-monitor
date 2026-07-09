import { useEffect, useState, useMemo } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { AlertCircle, Trash2, Check, ShieldAlert, Plus, X, ToggleLeft, ToggleRight, Search, Download } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useAlerts, useAlertRules, useBuildings } from '@/hooks/queries'
import { useAuth } from '@/contexts/AuthContext'
import { translations } from '@/i18n/translations'
import { useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import clsx from 'clsx'
import { EmptyBlock, ErrorBlock } from '@/components/StateBlock'
import { getApiErrorMessage } from '@/lib/errors'
import { notifyError, notifySuccess } from '@/lib/toast'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { TableSkeleton } from '@/components/Skeleton'
import { AlertRule } from '@/types/api'
import { TableColumnsMenu } from '@/components/TableColumnsMenu'
import { downloadCsv, TableColumn, useColumnVisibility } from '@/lib/table'

type AlertConfirmAction =
  | { type: 'clear-all' }
  | { type: 'delete-rule'; id: number }

const alertRuleOptions = {
  electricity: [
    { value: 'overvoltage', label: 'Yuqori kuchlanish' },
    { value: 'undervoltage', label: 'Past kuchlanish' },
    { value: 'frequency', label: 'Chastota normadan tashqari' },
  ],
  water: [
    { value: 'water_low_pressure', label: 'Suv bosimi past' },
    { value: 'water_not_reaching_top', label: 'Yuqori qavatga suv chiqmayapti' },
  ],
  gas: [
    { value: 'gas_pressure', label: 'Gaz bosimi normadan tashqari' },
    { value: 'gas_leak', label: 'Gaz sizishi' },
  ],
} as const

const alertHistoryColumns: TableColumn[] = [
  { key: 'severity', label: 'Daraja' },
  { key: 'kind', label: 'Tur' },
  { key: 'message', label: 'Xabar' },
  { key: 'timestamp', label: 'Vaqt' },
  { key: 'status', label: 'Holat' },
  { key: 'actions', label: 'Amallar' },
]

const alertRuleColumns: TableColumn[] = [
  { key: 'kind', label: 'Qoida turi' },
  { key: 'utility', label: 'Datchik' },
  { key: 'building', label: 'Bino' },
  { key: 'thresholds', label: 'Chegaralar' },
  { key: 'severity', label: 'Daraja' },
  { key: 'status', label: 'Holat' },
  { key: 'actions', label: 'Amallar' },
]

const ALERT_PAGE_SIZE = 12

export default function AlertsPage() {
  const { data: alerts, isLoading: alertsLoading, isError: alertsError, error: alertsQueryError, refetch: refetchAlerts } = useAlerts()
  const { data: alertRules, isLoading: rulesLoading, isError: rulesError, error: rulesQueryError, refetch: refetchRules } = useAlertRules()
  const { data: buildings } = useBuildings()
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()

  // Tab State: 'history' or 'rules'
  const [activeTab, setActiveTab] = useState<'history' | 'rules'>('history')
  const [searchQuery, setSearchQuery] = useState('')
  const [severityFilter, setSeverityFilter] = useState<'all' | 'info' | 'warning' | 'critical'>('all')
  const [alertStatusFilter, setAlertStatusFilter] = useState<'all' | 'open' | 'cleared'>('all')
  const [ruleUtilityFilter, setRuleUtilityFilter] = useState<'all' | 'electricity' | 'water' | 'gas'>('all')
  const [ruleStatusFilter, setRuleStatusFilter] = useState<'all' | 'enabled' | 'disabled'>('all')
  const [sortBy, setSortBy] = useState<'time' | 'severity' | 'kind'>('time')
  const [page, setPage] = useState(1)
  const { isColumnVisible: isAlertColumnVisible, toggleColumn: toggleAlertColumn } = useColumnVisibility(alertHistoryColumns, 'alerts-history-columns')
  const { isColumnVisible: isRuleColumnVisible, toggleColumn: toggleRuleColumn } = useColumnVisibility(alertRuleColumns, 'alerts-rules-columns')

  const [clearing, setClearing] = useState(false)
  const [confirmAction, setConfirmAction] = useState<AlertConfirmAction | null>(null)

  // Rule Modal & Form State
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [kind, setKind] = useState('overvoltage')
  const [utilityType, setUtilityType] = useState('electricity')
  const [buildingId, setBuildingId] = useState('')
  const [minValue, setMinValue] = useState('')
  const [maxValue, setMaxValue] = useState('')
  const [severity, setSeverity] = useState('warning')
  const [message, setMessage] = useState('')
  const [dedupeSec, setDedupeSec] = useState('300')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const currentRuleOptions = alertRuleOptions[utilityType as keyof typeof alertRuleOptions] ?? alertRuleOptions.electricity

  useEffect(() => {
    if (!currentRuleOptions.some((option) => option.value === kind)) {
      setKind(currentRuleOptions[0].value)
    }
  }, [currentRuleOptions, kind])

  const handleClearAlert = async (id: number) => {
    try {
      await apiClient.post(`/api/alerts/${id}/clear`)
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      notifySuccess('Ogohlantirish tozalandi')
    } catch (err) {
      console.error('Error clearing alert:', err)
      notifyError('Ogohlantirish tozalanmadi', getApiErrorMessage(err))
    }
  }

  const handleClearAll = async () => {
    setClearing(true)
    try {
      await apiClient.post('/api/alerts/clear-all')
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      notifySuccess('Ogohlantirishlar tozalandi')
    } catch (err) {
      console.error('Error clearing all alerts:', err)
      notifyError('Ogohlantirishlar tozalanmadi', getApiErrorMessage(err))
    } finally {
      setClearing(false)
      setConfirmAction(null)
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
      setKind('overvoltage')
      setUtilityType('electricity')
      setBuildingId('')
      setMinValue('')
      setMaxValue('')
      setSeverity('warning')
      setMessage('')
      setDedupeSec('300')
      notifySuccess('Qoida yaratildi')
    } catch (err: any) {
      console.error(err)
      setError(getApiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleDeleteRule = async (id: number) => {
    try {
      await apiClient.delete(`/api/alert-rules/${id}`)
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] })
      notifySuccess('Qoida o‘chirildi')
    } catch (err) {
      console.error('Error deleting rule:', err)
      notifyError('Qoida o‘chirilmadi', getApiErrorMessage(err))
    } finally {
      setConfirmAction(null)
    }
  }

  const handleToggleRule = async (rule: AlertRule) => {
    try {
      await apiClient.put(`/api/alert-rules/${rule.id}`, {
        ...rule,
        enabled: !rule.enabled,
      })
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] })
      notifySuccess(rule.enabled ? 'Qoida o‘chirildi' : 'Qoida yoqildi')
    } catch (err) {
      console.error('Error toggling rule status:', err)
      notifyError('Qoida yangilanmadi', getApiErrorMessage(err))
    }
  }

  const activeAlertsCount = alerts?.filter(a => !a.cleared).length ?? 0
  const filteredAlerts = useMemo(() => {
    const q = searchQuery.toLowerCase().trim()
    return (alerts ?? [])
      .filter((alert) => {
        const matchesSearch =
          !q ||
          alert.kind.toLowerCase().includes(q) ||
          (alert.message ?? '').toLowerCase().includes(q) ||
          alert.device_id.toLowerCase().includes(q) ||
          alert.utility_type.toLowerCase().includes(q)
        const matchesSeverity = severityFilter === 'all' || alert.severity === severityFilter
        const matchesStatus =
          alertStatusFilter === 'all' ||
          (alertStatusFilter === 'open' && !alert.cleared) ||
          (alertStatusFilter === 'cleared' && alert.cleared)
        return matchesSearch && matchesSeverity && matchesStatus
      })
      .sort((a, b) => {
        if (sortBy === 'severity') return a.severity.localeCompare(b.severity) || b.ts - a.ts
        if (sortBy === 'kind') return a.kind.localeCompare(b.kind) || b.ts - a.ts
        return b.ts - a.ts
      })
  }, [alertStatusFilter, alerts, searchQuery, severityFilter, sortBy])

  const filteredRules = useMemo(() => {
    const q = searchQuery.toLowerCase().trim()
    return (alertRules ?? [])
      .filter((rule) => {
        const building = buildings?.find((item) => item.id === rule.building_id)
        const matchesSearch =
          !q ||
          rule.kind.toLowerCase().includes(q) ||
          (rule.message ?? '').toLowerCase().includes(q) ||
          (building?.name ?? '').toLowerCase().includes(q)
        const matchesUtility = ruleUtilityFilter === 'all' || rule.utility_type === ruleUtilityFilter
        const matchesStatus =
          ruleStatusFilter === 'all' ||
          (ruleStatusFilter === 'enabled' && rule.enabled) ||
          (ruleStatusFilter === 'disabled' && !rule.enabled)
        return matchesSearch && matchesUtility && matchesStatus
      })
      .sort((a, b) => {
        if (sortBy === 'severity') return String(a.severity).localeCompare(String(b.severity)) || a.kind.localeCompare(b.kind)
        return a.kind.localeCompare(b.kind)
      })
  }, [alertRules, buildings, ruleStatusFilter, ruleUtilityFilter, searchQuery, sortBy])

  const activeRows = activeTab === 'history' ? filteredAlerts : filteredRules
  const totalPages = Math.max(1, Math.ceil(activeRows.length / ALERT_PAGE_SIZE))
  const pagedAlerts = useMemo(
    () => filteredAlerts.slice((page - 1) * ALERT_PAGE_SIZE, page * ALERT_PAGE_SIZE),
    [filteredAlerts, page],
  )
  const pagedRules = useMemo(
    () => filteredRules.slice((page - 1) * ALERT_PAGE_SIZE, page * ALERT_PAGE_SIZE),
    [filteredRules, page],
  )

  useEffect(() => {
    setPage(1)
  }, [activeTab, alertStatusFilter, ruleStatusFilter, ruleUtilityFilter, searchQuery, severityFilter, sortBy])

  const handleExportCSV = () => {
    if (activeTab === 'history') {
      if (filteredAlerts.length === 0) return
      downloadCsv(
        `alerts_${new Date().toISOString().slice(0, 10)}.csv`,
        ['ID', 'Device ID', 'Utility', 'Severity', 'Kind', 'Message', 'Status', 'Timestamp'],
        filteredAlerts.map((alert) => [
          alert.id,
          alert.device_id,
          alert.utility_type,
          alert.severity,
          alert.kind,
          alert.message ?? '',
          alert.cleared ? 'cleared' : 'open',
          new Date(alert.ts * 1000).toISOString(),
        ]),
      )
      notifySuccess('Ogohlantirishlar CSV eksport qilindi', `${filteredAlerts.length} ta yozuv eksport qilindi.`)
      return
    }

    if (filteredRules.length === 0) return
    downloadCsv(
      `alert_rules_${new Date().toISOString().slice(0, 10)}.csv`,
      ['ID', 'Kind', 'Utility', 'Building ID', 'Min', 'Max', 'Severity', 'Status', 'Message'],
      filteredRules.map((rule) => [
        rule.id,
        rule.kind,
        rule.utility_type ?? 'all',
        rule.building_id ?? '',
        rule.min_value ?? '',
        rule.max_value ?? '',
        rule.severity,
        rule.enabled ? 'enabled' : 'disabled',
        rule.message ?? '',
      ]),
    )
    notifySuccess('Qoidalar CSV eksport qilindi', `${filteredRules.length} ta yozuv eksport qilindi.`)
  }

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
                onClick={() => setConfirmAction({ type: 'clear-all' })}
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

        <div className="flex flex-col xl:flex-row gap-4 justify-between items-stretch xl:items-center glass-card rounded-xl p-4 sm:p-5 shadow">
          <div className="relative w-full md:max-w-md">
            <Search className="absolute left-3 top-2.5 h-4.5 w-4.5 text-gray-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder={activeTab === 'history' ? 'Alert, qurilma yoki xabar bo‘yicha qidirish...' : 'Qoida, bino yoki xabar bo‘yicha qidirish...'}
              className="w-full pl-10 pr-4 py-2 rounded-lg glass-input focus:outline-none text-sm"
            />
          </div>
          <div className="flex flex-wrap gap-2 w-full xl:w-auto">
            {activeTab === 'history' ? (
              <>
                <select
                  value={severityFilter}
                  onChange={(event) => setSeverityFilter(event.target.value as 'all' | 'info' | 'warning' | 'critical')}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold focus:outline-none glass-input shadow-sm"
                >
                  <option value="all">Barcha darajalar</option>
                  <option value="critical">Critical</option>
                  <option value="warning">Warning</option>
                  <option value="info">Info</option>
                </select>
                <select
                  value={alertStatusFilter}
                  onChange={(event) => setAlertStatusFilter(event.target.value as 'all' | 'open' | 'cleared')}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold focus:outline-none glass-input shadow-sm"
                >
                  <option value="all">Barcha holatlar</option>
                  <option value="open">Ochiq</option>
                  <option value="cleared">Tozalangan</option>
                </select>
              </>
            ) : (
              <>
                <select
                  value={ruleUtilityFilter}
                  onChange={(event) => setRuleUtilityFilter(event.target.value as 'all' | 'electricity' | 'water' | 'gas')}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold focus:outline-none glass-input shadow-sm"
                >
                  <option value="all">Barcha datchiklar</option>
                  <option value="electricity">Elektr</option>
                  <option value="water">Suv</option>
                  <option value="gas">Gaz</option>
                </select>
                <select
                  value={ruleStatusFilter}
                  onChange={(event) => setRuleStatusFilter(event.target.value as 'all' | 'enabled' | 'disabled')}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold focus:outline-none glass-input shadow-sm"
                >
                  <option value="all">Barcha qoidalar</option>
                  <option value="enabled">Yoqilgan</option>
                  <option value="disabled">O‘chirilgan</option>
                </select>
              </>
            )}
            <select
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value as 'time' | 'severity' | 'kind')}
              className="px-3.5 py-1.5 rounded-lg text-xs font-semibold focus:outline-none glass-input shadow-sm"
            >
              <option value="time">Saralash: vaqt</option>
              <option value="severity">Saralash: daraja</option>
              <option value="kind">Saralash: tur</option>
            </select>
            <button
              onClick={handleExportCSV}
              disabled={activeRows.length === 0}
              className="surface-button gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
            {activeTab === 'history' ? (
              <TableColumnsMenu
                columns={alertHistoryColumns}
                isColumnVisible={isAlertColumnVisible}
                toggleColumn={toggleAlertColumn}
              />
            ) : (
              <TableColumnsMenu
                columns={alertRuleColumns}
                isColumnVisible={isRuleColumnVisible}
                toggleColumn={toggleRuleColumn}
              />
            )}
          </div>
        </div>

        {/* Content Tabs */}
        {activeTab === 'history' ? (
          /* Alerts History Log */
          alertsLoading ? (
            <TableSkeleton rows={6} />
          ) : alertsError ? (
            <ErrorBlock message={getApiErrorMessage(alertsQueryError)} onRetry={() => refetchAlerts()} />
          ) : filteredAlerts.length > 0 ? (
            <div className="glass-card rounded-xl overflow-hidden shadow-lg">
              <div className="px-4 py-3 border-b border-gray-300 dark:border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <p className="text-xs font-semibold text-gray-600 dark:text-gray-400">
                  {filteredAlerts.length} ta alert · {page}/{totalPages} sahifa
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                    disabled={page === 1}
                    className="surface-button px-3 py-1.5 text-xs font-bold"
                  >
                    Oldingi
                  </button>
                  <button
                    onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                    disabled={page === totalPages}
                    className="surface-button px-3 py-1.5 text-xs font-bold"
                  >
                    Keyingi
                  </button>
                </div>
              </div>
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-300 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30">
                      {isAlertColumnVisible('severity') && (
                        <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                          {translations.alerts.severity}
                        </th>
                      )}
                      {isAlertColumnVisible('kind') && (
                        <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                          {translations.alerts.kind}
                        </th>
                      )}
                      {isAlertColumnVisible('message') && (
                        <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                          {translations.alerts.message}
                        </th>
                      )}
                      {isAlertColumnVisible('timestamp') && (
                        <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                          {translations.alerts.timestamp}
                        </th>
                      )}
                      {isAlertColumnVisible('status') && (
                        <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                          {translations.alerts.status}
                        </th>
                      )}
                      {isAdmin && isAlertColumnVisible('actions') && (
                        <th className="text-right px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                          Amallar
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {pagedAlerts.map((alert) => (
                      <tr
                        key={alert.id}
                        className="border-b border-gray-300 dark:border-gray-700 hover:bg-gray-100/30 dark:hover:bg-gray-850/30 transition"
                      >
                        {isAlertColumnVisible('severity') && (
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
                        )}
                        {isAlertColumnVisible('kind') && <td className="px-6 py-4 text-gray-900 dark:text-gray-100 font-semibold">{alert.kind}</td>}
                        {isAlertColumnVisible('message') && <td className="px-6 py-4 text-gray-750 dark:text-gray-350 max-w-xs truncate">{alert.message ?? '—'}</td>}
                        {isAlertColumnVisible('timestamp') && (
                          <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                            {formatDistanceToNow(new Date(alert.ts * 1000), {
                              addSuffix: true,
                            })}
                          </td>
                        )}
                        {isAlertColumnVisible('status') && (
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
                        )}
                        {isAdmin && isAlertColumnVisible('actions') && (
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
              <div className="md:hidden mobile-card-list p-3">
                {pagedAlerts.map((alert) => (
                  <div key={alert.id} className="mobile-data-card">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-bold text-gray-950 dark:text-gray-100 truncate">{alert.kind}</p>
                        <p className="text-xs text-gray-500 mt-1">{alert.message ?? '—'}</p>
                      </div>
                      <span
                        className={`shrink-0 px-2 py-1 rounded-full text-[11px] font-bold ${
                          alert.severity === 'critical'
                            ? 'bg-red-500/10 text-red-600 dark:text-red-400'
                            : alert.severity === 'warning'
                              ? 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-450'
                              : 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                        }`}
                      >
                        {alert.severity}
                      </span>
                    </div>
                    <div className="mobile-data-row">
                      <span className="mobile-data-label">{translations.alerts.timestamp}</span>
                      <span className="mobile-data-value">{formatDistanceToNow(new Date(alert.ts * 1000), { addSuffix: true })}</span>
                    </div>
                    <div className="mobile-data-row">
                      <span className="mobile-data-label">{translations.alerts.status}</span>
                      <span className="mobile-data-value">{alert.cleared ? translations.alerts.cleared : translations.alerts.open}</span>
                    </div>
                    {isAdmin && !alert.cleared && (
                      <button
                        onClick={() => handleClearAlert(alert.id)}
                        className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-green-600 px-3 py-2 text-xs font-bold text-white hover:bg-green-700 transition"
                      >
                        <Check className="w-3.5 h-3.5" />
                        Tozalash
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyBlock title={translations.common.noData} message="Hozircha ogohlantirishlar mavjud emas." />
          )
        ) : (
          /* Alert Rules Tab */
          rulesLoading ? (
            <TableSkeleton rows={6} />
          ) : rulesError ? (
            <ErrorBlock message={getApiErrorMessage(rulesQueryError)} onRetry={() => refetchRules()} />
          ) : filteredRules.length > 0 ? (
            <div className="glass-card rounded-xl overflow-hidden shadow-lg">
              <div className="px-4 py-3 border-b border-gray-300 dark:border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <p className="text-xs font-semibold text-gray-600 dark:text-gray-400">
                  {filteredRules.length} ta qoida · {page}/{totalPages} sahifa
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                    disabled={page === 1}
                    className="surface-button px-3 py-1.5 text-xs font-bold"
                  >
                    Oldingi
                  </button>
                  <button
                    onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                    disabled={page === totalPages}
                    className="surface-button px-3 py-1.5 text-xs font-bold"
                  >
                    Keyingi
                  </button>
                </div>
              </div>
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="border-b border-gray-300 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30">
                      {isRuleColumnVisible('kind') && <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Qoida turi</th>}
                      {isRuleColumnVisible('utility') && <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Datchik</th>}
                      {isRuleColumnVisible('building') && <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Bino</th>}
                      {isRuleColumnVisible('thresholds') && <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Chegaralar</th>}
                      {isRuleColumnVisible('severity') && <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Daraja</th>}
                      {isRuleColumnVisible('status') && <th className="px-6 py-4 font-semibold text-gray-600 dark:text-gray-400">Holat</th>}
                      {isAdmin && isRuleColumnVisible('actions') && <th className="px-6 py-4 text-right text-gray-600 dark:text-gray-400 font-semibold">Amallar</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-300 dark:divide-gray-800 text-gray-700 dark:text-gray-300">
                    {pagedRules.map((rule) => {
                      const building = buildings?.find(b => b.id === rule.building_id)
                      return (
                        <tr key={rule.id} className="hover:bg-gray-100/30 dark:hover:bg-gray-850/50 transition">
                          {isRuleColumnVisible('kind') && <td className="px-6 py-3.5 font-bold text-gray-950 dark:text-gray-100">{rule.kind}</td>}
                          {isRuleColumnVisible('utility') && (
                            <td className="px-6 py-3.5">
                              {rule.utility_type
                                ? (translations.deviceTypes[rule.utility_type as keyof typeof translations.deviceTypes] || rule.utility_type)
                                : 'Barchasi'}
                            </td>
                          )}
                          {isRuleColumnVisible('building') && <td className="px-6 py-3.5">{building ? building.name : 'Barcha binolar'}</td>}
                          {isRuleColumnVisible('thresholds') && (
                            <td className="px-6 py-3.5 font-mono text-gray-600 dark:text-gray-400">
                              {rule.min_value !== null ? `>= ${rule.min_value}` : ''}
                              {rule.min_value !== null && rule.max_value !== null ? ' va ' : ''}
                              {rule.max_value !== null ? `<= ${rule.max_value}` : ''}
                              {rule.min_value === null && rule.max_value === null ? '—' : ''}
                            </td>
                          )}
                          {isRuleColumnVisible('severity') && (
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
                          )}
                          {isRuleColumnVisible('status') && (
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
                          )}
                          {isAdmin && isRuleColumnVisible('actions') && (
                            <td className="px-6 py-3.5 text-right">
                              <button
                                onClick={() => setConfirmAction({ type: 'delete-rule', id: rule.id })}
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
              <div className="md:hidden mobile-card-list p-3">
                {pagedRules.map((rule) => {
                  const building = buildings?.find(b => b.id === rule.building_id)
                  return (
                    <div key={rule.id} className="mobile-data-card">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-bold text-gray-950 dark:text-gray-100 truncate">{rule.kind}</p>
                          <p className="text-xs text-gray-500">{building ? building.name : 'Barcha binolar'}</p>
                        </div>
                        <button
                          onClick={() => isAdmin && handleToggleRule(rule)}
                          disabled={!isAdmin}
                          className="shrink-0"
                        >
                          {rule.enabled ? (
                            <ToggleRight className="w-6 h-6 text-green-500" />
                          ) : (
                            <ToggleLeft className="w-6 h-6 text-gray-400 dark:text-gray-500" />
                          )}
                        </button>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Datchik</span>
                        <span className="mobile-data-value">
                          {rule.utility_type
                            ? (translations.deviceTypes[rule.utility_type as keyof typeof translations.deviceTypes] || rule.utility_type)
                            : 'Barchasi'}
                        </span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Chegara</span>
                        <span className="mobile-data-value font-mono">
                          {rule.min_value !== null ? `>= ${rule.min_value}` : ''}
                          {rule.min_value !== null && rule.max_value !== null ? ' va ' : ''}
                          {rule.max_value !== null ? `<= ${rule.max_value}` : ''}
                          {rule.min_value === null && rule.max_value === null ? '—' : ''}
                        </span>
                      </div>
                      <div className="mobile-data-row">
                        <span className="mobile-data-label">Daraja</span>
                        <span className="mobile-data-value">{rule.severity}</span>
                      </div>
                      {isAdmin && (
                        <button
                          onClick={() => setConfirmAction({ type: 'delete-rule', id: rule.id })}
                          className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-red-600 px-3 py-2 text-xs font-bold text-white hover:bg-red-700 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          O‘chirish
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            <EmptyBlock title={translations.common.noData} message="Sizda hali chegara qoidalari sozlanmagan." />
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
                      {currentRuleOptions.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
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
        <ConfirmDialog
          open={confirmAction !== null}
          title={confirmAction?.type === 'clear-all' ? 'Barcha ogohlantirishlarni tozalash' : 'Qoidani o‘chirish'}
          message={
            confirmAction?.type === 'clear-all'
              ? 'Barcha ochiq ogohlantirishlar tozalanadi. Amalni davom ettirasizmi?'
              : 'Bu chegara qoidasi o‘chiriladi. Keyingi o‘lchovlarda bu qoida ishlamaydi.'
          }
          confirmLabel={confirmAction?.type === 'clear-all' ? 'Barchasini tozalash' : 'O‘chirish'}
          tone="danger"
          pending={clearing}
          onConfirm={() => {
            if (confirmAction?.type === 'clear-all') handleClearAll()
            if (confirmAction?.type === 'delete-rule') handleDeleteRule(confirmAction.id)
          }}
          onCancel={() => setConfirmAction(null)}
        />
      </div>
    </RootLayout>
  )
}
