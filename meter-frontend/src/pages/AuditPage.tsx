import { useEffect, useState, useMemo } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { RootLayout } from '@/components/layout/RootLayout'
import { useAuditLogs } from '@/hooks/queries'
import { translations } from '@/i18n/translations'
import { Search, ShieldCheck, UserCheck, Key, Database, Download } from 'lucide-react'
import clsx from 'clsx'
import { EmptyBlock, ErrorBlock } from '@/components/StateBlock'
import { getApiErrorMessage } from '@/lib/errors'
import { TableSkeleton } from '@/components/Skeleton'
import { notifySuccess } from '@/lib/toast'

export default function AuditPage() {
  const { data: auditLogs, isLoading, isError, error: queryError, refetch } = useAuditLogs()

  // Filter States
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedEntity, setSelectedEntity] = useState<string>('all')
  const [page, setPage] = useState(1)
  const pageSize = 15

  // Available entity options for filtering
  const entityOptions = [
    { label: 'Barchasi', value: 'all', icon: <Database className="w-3.5 h-3.5" /> },
    { label: 'Foydalanuvchilar', value: 'user', icon: <UserCheck className="w-3.5 h-3.5" /> },
    { label: 'Qurilmalar', value: 'device', icon: <ShieldCheck className="w-3.5 h-3.5" /> },
    { label: 'Binolar', value: 'building', icon: <Key className="w-3.5 h-3.5" /> },
  ]

  // Filtered Logs list based on search query and entity selection
  const filteredLogs = useMemo(() => {
    if (!auditLogs) return []
    return auditLogs.filter((log) => {
      const matchesEntity = selectedEntity === 'all' || log.entity_type === selectedEntity
      
      const userStr = (log.username ?? log.user_id ?? '').toString().toLowerCase()
      const actionStr = (log.action ?? '').toLowerCase()
      const typeStr = (log.entity_type ?? '').toLowerCase()
      const q = searchQuery.toLowerCase().trim()

      const matchesSearch =
        !q ||
        userStr.includes(q) ||
        actionStr.includes(q) ||
        typeStr.includes(q)

      return matchesEntity && matchesSearch
    })
  }, [auditLogs, searchQuery, selectedEntity])

  useEffect(() => {
    setPage(1)
  }, [searchQuery, selectedEntity])

  const totalPages = Math.max(1, Math.ceil(filteredLogs.length / pageSize))
  const pagedLogs = useMemo(
    () => filteredLogs.slice((page - 1) * pageSize, page * pageSize),
    [filteredLogs, page],
  )

  const handleExportCSV = () => {
    if (filteredLogs.length === 0) return
    const rows = [
      ['Timestamp', 'User', 'Action', 'Entity Type', 'Entity ID', 'Detail'].join(','),
      ...filteredLogs.map((log) => [
        new Date(log.ts * 1000).toISOString(),
        log.username ?? log.user_id ?? '',
        log.action,
        log.entity_type ?? '',
        log.entity_id ?? '',
        log.detail ?? '',
      ].map((value) => `"${String(value).replace(/"/g, '""')}"`).join(',')),
    ]
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `audit_${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
    notifySuccess('Audit CSV eksport qilindi', `${filteredLogs.length} ta yozuv eksport qilindi.`)
  }

  return (
    <RootLayout>
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-100">{translations.audit.title}</h1>

        {/* Filters Toolbar */}
        <div className="flex flex-col xl:flex-row gap-4 justify-between items-stretch xl:items-center glass-card rounded-xl p-4 sm:p-5 shadow">
          {/* Search bar */}
          <div className="relative w-full md:max-w-md">
            <Search className="absolute left-3 top-2.5 h-4.5 w-4.5 text-gray-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Foydalanuvchi yoki amalni qidirish..."
              className="w-full pl-10 pr-4 py-2 rounded-lg glass-input focus:outline-none text-sm"
            />
          </div>

          {/* Quick pills filters */}
          <div className="flex flex-wrap gap-2 w-full xl:w-auto">
            {entityOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setSelectedEntity(opt.value)}
                className={clsx(
                  'flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold border transition shadow-sm',
                  selectedEntity === opt.value
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-white/40 dark:bg-gray-950/40 border-gray-300 dark:border-gray-800 text-gray-500 dark:text-gray-400 hover:text-gray-950 dark:hover:text-gray-200'
                )}
              >
                {opt.icon}
                {opt.label}
              </button>
            ))}
            <button
              onClick={handleExportCSV}
              disabled={filteredLogs.length === 0}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold border transition shadow-sm bg-white/40 dark:bg-gray-950/40 border-gray-300 dark:border-gray-800 text-gray-500 dark:text-gray-400 hover:text-gray-950 dark:hover:text-gray-200 disabled:opacity-40"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
          </div>
        </div>

        {/* Audit Table */}
        {isLoading ? (
          <TableSkeleton rows={8} />
        ) : isError ? (
          <ErrorBlock message={getApiErrorMessage(queryError)} onRetry={() => refetch()} />
        ) : filteredLogs && filteredLogs.length > 0 ? (
          <div className="glass-card rounded-xl overflow-hidden shadow-lg">
            <div className="px-4 py-3 border-b border-gray-300 dark:border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <p className="text-xs font-semibold text-gray-600 dark:text-gray-400">
                {filteredLogs.length} ta yozuv · {page}/{totalPages} sahifa
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-gray-100 dark:bg-gray-850 disabled:opacity-40 hover:bg-gray-200 dark:hover:bg-gray-750 transition"
                >
                  Oldingi
                </button>
                <button
                  onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-gray-100 dark:bg-gray-850 disabled:opacity-40 hover:bg-gray-200 dark:hover:bg-gray-750 transition"
                >
                  Keyingi
                </button>
              </div>
            </div>
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-300 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30">
                    <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                      {translations.audit.timestamp}
                    </th>
                    <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                      {translations.audit.user}
                    </th>
                    <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                      {translations.audit.action}
                    </th>
                    <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                      Resurs turi
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-300 dark:divide-gray-800 text-gray-750 dark:text-gray-300">
                  {pagedLogs.map((log) => (
                    <tr
                      key={log.id}
                      className="border-b border-gray-300 dark:border-gray-700 hover:bg-gray-100/30 dark:hover:bg-gray-850/30 transition"
                    >
                      <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                        {formatDistanceToNow(new Date(log.ts * 1000), {
                          addSuffix: true,
                        })}
                      </td>
                      <td className="px-6 py-4 text-gray-950 dark:text-gray-100 font-bold">{log.username ?? log.user_id ?? '—'}</td>
                      <td className="px-6 py-4">
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                          {log.action}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-gray-600 dark:text-gray-400 capitalize">{log.entity_type ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="md:hidden mobile-card-list p-3">
              {pagedLogs.map((log) => (
                <div key={log.id} className="mobile-data-card">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-bold text-gray-950 dark:text-gray-100 truncate">{log.username ?? log.user_id ?? '—'}</p>
                      <p className="text-xs text-gray-500">{formatDistanceToNow(new Date(log.ts * 1000), { addSuffix: true })}</p>
                    </div>
                    <span className="shrink-0 px-2 py-1 rounded text-[11px] font-bold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                      {log.action}
                    </span>
                  </div>
                  <div className="mobile-data-row">
                    <span className="mobile-data-label">Resurs</span>
                    <span className="mobile-data-value capitalize">{log.entity_type ?? '—'}</span>
                  </div>
                  <div className="mobile-data-row">
                    <span className="mobile-data-label">ID</span>
                    <span className="mobile-data-value font-mono">{log.entity_id ?? '—'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyBlock title={translations.common.noData} message="Ushbu filtrga mos keluvchi audit yozuvlari topilmadi" />
        )}
      </div>
    </RootLayout>
  )
}
