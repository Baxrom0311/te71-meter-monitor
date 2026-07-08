import { useState } from 'react'
import { Settings, Info, Save, Bot, Key, Radio } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { translations } from '@/i18n/translations'
import { useSummary } from '@/hooks/queries'

export default function SettingsPage() {
  const { data: summary } = useSummary()

  // Telegram Notifications Mock State
  const [botToken, setBotToken] = useState('5839201948:AAFlk3849Dk2849Dk_f81747Djs9')
  const [chatId, setChatId] = useState('-100192840192')
  const [tgEnabled, setTgEnabled] = useState(true)

  // API Config State
  const [apiBase, setApiBase] = useState(import.meta.env.VITE_API_URL || 'http://localhost:8001')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setMsg(null)
    setTimeout(() => {
      setSaving(false)
      setMsg('Sozlamalar muvaffaqiyatli saqlandi!')
    }, 800)
  }

  return (
    <RootLayout>
      <div className="space-y-6 max-w-4xl">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Settings className="w-8 h-8 text-blue-500" />
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">{translations.settings.title}</h1>
        </div>

        {msg && (
          <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg text-sm text-green-400">
            {msg}
          </div>
        )}

        <form onSubmit={handleSave} className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
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

          {/* System Health / Status info */}
          <div className="glass-card rounded-xl p-6 space-y-4 shadow md:col-span-2">
            <h2 className="text-lg font-bold text-gray-950 dark:text-gray-100 flex items-center gap-2 border-b border-gray-300 dark:border-gray-800 pb-2">
              <Radio className="w-5 h-5 text-blue-450 animate-pulse" />
              Tizim holati (System Health)
            </h2>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-gray-100/30 dark:bg-gray-950/40 p-4 border border-gray-350 dark:border-gray-800 rounded-xl shadow-inner">
                <span className="text-xs text-gray-500 block uppercase tracking-wider mb-1">WS ulanishlar</span>
                <strong className="text-xl font-extrabold text-blue-500 font-mono">{summary?.ws_clients ?? 0} ta</strong>
              </div>
              <div className="bg-gray-100/30 dark:bg-gray-950/40 p-4 border border-gray-350 dark:border-gray-800 rounded-xl shadow-inner">
                <span className="text-xs text-gray-500 block uppercase tracking-wider mb-1">O'lchov nuqtalari</span>
                <strong className="text-xl font-extrabold text-green-500 font-mono">{summary?.measurement_points ?? 0} ta</strong>
              </div>
              <div className="bg-gray-100/30 dark:bg-gray-950/40 p-4 border border-gray-350 dark:border-gray-800 rounded-xl shadow-inner">
                <span className="text-xs text-gray-500 block uppercase tracking-wider mb-1">Binolar soni</span>
                <strong className="text-xl font-extrabold text-purple-500 font-mono">{summary?.buildings ?? 0} ta</strong>
              </div>
              <div className="bg-gray-100/30 dark:bg-gray-950/40 p-4 border border-gray-350 dark:border-gray-800 rounded-xl shadow-inner">
                <span className="text-xs text-gray-500 block uppercase tracking-wider mb-1">Datchiklar jami</span>
                <strong className="text-xl font-extrabold text-yellow-600 dark:text-yellow-500 font-mono">{summary?.devices_total ?? 0} ta</strong>
              </div>
            </div>

            <div className="bg-blue-500/10 border border-blue-500/20 p-4 rounded-lg flex gap-3 text-xs text-blue-400">
              <Info className="w-5 h-5 shrink-0" />
              <div>
                Ushbu bo'limda tizimning umumiy ishlash ko'rsatkichlari real-time holatda monitoring qilinadi. Barcha parametrlar soatlik va kunlik hisobot jurnallariga muvofiq yangilanadi.
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex justify-end gap-3 md:col-span-2 pt-2">
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
