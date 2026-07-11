import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Plus, X, Search, Home, Building2, MapPin, Layers, Navigation, ArrowRight, ExternalLink, Download } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useBuildings } from '@/hooks/queries'
import { useAuth } from '@/contexts/AuthContext'
import { translations } from '@/i18n/translations'
import { useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlock'
import { getApiErrorMessage } from '@/lib/errors'
import { notifySuccess } from '@/lib/toast'
import { MapPanel } from '@/components/MapPanel'
import { resolveCoordinates } from '@/lib/map'

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
  const [floors, setFloors] = useState(1)
  const [entrancesCount, setEntrancesCount] = useState(1)
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
      setFloors(1)
      setEntrancesCount(1)
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
    () => filteredBuildings.filter((b) => resolveCoordinates(b.latitude, b.longitude, b.maps_url)),
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

        {mappedBuildings.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_0.8fr] gap-5">
            {selectedMapBuilding && (
              <MapPanel
                title="Binolar xaritasi"
                subtitle={`${mappedBuildings.length} ta koordinatali bino`}
                name={selectedMapBuilding.name}
                address={selectedMapBuilding.address}
                mapsUrl={selectedMapBuilding.maps_url}
                latitude={selectedMapBuilding.latitude}
                longitude={selectedMapBuilding.longitude}
                heightClassName="h-[360px]"
              />
            )}

            <div className="glass-card rounded-2xl p-5 space-y-4">
              {selectedMapBuilding ? (
                <>
                  <div>
                    <p className="text-xs font-bold uppercase text-gray-500 mb-1">Tanlangan bino</p>
                    <h2 className="text-xl font-bold text-gray-950 dark:text-gray-100">{selectedMapBuilding.name}</h2>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{selectedMapBuilding.address ?? 'Manzil kiritilmagan'}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl border border-gray-300 dark:border-gray-800 p-3">
                      <p className="text-[11px] uppercase font-bold text-gray-500">Latitude</p>
                      <p className="font-mono text-sm text-gray-950 dark:text-gray-100">{selectedMapBuilding.latitude}</p>
                    </div>
                    <div className="rounded-xl border border-gray-300 dark:border-gray-800 p-3">
                      <p className="text-[11px] uppercase font-bold text-gray-500">Longitude</p>
                      <p className="font-mono text-sm text-gray-950 dark:text-gray-100">{selectedMapBuilding.longitude}</p>
                    </div>
                  </div>
                  <div className="max-h-44 overflow-y-auto space-y-2 pr-1">
                    {mappedBuildings.map((building) => (
                      <button
                        key={building.id}
                        onClick={() => setSelectedMapBuildingId(building.id)}
                        className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                          selectedMapBuilding.id === building.id
                            ? 'border-blue-500/40 bg-blue-500/10'
                            : 'border-gray-300/60 dark:border-gray-800/70 hover:border-blue-500/30'
                        }`}
                      >
                        <p className="text-sm font-bold text-gray-950 dark:text-gray-100">{building.name}</p>
                        <p className="text-xs text-gray-500 truncate">{building.address ?? building.maps_url ?? 'Manzil yo‘q'}</p>
                      </button>
                    ))}
                  </div>
                  {selectedMapBuilding.maps_url && (
                    <a
                      href={selectedMapBuilding.maps_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-blue-700 transition"
                    >
                      <ExternalLink className="w-4 h-4" />
                      Google Mapsda ochish
                    </a>
                  )}
                </>
              ) : (
                <EmptyBlock title="Koordinata yo‘q" message="Xaritada ko‘rsatish uchun latitude/longitude kerak." />
              )}
            </div>
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
                className="group glass-card glass-card-hover rounded-2xl p-6 block relative overflow-hidden"
              >
                {/* Building Icon & Header */}
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="space-y-1">
                    <h3 className="text-xl font-bold text-gray-950 dark:text-gray-100 group-hover:text-blue-500 transition-colors">
                      {building.name}
                    </h3>
                    {building.address && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-blue-550 shrink-0" />
                        <span className="truncate">{building.address}</span>
                      </p>
                    )}
                  </div>
                  <div className="p-3 rounded-xl bg-blue-500/10 text-blue-500 border border-blue-500/20 shadow-inner group-hover:scale-110 transition-transform duration-300">
                    <Building2 className="w-5 h-5" />
                  </div>
                </div>

                {/* Badges Info */}
                <div className="flex flex-wrap gap-2.5 my-4">
                  <div className="flex items-center gap-1.5 px-3 py-1 bg-gray-100/50 dark:bg-white/5 border border-gray-300/40 dark:border-white/5 rounded-lg text-xs font-semibold text-gray-700 dark:text-gray-300">
                    <Layers className="w-3.5 h-3.5 text-blue-500" />
                    <span>{building.floors} qavat</span>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-1 bg-gray-100/50 dark:bg-white/5 border border-gray-300/40 dark:border-white/5 rounded-lg text-xs font-semibold text-gray-700 dark:text-gray-300">
                    <Navigation className="w-3.5 h-3.5 text-purple-500" />
                    <span>{building.entrances_count} kirish</span>
                  </div>
                  {building.maps_url && (
                    <div className="flex items-center gap-1.5 px-3 py-1 bg-gray-100/50 dark:bg-white/5 border border-gray-300/40 dark:border-white/5 rounded-lg text-xs font-semibold text-gray-700 dark:text-gray-300">
                      <ExternalLink className="w-3.5 h-3.5 text-emerald-500" />
                      <span>Maps</span>
                    </div>
                  )}
                </div>

                {/* Description and arrow */}
                <div className="pt-3 border-t border-gray-300/40 dark:border-white/5 flex items-center justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    {building.description ? (
                      <p className="text-xs text-gray-500 dark:text-gray-450 truncate italic">
                        {building.description}
                      </p>
                    ) : (
                      <p className="text-xs text-gray-500 dark:text-gray-550 italic">
                        Tavsif mavjud emas
                      </p>
                    )}
                  </div>
                  <div className="text-blue-500 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all duration-300 shrink-0">
                    <ArrowRight className="w-4 h-4" />
                  </div>
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
