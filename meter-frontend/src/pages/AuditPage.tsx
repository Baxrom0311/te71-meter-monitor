import { useState, useMemo } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { RootLayout } from '@/components/layout/RootLayout'
import { useAuditLogs } from '@/hooks/queries'
import { translations } from '@/i18n/translations'
import { Search, Filter, ShieldCheck, UserCheck, Key, Database } from 'lucide-react'
import clsx from 'clsx'

export default function AuditPage() {
  const { data: auditLogs, isLoading } = useAuditLogs()

  // Filter States
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedEntity, setSelectedEntity] = useState<string>('all')

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

  return (
    <RootLayout>
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-100">{translations.audit.title}</h1>

        {/* Filters Toolbar */}
        <div className="flex flex-col md:flex-row gap-4 justify-between items-center glass-card rounded-xl p-5 shadow">
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
          <div className="flex flex-wrap gap-2 w-full md:w-auto">
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
          </div>
        </div>

        {/* Audit Table */}
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : filteredLogs && filteredLogs.length > 0 ? (
          <div className="glass-card rounded-xl overflow-hidden shadow-lg">
            <div className="overflow-x-auto">
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
                  {filteredLogs.map((log) => (
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
          </div>
        ) : (
          <div className="glass-card rounded-xl p-12 text-center shadow">
            <p className="text-gray-600 dark:text-gray-400 font-medium">{translations.common.noData}</p>
            <p className="text-gray-500 dark:text-gray-550 text-sm mt-1">Ushbu filtrga mos keluvchi audit yozuvlari topilmadi</p>
          </div>
        )}
      </div>
    </RootLayout>
  )
}
