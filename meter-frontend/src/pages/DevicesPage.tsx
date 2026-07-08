import { useEffect, useState, useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Download, Plus, X, Search, Cpu, Wifi, WifiOff, PlusCircle, Zap, Droplets, Flame } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useDevices, useBuildings } from '@/hooks/queries'
import { useAuth } from '@/contexts/AuthContext'
import { translations } from '@/i18n/translations'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import clsx from 'clsx'
import { Device } from '@/types/api'
import { EmptyBlock, ErrorBlock } from '@/components/StateBlock'
import { getApiErrorMessage } from '@/lib/errors'
import { notifySuccess } from '@/lib/toast'
import { TableSkeleton } from '@/components/Skeleton'

const utilityCards = [
  { key: 'electricity', label: 'Elektr', icon: Zap, accent: 'text-yellow-500', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20' },
  { key: 'water', label: 'Suv', icon: Droplets, accent: 'text-cyan-500', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20' },
  { key: 'gas', label: 'Gaz', icon: Flame, accent: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
] as const

export default function DevicesPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { data: devices, isLoading, isError, error: queryError, refetch } = useDevices()
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
      notifySuccess('Qurilma biriktirildi')
      setDeviceToAssign(null)
    },
  })

  // Filters State
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'online' | 'offline'>('all')
  const [sortBy, setSortBy] = useState<'name' | 'type' | 'status'>('name')
  const [page, setPage] = useState(1)
  const pageSize = 12

  useEffect(() => {
    const utility = new URLSearchParams(location.search).get('utility')
    if (utility === 'electricity' || utility === 'water' || utility === 'gas') {
      setTypeFilter(utility)
    }
  }, [location.search])

  const utilityStats = useMemo(() => {
    const source = devices ?? []
    return utilityCards.map((utility) => {
      const rows = source.filter((device) => device.utility_type === utility.key)
      return {
        ...utility,
        total: rows.length,
        online: rows.filter((device) => device.online).length,
        unassigned: rows.filter((device) => device.building_id === null).length,
      }
    })
  }, [devices])

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
      notifySuccess('Qurilma saqlandi', `${deviceId} ro‘yxatdan o‘tdi.`)
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
      setError(getApiErrorMessage(err))
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
    }).sort((a, b) => {
      if (sortBy === 'status') return Number(b.online) - Number(a.online)
      if (sortBy === 'type') return a.utility_type.localeCompare(b.utility_type)
      return (a.name ?? a.id).localeCompare(b.name ?? b.id)
    })
  }, [devices, searchQuery, typeFilter, statusFilter, sortBy])

  const groupedDevices = useMemo(() => {
    if (!devices) return []
    const q = searchQuery.toLowerCase().trim()
    const baseRows = devices.filter((device) => {
      const matchesSearch =
        !q ||
        (device.name ?? '').toLowerCase().includes(q) ||
        device.id.toLowerCase().includes(q) ||
        (device.ip ?? '').toLowerCase().includes(q)

      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'online' && device.online) ||
        (statusFilter === 'offline' && !device.online)

      return matchesSearch && matchesStatus
    })

    return utilityCards.map((utility) => ({
      ...utility,
      rows: baseRows
        .filter((device) => device.utility_type === utility.key)
        .sort((a, b) => {
          if (sortBy === 'status') return Number(b.online) - Number(a.online)
          return (a.name ?? a.id).localeCompare(b.name ?? b.id)
        }),
    }))
  }, [devices, searchQuery, statusFilter, sortBy])

  useEffect(() => {
    setPage(1)
  }, [searchQuery, typeFilter, statusFilter, sortBy])

  const totalPages = Math.max(1, Math.ceil(filteredDevices.length / pageSize))
  const pagedDevices = useMemo(
    () => filteredDevices.slice((page - 1) * pageSize, page * pageSize),
    [filteredDevices, page],
  )

  const handleExportCSV = () => {
    if (filteredDevices.length === 0) return
    const rows = [
      ['ID', 'Name', 'Utility', 'Status', 'IP', 'Firmware', 'Building ID'].join(','),
      ...filteredDevices.map((device) => [
        device.id,
        device.name ?? '',
        device.utility_type,
        device.online ? 'online' : 'offline',
        device.ip ?? '',
        device.fw_version ?? '',
        device.building_id ?? '',
      ].map((value) => `"${String(value).replace(/"/g, '""')}"`).join(',')),
    ]
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `devices_${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
    notifySuccess('CSV eksport qilindi', `${filteredDevices.length} ta qurilma eksport qilindi.`)
  }

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

        {!isLoading && !isError && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {utilityStats.map((utility) => {
              const Icon = utility.icon
              const active = typeFilter === utility.key
              return (
                <button
                  key={utility.key}
                  onClick={() => setTypeFilter(active ? 'all' : utility.key)}
                  className={clsx(
                    'glass-card rounded-xl p-4 text-left border transition hover:-translate-y-0.5',
                    active ? `${utility.border} ring-2 ring-blue-500/30` : 'hover:border-blue-500/30'
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-bold text-gray-950 dark:text-gray-100">{utility.label}</p>
                      <p className="text-2xl font-extrabold text-gray-950 dark:text-gray-100 mt-1">{utility.total}</p>
                    </div>
                    <div className={`p-2.5 rounded-lg ${utility.bg} ${utility.border} border`}>
                      <Icon className={`w-5 h-5 ${utility.accent}`} />
                    </div>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs">
                    <span className="text-green-600 dark:text-green-400 font-bold">{utility.online} online</span>
                    <span className="text-yellow-600 dark:text-yellow-400 font-bold">{utility.unassigned} birikmagan</span>
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {/* Filters Toolbar */}
        <div className="flex flex-col xl:flex-row gap-4 justify-between items-stretch xl:items-center glass-card rounded-xl p-4 sm:p-5 shadow">
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
          <div className="flex flex-wrap gap-3 w-full xl:w-auto">
            <div className="flex rounded-lg overflow-hidden border border-gray-300 dark:border-gray-800 bg-gray-100/50 dark:bg-gray-950/50 shadow-sm">
              <button
                onClick={() => setTypeFilter('all')}
                className={clsx(
                  'px-3.5 py-1.5 text-xs font-semibold transition',
                  typeFilter === 'all' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-950 dark:text-gray-400 dark:hover:text-gray-100'
                )}
              >
                Hammasi
              </button>
              {utilityStats.map((utility) => (
                <button
                  key={utility.key}
                  onClick={() => setTypeFilter(utility.key)}
                  className={clsx(
                    'px-3.5 py-1.5 text-xs font-semibold transition',
                    typeFilter === utility.key ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-950 dark:text-gray-400 dark:hover:text-gray-100'
                  )}
                >
                  {utility.label} ({utility.total})
                </button>
              ))}
            </div>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'name' | 'type' | 'status')}
              className="px-3.5 py-1.5 rounded-lg text-xs font-semibold focus:outline-none glass-input shadow-sm"
            >
              <option value="name">Saralash: nomi</option>
              <option value="type">Saralash: turi</option>
              <option value="status">Saralash: status</option>
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

            <button
              onClick={handleExportCSV}
              disabled={filteredDevices.length === 0}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-gray-100 hover:bg-gray-200 disabled:opacity-45 dark:bg-gray-850 dark:hover:bg-gray-750 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-800 transition"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
          </div>
        </div>

        {typeFilter === 'all' && !isLoading && !isError && groupedDevices.length > 0 && (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            {groupedDevices.map((group) => {
              const Icon = group.icon
              return (
                <section key={group.key} className="glass-card rounded-2xl p-4 border relative overflow-hidden">
                  <div className={`absolute inset-x-0 top-0 h-1 ${group.key === 'electricity' ? 'bg-yellow-500' : group.key === 'water' ? 'bg-cyan-500' : 'bg-orange-500'}`} />
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <div>
                      <p className="text-base font-extrabold text-gray-950 dark:text-gray-100">{group.label}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{group.rows.length} ta qurilma</p>
                    </div>
                    <div className={`p-2.5 rounded-xl ${group.bg} ${group.border} border`}>
                      <Icon className={`w-5 h-5 ${group.accent}`} />
                    </div>
                  </div>

                  {group.rows.length > 0 ? (
                    <div className="space-y-2">
                      {group.rows.slice(0, 4).map((device) => (
                        <button
                          key={device.id}
                          onClick={() => navigate(`/devices/${device.id}`)}
                          className="w-full rounded-xl border border-gray-300/60 dark:border-gray-800/70 bg-white/35 dark:bg-gray-950/25 px-3 py-2.5 text-left hover:border-blue-500/35 hover:bg-blue-500/5 transition"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-bold text-gray-950 dark:text-gray-100">{device.name ?? device.id}</p>
                              <p className="truncate text-xs text-gray-500 font-mono">{device.ip ?? device.id}</p>
                            </div>
                            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${device.online ? 'bg-green-500' : 'bg-red-500'}`} />
                          </div>
                        </button>
                      ))}
                      {group.rows.length > 4 && (
                        <button
                          onClick={() => setTypeFilter(group.key)}
                          className="w-full rounded-xl border border-blue-500/20 bg-blue-500/10 px-3 py-2 text-xs font-bold text-blue-600 dark:text-blue-400 hover:bg-blue-500/15 transition"
                        >
                          Yana {group.rows.length - 4} tasini ko‘rish
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="rounded-xl border border-dashed border-gray-300 dark:border-gray-800 p-4 text-center text-xs text-gray-500">
                      Hozircha {group.label.toLowerCase()} qurilmasi yo‘q.
                    </div>
                  )}
                </section>
              )
            })}
          </div>
        )}

        {/* Devices Table */}
        {isLoading ? (
          <TableSkeleton rows={8} />
        ) : isError ? (
          <ErrorBlock message={getApiErrorMessage(queryError)} onRetry={() => refetch()} />
        ) : filteredDevices && filteredDevices.length > 0 ? (
          <div className="glass-card rounded-xl overflow-hidden shadow-lg">
            <div className="px-4 py-3 border-b border-gray-300 dark:border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <p className="text-xs font-semibold text-gray-600 dark:text-gray-400">
                {filteredDevices.length} ta natija · {page}/{totalPages} sahifa
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
                  {pagedDevices.map((device) => (
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
                        <span className={clsx(
                          'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold border',
                          device.utility_type === 'electricity' && 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border-yellow-500/20',
                          device.utility_type === 'water' && 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20',
                          device.utility_type === 'gas' && 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20',
                        )}>
                          {translations.deviceTypes[device.utility_type as keyof typeof translations.deviceTypes] || device.utility_type}
                        </span>
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
            <div className="md:hidden mobile-card-list p-3">
              {pagedDevices.map((device) => (
                <div key={device.id} className="mobile-data-card">
                  <div className="flex items-start justify-between gap-3">
                    <button
                      onClick={() => navigate(`/devices/${device.id}`)}
                      className="text-left min-w-0"
                    >
                      <p className="font-bold text-gray-950 dark:text-gray-100 truncate">{device.name ?? device.id}</p>
                      <p className="text-xs text-gray-500 font-mono truncate">{device.id}</p>
                    </button>
                    <div className="flex items-center gap-2 shrink-0">
                      {device.building_id === null && (
                        <span className="px-1.5 py-0.5 text-xs bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 rounded font-semibold border border-yellow-500/25">
                          yangi
                        </span>
                      )}
                      <span className={`h-2.5 w-2.5 rounded-full ${device.online ? 'bg-green-500' : 'bg-red-500'}`} />
                    </div>
                  </div>
                  <div className="mobile-data-row">
                    <span className="mobile-data-label">{translations.devices.type}</span>
                    <span className="mobile-data-value">
                      {translations.deviceTypes[device.utility_type as keyof typeof translations.deviceTypes] || device.utility_type}
                    </span>
                  </div>
                  <div className="mobile-data-row">
                    <span className="mobile-data-label">{translations.devices.ip}</span>
                    <span className="mobile-data-value font-mono">{device.ip ?? '—'}</span>
                  </div>
                  <div className="mobile-data-row">
                    <span className="mobile-data-label">{translations.devices.firmware}</span>
                    <span className="mobile-data-value font-mono">{device.fw_version ?? '—'}</span>
                  </div>
                  {device.building_id === null && isAdmin && (
                    <button
                      onClick={() => {
                        setDeviceToAssign(device)
                        setAssignName(device.meter_serial || device.name || device.id)
                        setAssignBuildingId('')
                      }}
                      className="mt-3 w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition"
                    >
                      Biriktirish
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyBlock title={translations.common.noData} message="Ushbu filtrga mos keluvchi qurilmalar topilmadi" />
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
