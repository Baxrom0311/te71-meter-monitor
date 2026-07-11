import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Plus, X, Search, Home, Building2, MapPin, Layers, Navigation,
  ArrowRight, Download, LayoutGrid, Table2, Settings2, Check,
} from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useBuildings } from '@/hooks/queries'
import { useAuth } from '@/contexts/AuthContext'
import { translations } from '@/i18n/translations'
import { useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlock'
import { getApiErrorMessage } from '@/lib/errors'
import { notifySuccess } from '@/lib/toast'
import type { Building } from '@/types/api'

import { GoogleBuildingsMap } from '@/components/GoogleBuildingsMap'

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
const STATUS_TEXT_COLOR: Record<string, string> = {
  online: 'text-green-400',
  unknown: 'text-yellow-400',
  offline: 'text-red-400',
}

// Jadval ustunlari
const ALL_COLUMNS = [
  { key: 'name',              label: 'Nomi' },
  { key: 'address',           label: 'Manzil' },
  { key: 'organization',      label: 'Tashkilot' },
  { key: 'status',            label: 'Holat' },
  { key: 'floors',            label: 'Qavatlar' },
  { key: 'entrances',         label: 'Kirishlar' },
  { key: 'apartments',        label: 'Xonadonlar' },
  { key: 'temp_out',          label: 'Tashqi °C' },
  { key: 'temp_in',           label: 'Ichki °C' },
  { key: 'mahalla',           label: 'Mahalla' },
  { key: 'object_type',       label: 'Tur' },
  { key: 'construction_year', label: 'Qurilgan yil' },
] as const

type ColKey = typeof ALL_COLUMNS[number]['key']

const DEFAULT_COLS = new Set<ColKey>(['name', 'address', 'organization', 'status', 'floors', 'entrances', 'temp_out'])

export default function BuildingsPage() {
  const { data: buildings, isLoading, isError, error: queryError, refetch } = useBuildings()
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()

  const [searchQuery, setSearchQuery] = useState('')
  const [selectedMapBuildingId, setSelectedMapBuildingId] = useState<number | null>(null)
  const [viewMode, setViewMode] = useState<'card' | 'table'>('card')
  const [visibleCols, setVisibleCols] = useState<Set<ColKey>>(DEFAULT_COLS)
  const [colPickerOpen, setColPickerOpen] = useState(false)

  // Modal
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

  const toggleCol = (key: ColKey) => {
    setVisibleCols(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

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
        name, address: address || null, maps_url: mapsUrl || null,
        floors, entrances_count: entrancesCount, description: description || null,
      })
      queryClient.invalidateQueries({ queryKey: ['buildings'] })
      notifySuccess('Bino qo\'shildi', `${name} muvaffaqiyatli yaratildi.`)
      setIsModalOpen(false)
      setName(''); setAddress(''); setMapsUrl(''); setFloors(4); setEntrancesCount(3); setDescription('')
    } catch (err: any) {
      setError(getApiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const filteredBuildings = useMemo(() => {
    if (!buildings) return []
    return buildings.filter(b => {
      const q = searchQuery.toLowerCase().trim()
      if (!q) return true
      return (
        b.name.toLowerCase().includes(q) ||
        (b.address ?? '').toLowerCase().includes(q) ||
        (b.organization_name ?? '').toLowerCase().includes(q) ||
        (b.mahalla_name ?? '').toLowerCase().includes(q) ||
        (b.description ?? '').toLowerCase().includes(q)
      )
    })
  }, [buildings, searchQuery])

  const mappedBuildings = useMemo(
    () => filteredBuildings.filter(b => b.latitude && b.longitude),
    [filteredBuildings],
  )

  return (
    <RootLayout>
      <div className="space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Home className="w-7 h-7 text-blue-500" />
            <h1 className="text-2xl font-bold text-gray-100">{translations.buildings.title}</h1>
            {buildings && (
              <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">{buildings.length}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {isAdmin && (
              <>
                <button onClick={handleImportExternal} disabled={importing}
                  className="flex items-center gap-2 px-3 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white rounded-lg transition text-xs font-semibold shadow">
                  <Download className="w-3.5 h-3.5" />{importing ? 'Import...' : 'Import'}
                </button>
                <button onClick={() => setIsModalOpen(true)}
                  className="flex items-center gap-2 px-3 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition text-xs font-semibold shadow">
                  <Plus className="w-3.5 h-3.5" />{translations.buildings.addBuilding}
                </button>
              </>
            )}
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex gap-3 items-center glass-card rounded-xl p-4 shadow flex-wrap">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
            <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              placeholder="Nomi, manzil, tashkilot..."
              className="w-full pl-9 pr-4 py-2 rounded-lg glass-input focus:outline-none text-sm" />
          </div>

          {/* View toggle */}
          <div className="flex items-center gap-1 bg-gray-800/60 rounded-lg p-1">
            <button onClick={() => setViewMode('card')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition ${viewMode === 'card' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}>
              <LayoutGrid className="w-3.5 h-3.5" /> Kartalar
            </button>
            <button onClick={() => setViewMode('table')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition ${viewMode === 'table' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}>
              <Table2 className="w-3.5 h-3.5" /> Jadval
            </button>
          </div>

          {/* Column picker (only in table mode) */}
          {viewMode === 'table' && (
            <div className="relative">
              <button onClick={() => setColPickerOpen(v => !v)}
                className="flex items-center gap-1.5 px-3 py-2 bg-gray-800/60 hover:bg-gray-700/60 rounded-lg text-xs font-semibold text-gray-300 transition border border-gray-700/40">
                <Settings2 className="w-3.5 h-3.5" /> Ustunlar
              </button>
              {colPickerOpen && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setColPickerOpen(false)} />
                  <div className="absolute right-0 top-9 z-40 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-3 min-w-[180px] space-y-1">
                    {ALL_COLUMNS.map(col => (
                      <button key={col.key} onClick={() => toggleCol(col.key)}
                        className="flex items-center gap-2.5 w-full px-2 py-1.5 rounded-lg hover:bg-gray-800 text-sm text-left transition">
                        <span className={`w-4 h-4 rounded flex items-center justify-center border transition ${visibleCols.has(col.key) ? 'bg-blue-600 border-blue-600' : 'border-gray-600'}`}>
                          {visibleCols.has(col.key) && <Check className="w-2.5 h-2.5 text-white" />}
                        </span>
                        <span className="text-gray-300 text-xs font-medium">{col.label}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Stats */}
          <div className="flex items-center gap-3 ml-auto text-xs text-gray-500">
            <span>{filteredBuildings.length} ta bino</span>
            {searchQuery && <span className="text-blue-400">filtrlangan</span>}
          </div>
        </div>

        {/* Map */}
        {buildings && buildings.length > 0 && (
          <div className="glass-card rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-gray-800/40">
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-blue-400" />
                <span className="font-bold text-gray-100 text-sm">Binolar xaritasi</span>
                <span className="text-xs text-gray-500">{mappedBuildings.length} ta koordinatali</span>
              </div>
              <div className="flex items-center gap-3 text-xs font-semibold">
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-green-500 inline-block" />Faol</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" />Noaniq</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500 inline-block" />Nofaol</span>
              </div>
            </div>
              <GoogleBuildingsMap buildings={filteredBuildings} selectedId={selectedMapBuildingId} onSelect={setSelectedMapBuildingId} height="480px" />
          </div>
        )}

        {/* Content */}
        {isLoading ? (
          <LoadingBlock title="Binolar yuklanmoqda" />
        ) : isError ? (
          <ErrorBlock message={getApiErrorMessage(queryError)} onRetry={() => refetch()} />
        ) : filteredBuildings.length === 0 ? (
          <EmptyBlock title={translations.common.noData} message="Ushbu filtrga mos binolar topilmadi" />
        ) : viewMode === 'card' ? (
          /* ─── CARD VIEW ─── */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredBuildings.map(building => {
              const st = getBuildingStatus(building)
              return (
                <Link key={building.id} to={`/buildings/${building.id}`}
                  className="group glass-card glass-card-hover rounded-2xl p-5 block relative overflow-hidden">
                  <span className={`absolute top-4 right-4 w-2.5 h-2.5 rounded-full ${STATUS_DOT[st]}`} title={STATUS_LABEL[st]} />
                  <div className="flex items-start gap-3 mb-3 pr-5">
                    <div className="p-2.5 rounded-xl bg-blue-500/10 text-blue-500 border border-blue-500/20 shrink-0 group-hover:scale-110 transition-transform duration-300">
                      <Building2 className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-base font-bold text-gray-950 dark:text-gray-100 group-hover:text-blue-500 transition-colors leading-tight truncate">
                        {building.name}
                      </h3>
                      {building.address && (
                        <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                          <MapPin className="w-3 h-3 shrink-0" /><span className="truncate">{building.address}</span>
                        </p>
                      )}
                      {building.organization_name && (
                        <p className="text-xs text-blue-400/70 mt-0.5 truncate">{building.organization_name}</p>
                      )}
                    </div>
                  </div>
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
                  <div className="pt-3 border-t border-white/5 flex items-center justify-between gap-2">
                    <p className="text-xs text-gray-500 truncate italic flex-1">
                      {building.description || building.mahalla_name || 'Tavsif mavjud emas'}
                    </p>
                    <ArrowRight className="w-4 h-4 text-blue-500 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all shrink-0" />
                  </div>
                </Link>
              )
            })}
          </div>
        ) : (
          /* ─── TABLE VIEW ─── */
          <div className="glass-card rounded-2xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800/60 bg-gray-900/40">
                    {visibleCols.has('name') && <th className="text-left px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Nomi</th>}
                    {visibleCols.has('address') && <th className="text-left px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Manzil</th>}
                    {visibleCols.has('organization') && <th className="text-left px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Tashkilot</th>}
                    {visibleCols.has('status') && <th className="text-left px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Holat</th>}
                    {visibleCols.has('floors') && <th className="text-center px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Qavat</th>}
                    {visibleCols.has('entrances') && <th className="text-center px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Kirish</th>}
                    {visibleCols.has('apartments') && <th className="text-center px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Xonadon</th>}
                    {visibleCols.has('temp_out') && <th className="text-center px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Tashqi °C</th>}
                    {visibleCols.has('temp_in') && <th className="text-center px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Ichki °C</th>}
                    {visibleCols.has('mahalla') && <th className="text-left px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Mahalla</th>}
                    {visibleCols.has('object_type') && <th className="text-left px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Tur</th>}
                    {visibleCols.has('construction_year') && <th className="text-center px-4 py-3 text-xs font-bold uppercase text-gray-400 whitespace-nowrap">Yil</th>}
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/40">
                  {filteredBuildings.map(b => {
                    const st = getBuildingStatus(b)
                    return (
                      <tr key={b.id} className="hover:bg-gray-800/30 transition-colors group">
                        {visibleCols.has('name') && (
                          <td className="px-4 py-3 font-semibold text-gray-100 whitespace-nowrap max-w-[200px]">
                            <span className="truncate block">{b.name}</span>
                          </td>
                        )}
                        {visibleCols.has('address') && (
                          <td className="px-4 py-3 text-gray-400 text-xs max-w-[180px]">
                            <span className="truncate block">{b.address ?? '—'}</span>
                          </td>
                        )}
                        {visibleCols.has('organization') && (
                          <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{b.organization_name ?? '—'}</td>
                        )}
                        {visibleCols.has('status') && (
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className={`flex items-center gap-1.5 text-xs font-semibold ${STATUS_TEXT_COLOR[st]}`}>
                              <span className={`w-2 h-2 rounded-full ${STATUS_DOT[st]}`} />
                              {STATUS_LABEL[st]}
                            </span>
                          </td>
                        )}
                        {visibleCols.has('floors') && <td className="px-4 py-3 text-center text-gray-300 text-xs">{b.floors}</td>}
                        {visibleCols.has('entrances') && <td className="px-4 py-3 text-center text-gray-300 text-xs">{b.entrances_count}</td>}
                        {visibleCols.has('apartments') && <td className="px-4 py-3 text-center text-gray-400 text-xs">{b.total_apartments ?? '—'}</td>}
                        {visibleCols.has('temp_out') && (
                          <td className="px-4 py-3 text-center text-xs">
                            {b.ext_sensor_temp_out != null ? <span className="text-orange-300">{b.ext_sensor_temp_out}°</span> : <span className="text-gray-600">—</span>}
                          </td>
                        )}
                        {visibleCols.has('temp_in') && (
                          <td className="px-4 py-3 text-center text-xs">
                            {b.ext_sensor_temp_in != null ? <span className="text-blue-300">{b.ext_sensor_temp_in}°</span> : <span className="text-gray-600">—</span>}
                          </td>
                        )}
                        {visibleCols.has('mahalla') && <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{b.mahalla_name ?? '—'}</td>}
                        {visibleCols.has('object_type') && <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{b.object_type ?? '—'}</td>}
                        {visibleCols.has('construction_year') && <td className="px-4 py-3 text-center text-gray-400 text-xs">{b.construction_year ?? '—'}</td>}
                        <td className="px-4 py-3">
                          <Link to={`/buildings/${b.id}`}
                            className="opacity-0 group-hover:opacity-100 inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 text-xs font-semibold transition">
                            Ko'rish <ArrowRight className="w-3 h-3" />
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Add Building Modal */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="glass-card rounded-xl max-w-md w-full max-h-[90vh] overflow-y-auto p-6 space-y-4 shadow-2xl relative animate-modal-pop">
              <button onClick={() => setIsModalOpen(false)} className="absolute top-4 right-4 text-gray-400 hover:text-white transition">
                <X className="w-5 h-5" />
              </button>
              <h3 className="text-xl font-bold text-gray-100">{translations.buildings.addBuilding}</h3>
              {error && <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">{error}</div>}
              <form onSubmit={handleSubmit} className="space-y-4 text-sm">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Bino nomi *</label>
                  <input type="text" required value={name} onChange={e => setName(e.target.value)}
                    placeholder="Masalan: Bino A" className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Manzil</label>
                  <input type="text" value={address} onChange={e => setAddress(e.target.value)}
                    placeholder="Ko'cha, uy raqami" className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">{translations.buildings.mapsUrl}</label>
                  <input type="url" value={mapsUrl} onChange={e => setMapsUrl(e.target.value)}
                    placeholder="https://maps.app.goo.gl/..." className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1.5">Qavatlar soni</label>
                    <input type="number" min={1} value={floors} onChange={e => setFloors(parseInt(e.target.value) || 1)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1.5">Kirishlar soni</label>
                    <input type="number" min={1} value={entrancesCount} onChange={e => setEntrancesCount(parseInt(e.target.value) || 1)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium" />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Tavsif</label>
                  <textarea value={description} onChange={e => setDescription(e.target.value)}
                    placeholder="Qo'shimcha ma'lumotlar..." rows={2}
                    className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium resize-none" />
                </div>
                <div className="flex justify-end gap-3 pt-2">
                  <button type="button" onClick={() => setIsModalOpen(false)}
                    className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition">
                    {translations.common.cancel}
                  </button>
                  <button type="submit" disabled={submitting}
                    className="px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white rounded-lg transition font-medium">
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
