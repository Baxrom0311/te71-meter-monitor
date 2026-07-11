import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Plus, X, Search, Home, Building2, MapPin, Layers, Navigation, ArrowRight, Download } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useBuildings } from '@/hooks/queries'
import { useAuth } from '@/contexts/AuthContext'
import { translations } from '@/i18n/translations'
import { useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlock'
import { getApiErrorMessage } from '@/lib/errors'
import { notifySuccess } from '@/lib/toast'
import { lazy, Suspense } from 'react'
const MapboxBuildings = lazy(() => import('@/components/MapboxBuildings').then(m => ({ default: m.MapboxBuildings })))
import type { Building } from '@/types/api'

function getBuildingStatus(b: Building): 'online' | 'offline' | 'unknown' {
  if (!b.is_active) return 'offline'
  if (b.ext_sensor_online === true) return 'online'
  if (b.ext_sensor_online === false) return 'offline'
  return 'unknown'
}

const STATUS_DOT: Record<string, string> = {
  online: 'bg-green-500 shadow-[0_0_6px_#22c55e]',
  unknown: 'bg-yellow-400 shadow-[0_0_6px_#eab308]',
  offline: 'bg-red-500 shadow-[0_0_6px_#ef4444]',
}
const STATUS_LABEL: Record<string, string> = {
  online: 'Faol',
  unknown: 'Noaniq',
  offline: 'Nofaol',
}

export default function BuildingsPage() {
  const { data: buildings, isLoading, isError, error: queryError, refetch } = useBuildings()
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()

  // Search State
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedMapBuildingId, setSelectedMapBuildingId] = useState<number | null>(null)

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [mapsUrl, setMapsUrl] = useState('')
  const [floors, setFloors] = useState(4)
  const [entrancesCount, setEntrancesCount] = useState(3)
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)

  const handleImportExternal = async () => {
    setImporting(true)
    try {
      const res = await apiClient.post<{ created: number; skipped: number; total: number }>('/api/buildings/import-external')
      queryClient.invalidateQueries({ queryKey: ['buildings'] })
      notifySuccess('Import tugadi', `${res.data.created} ta yangi bino qo'shildi, ${res.data.skipped} ta o'tkazib yuborildi.`)
    } catch (err: any) {
      setError(getApiErrorMessage(err))
    } finally {
      setImporting(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setSubmitting(true)
    setError(null)

    try {
      await apiClient.post('/api/buildings', {
        name,
        address: address || null,
        maps_url: mapsUrl || null,
        floors,
        entrances_count: entrancesCount,
        description: description || null,
      })
      queryClient.invalidateQueries({ queryKey: ['buildings'] })
      notifySuccess('Bino qo‘shildi', `${name} muvaffaqiyatli yaratildi.`)
      setIsModalOpen(false)
      // Reset form
      setName('')
      setAddress('')
      setMapsUrl('')
      setFloors(4)
      setEntrancesCount(3)
      setDescription('')
    } catch (err: any) {
      console.error(err)
      setError(getApiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  // Filtered buildings list based on search query
  const filteredBuildings = useMemo(() => {
    if (!buildings) return []
    return buildings.filter((b) => {
      const q = searchQuery.toLowerCase().trim()
      if (!q) return true
      return (
        b.name.toLowerCase().includes(q) ||
        (b.address ?? '').toLowerCase().includes(q) ||
        (b.maps_url ?? '').toLowerCase().includes(q) ||
        (b.description ?? '').toLowerCase().includes(q)
      )
    })
  }, [buildings, searchQuery])

  const mappedBuildings = useMemo(
    () => filteredBuildings.filter((b) => b.latitude && b.longitude),
    [filteredBuildings],
  )

  const selectedMapBuilding = mappedBuildings.find((b) => b.id === selectedMapBuildingId) ?? mappedBuildings[0]

  return (
    <RootLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Home className="w-8 h-8 text-blue-500" />
            <h1 className="text-3xl font-bold text-gray-100">{translations.buildings.title}</h1>
          </div>
          {isAdmin && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleImportExternal}
                disabled={importing}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white rounded-lg transition text-sm font-semibold shadow"
                title="Urganchshahar API dan binolarni import qilish"
              >
                <Download className="w-4 h-4" />
                {importing ? 'Import...' : 'Import'}
              </button>
              <button
                onClick={() => setIsModalOpen(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-700 text-white rounded-lg transition text-sm font-semibold shadow"
              >
                <Plus className="w-4 h-4" />
                {translations.buildings.addBuilding}
              </button>
            </div>
          )}
        </div>

        {/* Search Toolbar */}
        <div className="flex gap-4 justify-between items-center glass-card rounded-xl p-5 shadow">
          <div className="relative w-full md:max-w-md">
            <Search className="absolute left-3 top-2.5 h-4.5 w-4.5 text-gray-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Binolar nomi yoki manzilini qidirish..."
              className="w-full pl-10 pr-4 py-2 rounded-lg glass-input focus:outline-none text-sm"
            />
          </div>
        </div>

        {/* Mapbox 3D xarita */}
        {buildings && buildings.length > 0 && (
          <div className="glass-card rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-gray-800/40">
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-blue-400" />
                <span className="font-bold text-gray-100 text-sm">Binolar xaritasi (3D)</span>
                <span className="text-xs text-gray-500">{mappedBuildings.length} ta koordinatali</span>
              </div>
              <div className="flex items-center gap-3 text-xs font-semibold">
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-green-500 inline-block" />Faol</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" />Noaniq</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500 inline-block" />Nofaol</span>
              </div>
            </div>
            <Suspense fallback={<div className="h-[500px] flex items-center justify-center bg-gray-900/50 text-gray-500 text-sm">Xarita yuklanmoqda...</div>}>
              <MapboxBuildings
                buildings={filteredBuildings}
                selectedId={selectedMapBuildingId}
                onSelect={setSelectedMapBuildingId}
                height="500px"
              />
            </Suspense>
          </div>
        )}

        {/* Buildings Grid */}
        {isLoading ? (
          <LoadingBlock title="Binolar yuklanmoqda" />
        ) : isError ? (
          <ErrorBlock message={getApiErrorMessage(queryError)} onRetry={() => refetch()} />
        ) : filteredBuildings && filteredBuildings.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredBuildings.map((building) => (
              <Link
                key={building.id}
                to={`/buildings/${building.id}`}
                className="group glass-card glass-card-hover rounded-2xl p-5 block relative overflow-hidden"
              >
                {/* Status dot */}
                {(() => {
                  const st = getBuildingStatus(building)
                  return (
                    <span className={`absolute top-4 right-4 w-2.5 h-2.5 rounded-full ${STATUS_DOT[st]}`} title={STATUS_LABEL[st]} />
                  )
                })()}

                {/* Header */}
                <div className="flex items-start gap-3 mb-3 pr-5">
                  <div className="p-2.5 rounded-xl bg-blue-500/10 text-blue-500 border border-blue-500/20 shrink-0 group-hover:scale-110 transition-transform duration-300">
                    <Building2 className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-base font-bold text-gray-950 dark:text-gray-100 group-hover:text-blue-500 transition-colors leading-tight truncate">
                      {building.name}
                    </h3>
                    {building.address && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3 h-3 shrink-0" />
                        <span className="truncate">{building.address}</span>
                      </p>
                    )}
                    {building.organization_name && (
                      <p className="text-xs text-blue-400/70 mt-0.5 truncate">{building.organization_name}</p>
                    )}
                  </div>
                </div>

                {/* Badges */}
                <div className="flex flex-wrap gap-2 my-3">
                  <span className="flex items-center gap-1 px-2.5 py-1 bg-white/5 border border-white/8 rounded-lg text-xs font-semibold text-gray-300">
                    <Layers className="w-3 h-3 text-blue-400" />{building.floors} qavat
                  </span>
                  <span className="flex items-center gap-1 px-2.5 py-1 bg-white/5 border border-white/8 rounded-lg text-xs font-semibold text-gray-300">
                    <Navigation className="w-3 h-3 text-purple-400" />{building.entrances_count} kirish
                  </span>
                  {building.ext_sensor_temp_out != null && (
                    <span className="flex items-center gap-1 px-2.5 py-1 bg-white/5 border border-white/8 rounded-lg text-xs font-semibold text-gray-300">
                      🌡 {building.ext_sensor_temp_out}°C
                    </span>
                  )}
                </div>

                {/* Footer */}
                <div className="pt-3 border-t border-white/5 flex items-center justify-between gap-2">
                  <p className="text-xs text-gray-500 truncate italic flex-1">
                    {building.description || building.mahalla_name || 'Tavsif mavjud emas'}
                  </p>
                  <ArrowRight className="w-4 h-4 text-blue-500 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all shrink-0" />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyBlock title={translations.common.noData} message="Ushbu filtrga mos keluvchi binolar topilmadi" />
        )}

        {/* Add Building Modal */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="glass-card rounded-xl max-w-md w-full max-h-[90vh] overflow-y-auto p-6 space-y-4 shadow-2xl relative animate-modal-pop">
              <button
                onClick={() => setIsModalOpen(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-900 dark:hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>

              <h3 className="text-xl font-bold text-gray-905 dark:text-gray-100">{translations.buildings.addBuilding}</h3>

              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4 text-sm">
                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Bino nomi *</label>
                    <input
                      type="text"
                      required
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Masalan: Bino A"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Manzil</label>
                    <input
                      type="text"
                      value={address}
                      onChange={(e) => setAddress(e.target.value)}
                      placeholder="Masalan: Mustaqillik shox ko'chasi, 12-uy"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{translations.buildings.mapsUrl}</label>
                    <input
                      type="url"
                      value={mapsUrl}
                      onChange={(e) => setMapsUrl(e.target.value)}
                      placeholder="https://maps.app.goo.gl/..."
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Qavatlar soni</label>
                    <input
                      type="number"
                      min={1}
                      value={floors}
                      onChange={(e) => setFloors(parseInt(e.target.value) || 1)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Kirishlar soni</label>
                    <input
                      type="number"
                      min={1}
                      value={entrancesCount}
                      onChange={(e) => setEntrancesCount(parseInt(e.target.value) || 1)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Tavsif</label>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Bino haqida qo'shimcha ma'lumotlar..."
                      rows={2}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium resize-none"
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
                    className="px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white rounded-lg transition font-medium"
                  >
                    {submitting ? 'Saqlanmoqda...' : translations.common.save}
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
