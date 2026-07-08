import { useState, useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Link2, Unlink, Plus, X, Smartphone, Home, Edit3, Trash2, ExternalLink } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useBuildingById, useDevices } from '@/hooks/queries'
import { translations } from '@/i18n/translations'
import { useAuth } from '@/contexts/AuthContext'
import { useQueryClient } from '@tanstack/react-query'
import { useTheme } from '@/contexts/ThemeContext'
import apiClient from '@/lib/api'

export default function BuildingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const { isDark } = useTheme()
  const queryClient = useQueryClient()

  const buildingIdInt = id ? parseInt(id) : 0
  const { data: building, isLoading: buildingLoading } = useBuildingById(id || '')
  const { data: devices, isLoading: devicesLoading } = useDevices(100)

  // Bind Device modal states
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [selectedDeviceId, setSelectedDeviceId] = useState('')
  const [binding, setBinding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Edit Building states
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [editName, setEditName] = useState('')
  const [editAddress, setEditAddress] = useState('')
  const [editMapsUrl, setEditMapsUrl] = useState('')
  const [editLatitude, setEditLatitude] = useState('')
  const [editLongitude, setEditLongitude] = useState('')
  const [editFloors, setEditFloors] = useState(1)
  const [editEntrancesCount, setEditEntrancesCount] = useState(1)
  const [editDescription, setEditDescription] = useState('')
  const [updating, setUpdating] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  // Filter devices belonging to this building
  const buildingDevices = useMemo(() => {
    if (!devices || !buildingIdInt) return []
    return devices.filter((d) => d.building_id === buildingIdInt)
  }, [devices, buildingIdInt])

  // Filter devices that have NO building assigned
  const unassignedDevices = useMemo(() => {
    if (!devices) return []
    return devices.filter((d) => !d.building_id)
  }, [devices])

  if (!id) return <div className="text-red-400 p-8">{translations.common.error}</div>

  const handleBindDevice = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedDeviceId) return
    setBinding(true)
    setError(null)

    try {
      const dev = devices?.find((d) => d.id === selectedDeviceId)
      if (dev) {
        await apiClient.put(`/api/devices/${selectedDeviceId}`, {
          building_id: buildingIdInt,
          name: dev.name || null,
          utility_type: dev.utility_type,
          is_active: dev.is_active ?? true,
        })
      }
      queryClient.invalidateQueries({ queryKey: ['devices'] })
      setIsModalOpen(false)
      setSelectedDeviceId('')
    } catch (err: any) {
      console.error(err)
      setError(err.response?.data?.detail || 'Qurilmani biriktirishda xatolik yuz berdi')
    } finally {
      setBinding(false)
    }
  }

  const handleUnbindDevice = async (deviceId: string) => {
    if (!confirm('Haqiqatdan ham ushbu qurilmani binodan uzmoqchisiz?')) return
    try {
      const dev = devices?.find((d) => d.id === deviceId)
      if (dev) {
        await apiClient.put(`/api/devices/${deviceId}`, {
          building_id: null,
          name: dev.name || null,
          utility_type: dev.utility_type,
          is_active: dev.is_active ?? true,
        })
      }
      queryClient.invalidateQueries({ queryKey: ['devices'] })
    } catch (err) {
      console.error('Error unbinding device:', err)
    }
  }

  const openEditModal = () => {
    if (!building) return
    setEditName(building.name)
    setEditAddress(building.address ?? '')
    setEditMapsUrl(building.maps_url ?? '')
    setEditLatitude(building.latitude?.toString() ?? '')
    setEditLongitude(building.longitude?.toString() ?? '')
    setEditFloors(building.floors)
    setEditEntrancesCount(building.entrances_count)
    setEditDescription(building.description ?? '')
    setEditError(null)
    setIsEditModalOpen(true)
  }

  const handleEditBuilding = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editName.trim()) return
    setUpdating(true)
    setEditError(null)

    try {
      await apiClient.put(`/api/buildings/${buildingIdInt}`, {
        name: editName,
        address: editAddress || null,
        maps_url: editMapsUrl || null,
        latitude: editLatitude ? Number(editLatitude) : null,
        longitude: editLongitude ? Number(editLongitude) : null,
        floors: editFloors,
        entrances_count: editEntrancesCount,
        description: editDescription || null,
      })
      queryClient.invalidateQueries({ queryKey: ['building', id] })
      queryClient.invalidateQueries({ queryKey: ['buildings'] })
      setIsEditModalOpen(false)
    } catch (err: any) {
      console.error(err)
      setEditError(err.response?.data?.detail || 'Binoni tahrirlashda xatolik yuz berdi')
    } finally {
      setUpdating(false)
    }
  }

  const handleDeleteBuilding = async () => {
    if (!confirm('Haqiqatdan ham ushbu binoni butunlay o\'chirmoqchisiz? Barcha ulanishlar uziladi.')) return
    try {
      await apiClient.delete(`/api/buildings/${buildingIdInt}`)
      queryClient.invalidateQueries({ queryKey: ['buildings'] })
      navigate('/buildings')
    } catch (err) {
      console.error('Error deleting building:', err)
      alert('Binoni o\'chirishda xatolik yuz berdi. Ehtimol, unga datchiklar bog\'langandir.')
    }
  }

  return (
    <RootLayout>
      <div className="space-y-6">
        {/* Back Button */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 transition text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          {translations.common.back}
        </button>

        {/* Building Details */}
        {buildingLoading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : building ? (
          <div className="space-y-6">
            {/* Building Info Card */}
            <div className="glass-card rounded-xl p-6 shadow space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <Home className="w-7 h-7 text-blue-500" />
                  <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">{building.name}</h1>
                </div>
                {isAdmin && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={openEditModal}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold border border-gray-200 dark:border-gray-700 transition"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      Tahrirlash
                    </button>
                    <button
                      onClick={handleDeleteBuilding}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600/10 hover:bg-red-650 text-red-400 hover:text-white rounded-lg text-xs font-semibold border border-red-500/20 transition"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      O'chirish
                    </button>
                  </div>
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2 text-sm">
                <div>
                  <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">{translations.buildings.address}</p>
                  <p className="text-base text-gray-900 dark:text-gray-100 font-medium">{building.address ?? '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">{translations.buildings.mapsUrl}</p>
                  {building.maps_url ? (
                    <a
                      href={building.maps_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-base text-blue-600 dark:text-blue-400 hover:underline font-medium"
                    >
                      Google Maps
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  ) : (
                    <p className="text-base text-gray-900 dark:text-gray-100 font-medium">—</p>
                  )}
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">{translations.buildings.coordinates}</p>
                  <p className="text-base text-gray-900 dark:text-gray-100 font-medium">
                    {building.latitude != null && building.longitude != null
                      ? `${building.latitude}, ${building.longitude}`
                      : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">Qavatlar soni</p>
                  <p className="text-base text-gray-900 dark:text-gray-100 font-medium">{building.floors}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">Kirish joylari</p>
                  <p className="text-base text-gray-900 dark:text-gray-100 font-medium">{building.entrances_count}</p>
                </div>
              </div>
              {building.description && (
                <div className="pt-2 border-t border-gray-200 dark:border-gray-800 text-sm">
                  <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">Tavsif</p>
                  <p className="text-gray-700 dark:text-gray-300">{building.description}</p>
                </div>
              )}
            </div>

            {/* Connected Devices List */}
            <div className="glass-card rounded-xl p-6 shadow space-y-4">
              <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-800 pb-3">
                <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                  <Smartphone className="w-5 h-5 text-blue-500" />
                  Biriktirilgan qurilmalar ({buildingDevices.length})
                </h2>
                {isAdmin && (
                  <button
                    onClick={() => setIsModalOpen(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition text-xs font-semibold shadow"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Qurilma biriktirish
                  </button>
                )}
              </div>

              {devicesLoading ? (
                <div className="flex justify-center py-6">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
                </div>
              ) : buildingDevices.length > 0 ? (
                <div className="overflow-x-auto pt-2">
                  <table className="w-full text-sm text-left">
                    <thead>
                      <tr className="border-b border-gray-300 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30 text-gray-650 dark:text-gray-400 font-semibold">
                        <th className="px-6 py-4">Status</th>
                        <th className="px-6 py-4">Qurilma nomi / ID</th>
                        <th className="px-6 py-4">Turi</th>
                        <th className="px-6 py-4">IP manzil</th>
                        {isAdmin && <th className="px-6 py-4 text-right">Amallar</th>}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-300 dark:divide-gray-800 text-gray-750 dark:text-gray-300">
                      {buildingDevices.map((device) => (
                        <tr key={device.id} className="hover:bg-gray-100/30 dark:hover:bg-gray-850/40 transition">
                          <td className="px-6 py-4">
                            <span
                              className={`inline-block w-2.5 h-2.5 rounded-full ${
                                device.online ? 'bg-green-500 animate-pulse' : 'bg-red-500'
                              }`}
                            />
                          </td>
                          <td className="px-6 py-4 font-bold text-gray-950 dark:text-gray-100 hover:text-blue-500 transition">
                            <Link to={`/devices/${device.id}`}>{device.name ?? device.id}</Link>
                          </td>
                          <td className="px-6 py-4 text-gray-700 dark:text-gray-350">
                            {translations.deviceTypes[device.utility_type as keyof typeof translations.deviceTypes] || device.utility_type}
                          </td>
                          <td className="px-6 py-4 font-mono text-gray-600 dark:text-gray-400">{device.ip ?? '—'}</td>
                          {isAdmin && (
                            <td className="px-6 py-4 text-right">
                              <button
                                onClick={() => handleUnbindDevice(device.id)}
                                title="Binodan uzish"
                                className="p-1.5 bg-red-600 hover:bg-red-700 text-white rounded transition shadow-sm border border-red-500/10"
                              >
                                <Unlink className="w-4 h-4" />
                              </button>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-gray-500 italic text-sm text-center py-6">Ushbu binoga hali hech qanday qurilma biriktirilmagan.</p>
              )}
            </div>
          </div>
        ) : (
          <div className="glass-card rounded-xl p-12 text-center shadow">
            <p className="text-gray-400">{translations.common.noData}</p>
          </div>
        )}

        {/* Edit Building Modal */}
        {isEditModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="glass-card rounded-xl max-w-md w-full max-h-[90vh] overflow-y-auto p-6 space-y-4 shadow-2xl relative">
              <button
                onClick={() => setIsEditModalOpen(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-900 dark:hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>

              <h3 className="text-xl font-bold text-gray-905 dark:text-gray-100 flex items-center gap-2">
                <Edit3 className="w-5 h-5 text-blue-500" />
                Binoni Tahrirlash
              </h3>

              {editError && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                  {editError}
                </div>
              )}

              <form onSubmit={handleEditBuilding} className="space-y-4 text-sm">
                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Bino nomi *</label>
                    <input
                      type="text"
                      required
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Manzil</label>
                    <input
                      type="text"
                      value={editAddress}
                      onChange={(e) => setEditAddress(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{translations.buildings.mapsUrl}</label>
                    <input
                      type="url"
                      value={editMapsUrl}
                      onChange={(e) => setEditMapsUrl(e.target.value)}
                      placeholder="https://maps.google.com/..."
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Latitude</label>
                    <input
                      type="number"
                      step="any"
                      min={-90}
                      max={90}
                      value={editLatitude}
                      onChange={(e) => setEditLatitude(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Longitude</label>
                    <input
                      type="number"
                      step="any"
                      min={-180}
                      max={180}
                      value={editLongitude}
                      onChange={(e) => setEditLongitude(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Qavatlar soni</label>
                    <input
                      type="number"
                      min={1}
                      value={editFloors}
                      onChange={(e) => setEditFloors(parseInt(e.target.value) || 1)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Kirishlar soni</label>
                    <input
                      type="number"
                      min={1}
                      value={editEntrancesCount}
                      onChange={(e) => setEditEntrancesCount(parseInt(e.target.value) || 1)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Tavsif</label>
                    <textarea
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      rows={2}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium resize-none"
                    />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsEditModalOpen(false)}
                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg transition"
                  >
                    {translations.common.cancel}
                  </button>
                  <button
                    type="submit"
                    disabled={updating}
                    className="px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white rounded-lg transition font-medium font-semibold"
                  >
                    {updating ? 'Saqlanmoqda...' : 'Saqlash'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Bind Device Modal */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="glass-card rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl relative">
              <button
                onClick={() => setIsModalOpen(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-900 dark:hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>

              <h3 className="text-xl font-bold text-gray-905 dark:text-gray-100 flex items-center gap-2">
                <Link2 className="w-5 h-5 text-blue-500" />
                Qurilma Biriktirish
              </h3>

              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                  {error}
                </div>
              )}

              <form onSubmit={handleBindDevice} className="space-y-4 text-sm">
                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Bo'sh turgan qurilma *</label>
                    {unassignedDevices.length > 0 ? (
                      <select
                        value={selectedDeviceId}
                        required
                        onChange={(e) => setSelectedDeviceId(e.target.value)}
                        className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                      >
                        <option value="">Qurilma tanlang...</option>
                        {unassignedDevices.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.name ?? d.id} ({translations.deviceTypes[d.utility_type as keyof typeof translations.deviceTypes] || d.utility_type})
                          </option>
                        ))}
                      </select>
                    ) : (
                      <p className="text-gray-500 italic mt-1 bg-gray-100/50 dark:bg-gray-950/40 p-3 rounded-lg border border-gray-300 dark:border-gray-800 text-xs">
                        Hozirda biriktirilmagan bo'sh qurilmalar mavjud emas. Yangi qurilma qo'shing.
                      </p>
                    )}
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
                    disabled={binding || !selectedDeviceId}
                    className="px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white rounded-lg transition font-medium font-semibold"
                  >
                    {binding ? 'Biriktirilmoqda...' : 'Biriktirish'}
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
