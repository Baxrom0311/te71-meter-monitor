import { useState } from 'react'
import { Settings, Info, Save, Bot, Key, Radio, Database, Download, RefreshCw, Trash2, ShieldAlert } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { translations } from '@/i18n/translations'
import { useSummary, useBackups, qk } from '@/hooks/queries'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlock'
import { API_BASE_URL } from '@/lib/env'
import { getApiErrorMessage } from '@/lib/errors'
import { notifySuccess, notifyError } from '@/lib/toast'
import apiClient from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'

export default function SettingsPage() {
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()
  const { data: summary, isLoading: summaryLoading, isError: summaryIsError, error: summaryError, refetch: refetchSummary } = useSummary()
  const { data: backupData, isLoading: backupsLoading, refetch: refetchBackups } = useBackups()

  // Telegram Notifications Mock State
  const [botToken, setBotToken] = useState('')
  const [chatId, setChatId] = useState('')
  const [tgEnabled, setTgEnabled] = useState(true)

  // API Config State
  const [apiBase, setApiBase] = useState(API_BASE_URL)
  const [saving, setSaving] = useState(false)
  const [creatingBackup, setCreatingBackup] = useState(false)

  // Create Backup Mutation
  const createBackupMutation = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post('/api/backups?reason=manual')
      return data
    },
    onSuccess: (data) => {
      notifySuccess('Zahira nusxa yaratildi', `Fayl: ${data.filename}`)
      queryClient.invalidateQueries({ queryKey: qk.backups() })
    },
    onError: (err) => {
      notifyError('Backup yaratib bo\'lmadi', getApiErrorMessage(err))
    },
  })

  // Delete Backup Mutation
  const deleteBackupMutation = useMutation({
    mutationFn: async (filename: string) => {
      const { data } = await apiClient.delete(`/api/backups/${filename}`)
      return data
    },
    onSuccess: () => {
      notifySuccess('Backup o\'chirildi')
      queryClient.invalidateQueries({ queryKey: qk.backups() })
    },
    onError: (err) => {
      notifyError('Backup o\'chirishda xatolik', getApiErrorMessage(err))
    },
  })

  // Restore Backup Mutation
  const restoreBackupMutation = useMutation({
    mutationFn: async (filename: string) => {
      const { data } = await apiClient.post(`/api/backups/restore/${filename}?confirm=RESTORE`)
      return data
    },
    onSuccess: () => {
      notifySuccess('Ma\'lumotlar bazasi qayta tiklandi (Restore)', 'Tizim qayta yuklandi.')
      queryClient.invalidateQueries()
    },
    onError: (err) => {
      notifyError('Restore xatoligi', getApiErrorMessage(err))
    },
  })

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setTimeout(() => {
      setSaving(false)
      notifySuccess('Sozlamalar saqlandi', 'Frontend sozlamalari lokal holatda yangilandi.')
    }, 600)
  }

  const handleDownload = (filename: string) => {
    window.open(`${API_BASE_URL}/api/backups/download/${filename}`, '_blank')
  }

  return (
    <RootLayout>
      <div className="space-y-6 w-full">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Settings className="w-8 h-8 text-blue-500" />
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">{translations.settings.title}</h1>
        </div>

        <form onSubmit={handleSave} className="grid grid-cols-1 xl:grid-cols-2 gap-6 text-sm">
          {/* System Settings & API */}
          <div className="glass-card rounded-xl p-6 space-y-4 shadow">
            <h2 className="text-lg font-bold text-gray-950 dark:text-gray-100 flex items-center gap-2 border-b border-gray-300 dark:border-gray-800 pb-2">
              <Settings className="w-5 h-5 text-blue-450" />
              {translations.settings.systemSettings}
            </h2>

            <div className="space-y-3">
              <div>
                <label className="block text-gray-700 dark:text-gray-400 font-medium mb-1.5">Server API Base URL</label>
                <input
                  type="url"
                  value={apiBase}
                  onChange={(e) => setApiBase(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-lg glass-input font-mono text-sm focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-gray-700 dark:text-gray-400 font-medium mb-1.5">Ma'lumotlarni saqlash muddati (kun)</label>
                <select
                  defaultValue="90"
                  className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                >
                  <option value="30">30 kun</option>
                  <option value="90">90 kun (3 oy)</option>
                  <option value="180">180 kun (6 oy)</option>
                  <option value="365">365 kun (1 yil)</option>
                </select>
              </div>
            </div>
          </div>

          {/* Telegram Notification settings */}
          <div className="glass-card rounded-xl p-6 space-y-4 shadow">
            <h2 className="text-lg font-bold text-gray-950 dark:text-gray-100 flex items-center gap-2 border-b border-gray-300 dark:border-gray-800 pb-2">
              <Bot className="w-5 h-5 text-blue-450" />
              Telegram xabarnomalari
            </h2>

            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 px-3 rounded-lg border border-gray-300 dark:border-gray-850 bg-gray-100/30 dark:bg-gray-950/40">
                <span className="text-gray-800 dark:text-gray-300 font-medium text-sm">Telegram ogohlantirishlarini yoqish</span>
                <input
                  type="checkbox"
                  checked={tgEnabled}
                  onChange={(e) => setTgEnabled(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-blue-500 focus:ring-0"
                />
              </div>

              <div>
                <label className="block text-gray-700 dark:text-gray-400 font-medium mb-1.5">Telegram Bot Token</label>
                <div className="relative">
                  <input
                    type="password"
                    disabled={!tgEnabled}
                    value={botToken}
                    onChange={(e) => setBotToken(e.target.value)}
                    placeholder="Bot tokenni kiriting"
                    className="w-full pl-3.5 pr-10 py-2 rounded-lg glass-input font-mono text-sm focus:outline-none disabled:opacity-40"
                  />
                  <Key className="absolute right-3.5 top-2.5 h-4.5 w-4.5 text-gray-400" />
                </div>
              </div>

              <div>
                <label className="block text-gray-700 dark:text-gray-400 font-medium mb-1.5">Telegram Chat / Group ID</label>
                <input
                  type="text"
                  disabled={!tgEnabled}
                  value={chatId}
                  onChange={(e) => setChatId(e.target.value)}
                  placeholder="Masalan: -100xxxxxxxxxx"
                  className="w-full px-3.5 py-2 rounded-lg glass-input font-mono text-sm focus:outline-none disabled:opacity-40"
                />
              </div>
            </div>
          </div>

          {/* Database Backup & Recovery Panel (Admin Only) */}
          {isAdmin && (
            <div className="glass-card rounded-xl p-6 space-y-4 shadow xl:col-span-2">
              <div className="flex items-center justify-between border-b border-gray-300 dark:border-gray-800 pb-3">
                <h2 className="text-lg font-bold text-gray-950 dark:text-gray-100 flex items-center gap-2">
                  <Database className="w-5 h-5 text-emerald-500" />
                  Ma'lumotlar bazasi zaxira nusxalari (Database Backups)
                </h2>
                <button
                  type="button"
                  onClick={() => createBackupMutation.mutate()}
                  disabled={createBackupMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition font-semibold shadow text-xs"
                >
                  <RefreshCw className={`w-4 h-4 ${createBackupMutation.isPending ? 'animate-spin' : ''}`} />
                  {createBackupMutation.isPending ? 'Yaratilmoqda...' : 'Yangi backup yaratish'}
                </button>
              </div>

              {backupsLoading ? (
                <LoadingBlock title="Backuplar yuklanmoqda..." message="Serverdan ma'lumotlar bazasi nusxalari olinmoqda." />
              ) : backupData?.backups && backupData.backups.length > 0 ? (
                <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 dark:bg-gray-900/60 text-gray-500 uppercase font-semibold border-b border-gray-200 dark:border-gray-800">
                      <tr>
                        <th className="px-4 py-3">Fayl nomi</th>
                        <th className="px-4 py-3">Hajmi</th>
                        <th className="px-4 py-3">Yaratilgan vaqti</th>
                        <th className="px-4 py-3 text-right">Amallar</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-800 font-mono">
                      {backupData.backups.map((b) => (
                        <tr key={b.filename} className="hover:bg-gray-50/50 dark:hover:bg-gray-900/40 transition">
                          <td className="px-4 py-3 font-semibold text-gray-900 dark:text-gray-100">{b.filename}</td>
                          <td className="px-4 py-3 text-gray-500">{(b.size / (1024 * 1024)).toFixed(2)} MB</td>
                          <td className="px-4 py-3 text-gray-500">
                            {new Date(b.created_at * 1000).toLocaleString('uz-UZ')}
                          </td>
                          <td className="px-4 py-3 text-right space-x-2">
                            <button
                              type="button"
                              onClick={() => handleDownload(b.filename)}
                              className="px-2.5 py-1 bg-blue-500/10 hover:bg-blue-500/20 text-blue-500 rounded font-semibold transition"
                            >
                              <Download className="w-3.5 h-3.5 inline mr-1" /> Yuklash
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                if (confirm(`Rostdan ham '${b.filename}' faylidan bazani qayta tiklamoqchimisiz?`)) {
                                  restoreBackupMutation.mutate(b.filename)
                                }
                              }}
                              className="px-2.5 py-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-500 rounded font-semibold transition"
                            >
                              <ShieldAlert className="w-3.5 h-3.5 inline mr-1" /> Restore
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                if (confirm(`Rostdan ham '${b.filename}' faylini o'chirmoqchimisiz?`)) {
                                  deleteBackupMutation.mutate(b.filename)
                                }
                              }}
                              className="px-2.5 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded font-semibold transition"
                            >
                              <Trash2 className="w-3.5 h-3.5 inline" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyBlock title="Backup topilmadi" message="Hozircha saqlangan ma'lumotlar bazasi nusxalari yo'q." />
              )}
            </div>
          )}

          {/* System Health / Status info */}
          <div className="glass-card rounded-xl p-6 space-y-4 shadow xl:col-span-2">
            <h2 className="text-lg font-bold text-gray-950 dark:text-gray-100 flex items-center gap-2 border-b border-gray-300 dark:border-gray-800 pb-2">
              <Radio className="w-5 h-5 text-blue-450 animate-pulse" />
              Tizim holati (System Health)
            </h2>

            {summaryLoading ? (
              <LoadingBlock title="Tizim holati yuklanmoqda..." message="Serverdan health va monitoring ko‘rsatkichlari olinmoqda." />
            ) : summaryIsError ? (
              <ErrorBlock
                title="Tizim holati olinmadi"
                message={getApiErrorMessage(summaryError)}
                onRetry={() => refetchSummary()}
              />
            ) : summary ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-100/30 dark:bg-gray-950/40 p-4 border border-gray-350 dark:border-gray-800 rounded-xl shadow-inner">
                  <span className="text-xs text-gray-500 block uppercase tracking-wider mb-1">WS ulanishlar</span>
                  <strong className="text-xl font-extrabold text-blue-500 font-mono">{summary.ws_clients ?? 0} ta</strong>
                </div>
                <div className="bg-gray-100/30 dark:bg-gray-950/40 p-4 border border-gray-350 dark:border-gray-800 rounded-xl shadow-inner">
                  <span className="text-xs text-gray-500 block uppercase tracking-wider mb-1">O'lchov nuqtalari</span>
                  <strong className="text-xl font-extrabold text-green-500 font-mono">{summary.measurement_points ?? 0} ta</strong>
                </div>
                <div className="bg-gray-100/30 dark:bg-gray-950/40 p-4 border border-gray-350 dark:border-gray-800 rounded-xl shadow-inner">
                  <span className="text-xs text-gray-500 block uppercase tracking-wider mb-1">Binolar soni</span>
                  <strong className="text-xl font-extrabold text-purple-500 font-mono">{summary.buildings ?? 0} ta</strong>
                </div>
                <div className="bg-gray-100/30 dark:bg-gray-950/40 p-4 border border-gray-350 dark:border-gray-800 rounded-xl shadow-inner">
                  <span className="text-xs text-gray-500 block uppercase tracking-wider mb-1">Datchiklar jami</span>
                  <strong className="text-xl font-extrabold text-yellow-600 dark:text-yellow-500 font-mono">{summary.devices_total ?? 0} ta</strong>
                </div>
              </div>
            ) : (
              <EmptyBlock title="Tizim holati topilmadi" message="Server health maʼlumot qaytarmadi." />
            )}

            <div className="bg-blue-500/10 border border-blue-500/20 p-4 rounded-lg flex gap-3 text-xs text-blue-400">
              <Info className="w-5 h-5 shrink-0" />
              <div>
                Ushbu bo'limda tizimning umumiy ishlash ko'rsatkichlari real-time holatda monitoring qilinadi. Barcha parametrlar soatlik va kunlik hisobot jurnallariga muvofiq yangilanadi.
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex justify-end gap-3 xl:col-span-2 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-5 py-2.5 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white rounded-lg transition font-semibold shadow-md"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Saqlanmoqda...' : 'Sozlamalarni saqlash'}
            </button>
          </div>
        </form>
      </div>
    </RootLayout>
  )
}
