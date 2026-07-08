import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, X, Search, Cpu, Wifi, WifiOff, PlusCircle } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useDevices, useBuildings } from '@/hooks/queries'
import { useAuth } from '@/contexts/AuthContext'
import { translations } from '@/i18n/translations'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import clsx from 'clsx'
import { Device } from '@/types/api'

export default function DevicesPage() {
  const navigate = useNavigate()
  const { data: devices, isLoading } = useDevices()
  const { data: buildings } = useBuildings()
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [deviceId, setDeviceId] = useState('')
  const [name, setName] = useState('')
  const [utilityType, setUtilityType] = useState('electricity')
  const [buildingId, setBuildingId] = useState('')
  const [meterType, setMeterType] = useState('')
  const [meterSerial, setMeterSerial] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Quick-assign state (for unassigned devices)
  const [deviceToAssign, setDeviceToAssign] = useState<Device | null>(null)
  const [assignName, setAssignName] = useState('')
  const [assignBuildingId, setAssignBuildingId] = useState<number | ''>('')

  const assignMutation = useMutation({
    mutationFn: async ({ deviceId, name, buildingId }: { deviceId: string; name: string; buildingId: number }) => {
      await apiClient.put(`/api/devices/${deviceId}`, { name, building_id: buildingId })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] })
      setDeviceToAssign(null)
    },
  })

  // Filters State
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'online' | 'offline'>('all')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!deviceId.trim()) return
    setSubmitting(true)
    setError(null)

    try {
      // 1. Register device
      await apiClient.post('/api/register', {
        device_id: deviceId,
        name: name || null,
        utility_type: utilityType,
        meter_type: meterType || 'unknown',
        meter_serial: meterSerial || null,
      })

      // 2. If building selected, update device using PUT /api/devices/{device_id}
      if (buildingId) {
        await apiClient.put(`/api/devices/${deviceId}`, {
          building_id: parseInt(buildingId),
          name: name || null,
          utility_type: utilityType,
          is_active: true,
        })
      }

      queryClient.invalidateQueries({ queryKey: ['devices'] })
      setIsModalOpen(false)
      // Reset form
      setDeviceId('')
      setName('')
      setUtilityType('electricity')
      setBuildingId('')
      setMeterType('')
      setMeterSerial('')
    } catch (err: any) {
      console.error(err)
      setError(err.response?.data?.detail || 'Xatolik yuz berdi')
    } finally {
      setSubmitting(false)
    }
  }

  // Filtered devices list based on search, type, and status
  const filteredDevices = useMemo(() => {
    if (!devices) return []
    return devices.filter((device) => {
      const q = searchQuery.toLowerCase().trim()
      const matchesSearch =
        !q ||
        (device.name ?? '').toLowerCase().includes(q) ||
        device.id.toLowerCase().includes(q) ||
        (device.ip ?? '').toLowerCase().includes(q)

      const matchesType = typeFilter === 'all' || device.utility_type === typeFilter
      
      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'online' && device.online) ||
        (statusFilter === 'offline' && !device.online)

      return matchesSearch && matchesType && matchesStatus
    })
  }, [devices, searchQuery, typeFilter, statusFilter])

  return (
    <RootLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Cpu className="w-8 h-8 text-blue-500" />
            <h1 className="text-3xl font-bold text-gray-100">{translations.devices.title}</h1>
          </div>
          {isAdmin && (
            <button
              onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-700 text-white rounded-lg transition text-sm font-semibold shadow"
            >
              <Plus className="w-4 h-4" />
              {translations.devices.addDevice}
            </button>
          )}
        </div>

        {/* Filters Toolbar */}
        <div className="flex flex-col md:flex-row gap-4 justify-between items-center glass-card rounded-xl p-5 shadow">
          {/* Search Bar */}
          <div className="relative w-full md:max-w-md">
            <Search className="absolute left-3 top-2.5 h-4.5 w-4.5 text-gray-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Qurilma ID, nomi yoki IP manzilini qidirish..."
              className="w-full pl-10 pr-4 py-2 rounded-lg glass-input focus:outline-none text-sm"
            />
          </div>

          {/* Quick Filters */}
          <div className="flex flex-wrap gap-3 w-full md:w-auto">
            {/* Utility Type Filter */}
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3.5 py-1.5 rounded-lg text-xs font-semibold focus:outline-none glass-input shadow-sm"
            >
              <option value="all">Barcha datchik turlari</option>
              <option value="electricity">Elektr</option>
              <option value="water">Suv</option>
              <option value="gas">Gaz</option>
            </select>

            {/* Status Filters */}
            <div className="flex border border-gray-300 dark:border-gray-800 rounded-lg overflow-hidden bg-gray-100/50 dark:bg-gray-950/50 shadow-sm">
              <button
                onClick={() => setStatusFilter('all')}
                className={clsx(
                  'px-3.5 py-1.5 text-xs font-semibold transition',
                  statusFilter === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-200/50 dark:hover:bg-gray-900/60'
                )}
              >
                Barchasi
              </button>
              <button
                onClick={() => setStatusFilter('online')}
                className={clsx(
                  'px-3.5 py-1.5 text-xs font-semibold flex items-center gap-1 transition',
                  statusFilter === 'online'
                    ? 'bg-green-600 text-white'
                    : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-200/50 dark:hover:bg-gray-900/60'
                )}
              >
                <Wifi className="w-3.5 h-3.5" />
                Online
              </button>
              <button
                onClick={() => setStatusFilter('offline')}
                className={clsx(
                  'px-3.5 py-1.5 text-xs font-semibold flex items-center gap-1 transition',
                  statusFilter === 'offline'
                    ? 'bg-red-650 text-white'
                    : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-200/50 dark:hover:bg-gray-900/60'
                )}
              >
                <WifiOff className="w-3.5 h-3.5" />
                Offline
              </button>
            </div>
          </div>
        </div>

        {/* Devices Table */}
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : filteredDevices && filteredDevices.length > 0 ? (
          <div className="glass-card rounded-xl overflow-hidden shadow-lg">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-300 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30">
                    <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold w-24">
                      {translations.devices.status}
                    </th>
                    <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                      {translations.devices.id}
                    </th>
                    <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                      {translations.devices.type}
                    </th>
                    <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                      {translations.devices.ip}
                    </th>
                    <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                      {translations.devices.firmware}
                    </th>
                    <th className="px-6 py-4 w-10" />
                  </tr>
                </thead>
                <tbody>
                  {filteredDevices.map((device) => (
                    <tr
                      key={device.id}
                      className={clsx(
                        'border-b border-gray-300 dark:border-gray-750 transition',
                        device.building_id === null
                          ? 'bg-yellow-550/5 dark:bg-yellow-500/5 hover:bg-yellow-550/10 dark:hover:bg-yellow-500/10'
                          : 'hover:bg-gray-100/30 dark:hover:bg-gray-850/50 cursor-pointer'
                      )}
                      onClick={() => device.building_id !== null && navigate(`/devices/${device.id}`)}
                    >
                      <td className="px-6 py-4">
                        <span
                          className={`inline-block w-3 h-3 rounded-full shadow-sm ${
                            device.online ? 'bg-green-400 animate-pulse' : 'bg-red-400'
                          }`}
                        />
                      </td>
                      <td className="px-6 py-4 font-semibold">
                        <div className="flex items-center gap-2">
                          <span
                            className={clsx(
                              device.building_id === null
                                ? 'text-yellow-600 dark:text-yellow-350 cursor-pointer hover:text-yellow-700 dark:hover:text-yellow-200'
                                : 'text-gray-950 dark:text-gray-100 hover:text-blue-500 transition font-bold'
                            )}
                            onClick={(e) => {
                              e.stopPropagation()
                              navigate(`/devices/${device.id}`)
                            }}
                          >
                            {device.name ?? device.id}
                          </span>
                          {device.building_id === null && (
                            <span className="px-1.5 py-0.5 text-xs bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 rounded font-semibold border border-yellow-500/25">
                              yangi
                            </span>
                          )}
                        </div>
                        {device.meter_serial && (
                          <p className="text-xs text-gray-500 mt-0.5">{device.meter_serial}</p>
                        )}
                      </td>
                      <td className="px-6 py-4 text-gray-700 dark:text-gray-300">
                        {translations.deviceTypes[device.utility_type as keyof typeof translations.deviceTypes] || device.utility_type}
                      </td>
                      <td className="px-6 py-4 text-gray-600 dark:text-gray-400 font-mono">{device.ip ?? '—'}</td>
                      <td className="px-6 py-4 text-gray-600 dark:text-gray-400 font-mono">{device.fw_version ?? '—'}</td>
                      <td className="px-6 py-4">
                        {device.building_id === null && isAdmin && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setDeviceToAssign(device)
                              setAssignName(device.meter_serial || device.name || device.id)
                              setAssignBuildingId('')
                            }}
                            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition whitespace-nowrap"
                          >
                            Biriktirish
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="glass-card rounded-xl p-12 text-center shadow">
            <p className="text-gray-400">{translations.common.noData}</p>
            <p className="text-gray-500 text-sm mt-1">Ushbu filtrga mos keluvchi qurilmalar topilmadi</p>
          </div>
        )}

        {/* Quick Assign Modal */}
        {deviceToAssign && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
            <div className="w-full max-w-md glass-card rounded-2xl p-6 shadow-2xl border border-gray-700">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                  <PlusCircle className="w-5 h-5 text-yellow-400" />
                  <h3 className="text-lg font-bold text-gray-100">Binoga biriktirish</h3>
                </div>
                <button onClick={() => setDeviceToAssign(null)} className="p-1.5 rounded-lg hover:bg-gray-700 text-gray-400 transition">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="mb-4 p-3 rounded-lg bg-gray-800/50 text-sm text-gray-400 space-y-1">
                <p><span className="text-gray-300 font-medium">ID:</span> {deviceToAssign.id}</p>
                {deviceToAssign.meter_serial && <p><span className="text-gray-300 font-medium">Serial:</span> {deviceToAssign.meter_serial}</p>}
                <p><span className="text-gray-300 font-medium">Tur:</span> {deviceToAssign.meter_type || deviceToAssign.utility_type}</p>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Qurilma nomi</label>
                  <input
                    type="text"
                    value={assignName}
                    onChange={(e) => setAssignName(e.target.value)}
                    placeholder="Masalan: 3-qavat, 12-xona"
                    className="w-full px-3 py-2.5 rounded-lg glass-input text-sm focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Bino</label>
                  <select
                    value={assignBuildingId}
                    onChange={(e) => setAssignBuildingId(e.target.value ? Number(e.target.value) : '')}
                    className="w-full px-3 py-2.5 rounded-lg glass-input text-sm focus:outline-none"
                  >
                    <option value="">— Binoni tanlang —</option>
                    {buildings?.map((b) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              {assignMutation.isError && <p className="mt-3 text-xs text-red-400">Xato yuz berdi. Qaytadan urinib ko'ring.</p>}
              <div className="mt-5 flex gap-3">
                <button onClick={() => setDeviceToAssign(null)} className="flex-1 px-4 py-2.5 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm font-medium transition">
                  Bekor
                </button>
                <button
                  onClick={() => {
                    if (!assignBuildingId || !assignName.trim()) return
                    assignMutation.mutate({ deviceId: deviceToAssign.id, name: assignName.trim(), buildingId: assignBuildingId as number })
                  }}
                  disabled={!assignBuildingId || !assignName.trim() || assignMutation.isPending}
                  className="flex-1 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold transition flex items-center justify-center gap-2"
                >
                  {assignMutation.isPending && <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent" />}
                  Saqlash
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Add Device Modal */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="glass-card rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl relative animate-modal-pop">
              <button
                onClick={() => setIsModalOpen(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-900 dark:hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>

              <h3 className="text-xl font-bold text-gray-905 dark:text-gray-100 flex items-center gap-2.5">
                <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-500 border border-blue-500/20">
                  <Cpu className="w-5 h-5" />
                </div>
                {translations.devices.addDevice}
              </h3>

              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4 text-sm">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Qurilma IDsi *</label>
                  <input
                    type="text"
                    required
                    value={deviceId}
                    onChange={(e) => setDeviceId(e.target.value)}
                    placeholder="Masalan: esp32-meter-01"
                    className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                  />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Qurilma nomi</label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Masalan: 1-qavat datchik"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Turi</label>
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
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Bino ulanishi</label>
                    <select
                      value={buildingId}
                      onChange={(e) => setBuildingId(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                      <option value="">Bino tanlang (ixtiyoriy)</option>
                      {buildings?.map((b) => (
                        <option key={b.id} value={b.id}>{b.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Hisoblagich turi</label>
                    <input
                      type="text"
                      value={meterType}
                      onChange={(e) => setMeterType(e.target.value)}
                      placeholder="Masalan: TE71 (ixtiyoriy)"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Serial raqami</label>
                    <input
                      type="text"
                      value={meterSerial}
                      onChange={(e) => setMeterSerial(e.target.value)}
                      placeholder="Masalan: SN-12345"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
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
