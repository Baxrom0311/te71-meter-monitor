import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Download, Plus, X, Search, Cpu, Wifi, WifiOff, PlusCircle, Zap, Droplets, Flame, Sprout, Volume2, LayoutList, LayoutGrid } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useDevicesList, useBuildings, qk } from '@/hooks/queries'
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
import { TableColumnsMenu } from '@/components/TableColumnsMenu'
import { downloadCsv, TableColumn, useColumnVisibility } from '@/lib/table'
import { Pagination } from '@/components/Pagination'

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]
const DEFAULT_PAGE_SIZE = 20

const UTILITY_TABS = [
  { key: 'electricity', label: 'Elektr',   icon: Zap,     accent: 'text-yellow-500', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20' },
  { key: 'water',       label: 'Suv',      icon: Droplets, accent: 'text-cyan-500',   bg: 'bg-cyan-500/10',   border: 'border-cyan-500/20'   },
  { key: 'gas',         label: 'Gaz',      icon: Flame,    accent: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
  { key: 'soil',        label: "Yerto'la", icon: Sprout,   accent: 'text-green-500',  bg: 'bg-green-500/10',  border: 'border-green-500/20'  },
  { key: 'sound',       label: 'Ovoz',     icon: Volume2,  accent: 'text-purple-500', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
] as const

const deviceTableColumns: TableColumn[] = [
  { key: 'status',   label: 'Holat'    },
  { key: 'id',       label: 'ID / nom' },
  { key: 'type',     label: 'Tur'      },
  { key: 'ip',       label: 'IP manzil'},
  { key: 'firmware', label: 'Firmware' },
  { key: 'actions',  label: 'Amallar'  },
]

export default function DevicesPage() {
  const navigate   = useNavigate()
  const location   = useLocation()
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()

  // ── Filter state ──────────────────────────────────────────────────────────
  const [searchQuery,  setSearchQuery]  = useState('')
  const [typeFilter,   setTypeFilter]   = useState('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'online' | 'offline'>('all')
  const [sortBy,       setSortBy]       = useState<'name' | 'type' | 'status' | 'last_seen'>('last_seen')
  const [page,         setPage]         = useState(1)
  const [pageSize,     setPageSize]     = useState(DEFAULT_PAGE_SIZE)

  // ── View mode ─────────────────────────────────────────────────────────────
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table')

  // ── Add-device modal ──────────────────────────────────────────────────────
  const [isModalOpen,  setIsModalOpen]  = useState(false)
  const [deviceId,     setDeviceId]     = useState('')
  const [name,         setName]         = useState('')
  const [utilityType,  setUtilityType]  = useState('electricity')
  const [buildingId,   setBuildingId]   = useState('')
  const [meterType,    setMeterType]    = useState('')
  const [meterSerial,  setMeterSerial]  = useState('')
  const [submitting,   setSubmitting]   = useState(false)
  const [error,        setError]        = useState<string | null>(null)

  // ── Quick-assign modal ────────────────────────────────────────────────────
  const [deviceToAssign,   setDeviceToAssign]   = useState<Device | null>(null)
  const [assignName,       setAssignName]       = useState('')
  const [assignBuildingId, setAssignBuildingId] = useState<number | ''>('')

  const { isColumnVisible, toggleColumn } = useColumnVisibility(deviceTableColumns, 'devices-table-columns')
  const { data: buildings } = useBuildings()

  // Read utility filter from URL (e.g. /devices?utility=water)
  useEffect(() => {
    const utility = new URLSearchParams(location.search).get('utility')
    if (utility === 'electricity' || utility === 'water' || utility === 'gas' || utility === 'soil' || utility === 'sound') {
      setTypeFilter(utility)
    }
  }, [location.search])

  // Reset page when any filter changes
  useEffect(() => { setPage(1) }, [searchQuery, typeFilter, statusFilter, sortBy])

  // ── Server query ──────────────────────────────────────────────────────────
  const { data, isLoading, isError, error: queryError, refetch, isFetching } = useDevicesList({
    page,
    pageSize,
    q:           searchQuery.trim() || undefined,
    utilityType: typeFilter !== 'all' ? typeFilter : undefined,
    online:      statusFilter === 'online' ? true : statusFilter === 'offline' ? false : undefined,
    sortBy:      sortBy === 'last_seen' ? 'last_seen' : sortBy,
    sortOrder:   sortBy === 'status' ? 'desc' : 'asc',
  })

  const devices    = data?.devices ?? []
  const total      = data?.total   ?? 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  // ── Mutations ─────────────────────────────────────────────────────────────
  const assignMutation = useMutation({
    mutationFn: async ({ deviceId, name, buildingId }: { deviceId: string; name: string; buildingId: number }) => {
      await apiClient.put(`/api/devices/${deviceId}`, { name, building_id: buildingId })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.devices() })
      notifySuccess('Qurilma biriktirildi')
      setDeviceToAssign(null)
    },
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!deviceId.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await apiClient.post('/api/devices', {
        device_id:     deviceId,
        name:          name || null,
        utility_type:  utilityType,
        firmware_mode: utilityType,
        meter_type:    meterType  || 'unknown',
        meter_serial:  meterSerial || null,
        building_id:   buildingId ? parseInt(buildingId) : null,
        is_active:     true,
      })
      queryClient.invalidateQueries({ queryKey: qk.devices() })
      notifySuccess('Qurilma saqlandi', `${deviceId} ro'yxatdan o'tdi.`)
      setIsModalOpen(false)
      setDeviceId(''); setName(''); setUtilityType('electricity')
      setBuildingId(''); setMeterType(''); setMeterSerial('')
    } catch (err: any) {
      setError(getApiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleExportCSV = () => {
    if (!devices.length) return
    downloadCsv(
      `devices_${new Date().toISOString().slice(0, 10)}.csv`,
      ['ID', 'Name', 'Utility', 'Status', 'IP', 'Firmware', 'Building ID'],
      devices.map((d) => [
        d.id, d.name ?? '', d.utility_type,
        d.online ? 'online' : 'offline',
        d.ip ?? '', d.fw_version ?? '', d.building_id ?? '',
      ]),
    )
    notifySuccess('CSV eksport qilindi', `${devices.length} ta qurilma (joriy sahifa)`)
  }

  return (
    <RootLayout>
      <div className="space-y-6">

        {/* ── Header ── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Cpu className="w-8 h-8 text-blue-500" />
            <div>
              <h1 className="text-3xl font-bold text-gray-100">{translations.devices.title}</h1>
              {total > 0 && !isLoading && (
                <p className="text-sm text-gray-500 mt-0.5">
                  Jami <span className="font-semibold text-gray-300">{total}</span> ta qurilma
                </p>
              )}
            </div>
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

        {/* ── Filter toolbar ── */}
        <div className="flex flex-col xl:flex-row gap-4 justify-between items-stretch xl:items-center glass-card rounded-xl p-4 sm:p-5 shadow">
          {/* Search */}
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

          {/* Filters */}
          <div className="flex flex-wrap gap-3 w-full xl:w-auto">
            {/* Utility type tabs */}
            <div className="flex rounded-lg overflow-hidden border border-gray-300 dark:border-gray-800 bg-gray-100/50 dark:bg-gray-950/50 shadow-sm">
              <button
                onClick={() => setTypeFilter('all')}
                className={clsx(
                  'px-3.5 py-1.5 text-xs font-semibold transition',
                  typeFilter === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-500 hover:text-gray-950 dark:text-gray-400 dark:hover:text-gray-100',
                )}
              >
                Hammasi
              </button>
              {UTILITY_TABS.map((u) => (
                <button
                  key={u.key}
                  onClick={() => setTypeFilter(typeFilter === u.key ? 'all' : u.key)}
                  className={clsx(
                    'px-3.5 py-1.5 text-xs font-semibold transition',
                    typeFilter === u.key
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-500 hover:text-gray-950 dark:text-gray-400 dark:hover:text-gray-100',
                  )}
                >
                  {u.label}
                </button>
              ))}
            </div>

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="px-3.5 py-1.5 rounded-lg text-xs font-semibold focus:outline-none glass-input shadow-sm"
            >
              <option value="last_seen">Saralash: oxirgi ko'rilgan</option>
              <option value="name">Saralash: nomi</option>
              <option value="type">Saralash: turi</option>
              <option value="status">Saralash: status</option>
            </select>

            {/* Status filter */}
            <div className="flex border border-gray-300 dark:border-gray-800 rounded-lg overflow-hidden bg-gray-100/50 dark:bg-gray-950/50 shadow-sm">
              {(['all', 'online', 'offline'] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={clsx(
                    'px-3.5 py-1.5 text-xs font-semibold flex items-center gap-1 transition',
                    statusFilter === s
                      ? s === 'online' ? 'bg-green-600 text-white'
                        : s === 'offline' ? 'bg-red-600 text-white'
                        : 'bg-blue-600 text-white'
                      : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200',
                  )}
                >
                  {s === 'online' && <Wifi    className="w-3.5 h-3.5" />}
                  {s === 'offline' && <WifiOff className="w-3.5 h-3.5" />}
                  {s === 'all' ? 'Barchasi' : s === 'online' ? 'Online' : 'Offline'}
                </button>
              ))}
            </div>

            {/* View toggle */}
            <div className="flex border border-gray-300 dark:border-gray-800 rounded-lg overflow-hidden bg-gray-100/50 dark:bg-gray-950/50 shadow-sm">
              <button
                onClick={() => setViewMode('table')}
                title="Jadval ko'rinishi"
                className={clsx('px-3 py-1.5 transition', viewMode === 'table' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200')}
              >
                <LayoutList className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('grid')}
                title="Karta ko'rinishi"
                className={clsx('px-3 py-1.5 transition', viewMode === 'grid' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200')}
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
            </div>

            <button
              onClick={handleExportCSV}
              disabled={!devices.length}
              className="surface-button gap-2 px-3.5 py-1.5 text-xs font-semibold"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
            <TableColumnsMenu
              columns={deviceTableColumns}
              isColumnVisible={isColumnVisible}
              toggleColumn={toggleColumn}
            />
          </div>
        </div>

        {/* ── Table ── */}
        {isLoading ? (
          <TableSkeleton rows={8} />
        ) : isError ? (
          <ErrorBlock message={getApiErrorMessage(queryError)} onRetry={() => refetch()} />
        ) : devices.length > 0 ? (
          <div className={clsx('glass-card rounded-xl overflow-hidden shadow-lg transition-opacity', isFetching && 'opacity-70')}>
            {/* Table view */}
            {viewMode === 'table' && <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-300 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30">
                    {isColumnVisible('status') && (
                      <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold w-24">
                        {translations.devices.status}
                      </th>
                    )}
                    {isColumnVisible('id') && (
                      <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                        {translations.devices.id}
                      </th>
                    )}
                    {isColumnVisible('type') && (
                      <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                        {translations.devices.type}
                      </th>
                    )}
                    {isColumnVisible('ip') && (
                      <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                        {translations.devices.ip}
                      </th>
                    )}
                    {isColumnVisible('firmware') && (
                      <th className="text-left px-6 py-4 text-gray-600 dark:text-gray-400 font-semibold">
                        {translations.devices.firmware}
                      </th>
                    )}
                    {isColumnVisible('actions') && <th className="px-6 py-4 w-10" />}
                  </tr>
                </thead>
                <tbody>
                  {devices.map((device) => (
                    <tr
                      key={device.id}
                      className={clsx(
                        'border-b border-gray-300 dark:border-gray-750 transition',
                        device.building_id === null
                          ? 'bg-yellow-550/5 dark:bg-yellow-500/5 hover:bg-yellow-550/10 dark:hover:bg-yellow-500/10'
                          : 'hover:bg-gray-100/30 dark:hover:bg-gray-850/50 cursor-pointer',
                      )}
                      onClick={() => device.building_id !== null && navigate(`/devices/${device.id}`)}
                    >
                      {isColumnVisible('status') && (
                        <td className="px-6 py-4">
                          <span
                            className={clsx(
                              'inline-block w-3 h-3 rounded-full shadow-sm',
                              device.online ? 'bg-green-400 animate-pulse' : 'bg-red-400',
                            )}
                          />
                        </td>
                      )}
                      {isColumnVisible('id') && (
                        <td className="px-6 py-4 font-semibold">
                          <div className="flex items-center gap-2">
                            <span
                              className={clsx(
                                device.building_id === null
                                  ? 'text-yellow-600 dark:text-yellow-350 cursor-pointer hover:text-yellow-700 dark:hover:text-yellow-200'
                                  : 'text-gray-950 dark:text-gray-100 hover:text-blue-500 transition font-bold',
                              )}
                              onClick={(e) => { e.stopPropagation(); navigate(`/devices/${device.id}`) }}
                            >
                              {device.name ?? device.id}
                            </span>
	                            {device.building_id === null && (
	                              <span className="px-1.5 py-0.5 text-xs bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 rounded font-semibold border border-yellow-500/25">
	                                yangi
	                              </span>
	                            )}
	                            {device.is_test_device && (
	                              <span className="px-1.5 py-0.5 text-xs bg-blue-500/10 text-blue-600 dark:text-blue-400 rounded font-semibold border border-blue-500/25">
	                                test
	                              </span>
	                            )}
	                            {device.needs_rebind && (
	                              <span className="px-1.5 py-0.5 text-xs bg-orange-500/10 text-orange-600 dark:text-orange-400 rounded font-semibold border border-orange-500/25">
	                                qayta biriktirish
	                              </span>
	                            )}
                          </div>
                          {device.meter_serial && (
                            <p className="text-xs text-gray-500 mt-0.5">{device.meter_serial}</p>
                          )}
                        </td>
                      )}
                      {isColumnVisible('type') && (
                        <td className="px-6 py-4">
                          <span className={clsx(
                            'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold border',
                            device.utility_type === 'electricity' && 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border-yellow-500/20',
                            device.utility_type === 'water'       && 'bg-cyan-500/10   text-cyan-600   dark:text-cyan-400   border-cyan-500/20',
                            device.utility_type === 'gas'         && 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20',
                            device.utility_type === 'soil'        && 'bg-green-500/10  text-green-600  dark:text-green-400  border-green-500/20',
                            device.utility_type === 'sound'       && 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
                          )}>
                            {translations.deviceTypes[device.utility_type as keyof typeof translations.deviceTypes] || device.utility_type}
                          </span>
                        </td>
                      )}
                      {isColumnVisible('ip')       && <td className="px-6 py-4 text-gray-600 dark:text-gray-400 font-mono">{device.ip       ?? '—'}</td>}
                      {isColumnVisible('firmware') && <td className="px-6 py-4 text-gray-600 dark:text-gray-400 font-mono">{device.fw_version ?? '—'}</td>}
                      {isColumnVisible('actions')  && (
                        <td className="px-6 py-4">
	                          {device.building_id === null && !device.is_test_device && isAdmin && (
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
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>}

            {/* Grid/card view */}
            {viewMode === 'grid' && <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {devices.map((device) => {
                const utilTab = UTILITY_TABS.find(u => u.key === device.utility_type)
                const Icon = utilTab?.icon ?? Cpu
                return (
                  <div
                    key={device.id}
                    onClick={() => device.building_id !== null && navigate(`/devices/${device.id}`)}
                    className={clsx(
                      'rounded-xl border p-4 flex flex-col gap-3 transition',
                      device.building_id === null
                        ? 'border-yellow-500/25 bg-yellow-500/5 hover:bg-yellow-500/10'
                        : 'border-gray-300 dark:border-gray-700 bg-white/30 dark:bg-gray-800/30 hover:bg-gray-100/40 dark:hover:bg-gray-800/50 cursor-pointer',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className={clsx('p-2 rounded-lg border', utilTab?.bg ?? 'bg-gray-500/10', utilTab?.border ?? 'border-gray-500/20')}>
                        <Icon className={clsx('w-4 h-4', utilTab?.accent ?? 'text-gray-500')} />
                      </div>
                      <div className="flex items-center gap-1.5">
                        {device.building_id === null && (
                          <span className="px-1.5 py-0.5 text-xs bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 rounded font-semibold border border-yellow-500/25">yangi</span>
                        )}
                        {device.is_test_device && (
                          <span className="px-1.5 py-0.5 text-xs bg-blue-500/10 text-blue-600 dark:text-blue-400 rounded font-semibold border border-blue-500/25">test</span>
                        )}
                        <span className={clsx('h-2.5 w-2.5 rounded-full shrink-0', device.online ? 'bg-green-400 animate-pulse' : 'bg-red-400')} />
                      </div>
                    </div>
                    <div className="min-w-0">
                      <p
                        className="font-bold text-gray-950 dark:text-gray-100 truncate text-sm leading-tight"
                        onClick={(e) => { e.stopPropagation(); navigate(`/devices/${device.id}`) }}
                      >
                        {device.name ?? device.id}
                      </p>
                      {device.name && <p className="text-xs text-gray-500 font-mono truncate mt-0.5">{device.id}</p>}
                      {device.meter_serial && <p className="text-xs text-gray-400 truncate">{device.meter_serial}</p>}
                    </div>
                    <div className="flex flex-col gap-1 text-xs text-gray-500 dark:text-gray-400">
                      <div className="flex justify-between">
                        <span>Tur</span>
                        <span className={clsx('font-semibold', utilTab?.accent)}>
                          {translations.deviceTypes[device.utility_type as keyof typeof translations.deviceTypes] || device.utility_type}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>IP</span>
                        <span className="font-mono">{device.ip ?? '—'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Firmware</span>
                        <span className="font-mono">{device.fw_version ?? '—'}</span>
                      </div>
                    </div>
                    {device.building_id === null && !device.is_test_device && isAdmin && (
                      <button
                        onClick={(e) => { e.stopPropagation(); setDeviceToAssign(device); setAssignName(device.meter_serial || device.name || device.id); setAssignBuildingId('') }}
                        className="mt-auto w-full px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition"
                      >
                        Biriktirish
                      </button>
                    )}
                  </div>
                )
              })}
            </div>}

            {/* ── Pagination ── */}
            <div className="border-t border-gray-300 dark:border-gray-800 px-4">
              <Pagination
                page={page}
                totalPages={totalPages}
                total={total}
                pageSize={pageSize}
                onPageChange={setPage}
                onPageSizeChange={(s) => { setPageSize(s); setPage(1) }}
                pageSizeOptions={PAGE_SIZE_OPTIONS}
                isLoading={isFetching}
                className="py-3"
              />
            </div>
          </div>
        ) : (
          <EmptyBlock title={translations.common.noData} message="Ushbu filtrga mos keluvchi qurilmalar topilmadi" />
        )}

        {/* ── Quick Assign Modal ── */}
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
                    type="text" value={assignName} onChange={(e) => setAssignName(e.target.value)}
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
                    {buildings?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </select>
                </div>
              </div>
              {assignMutation.isError && (
                <p className="mt-3 text-xs text-red-400">{getApiErrorMessage(assignMutation.error)}</p>
              )}
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

        {/* ── Add Device Modal ── */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="glass-card rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl relative animate-modal-pop">
              <button onClick={() => setIsModalOpen(false)} className="absolute top-4 right-4 text-gray-400 hover:text-gray-900 dark:hover:text-white transition">
                <X className="w-5 h-5" />
              </button>
              <h3 className="text-xl font-bold text-gray-905 dark:text-gray-100 flex items-center gap-2.5">
                <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-500 border border-blue-500/20">
                  <Cpu className="w-5 h-5" />
                </div>
                {translations.devices.addDevice}
              </h3>
              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">{error}</div>
              )}
              <form onSubmit={handleSubmit} className="space-y-4 text-sm">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Qurilma IDsi *</label>
                  <input type="text" required value={deviceId} onChange={(e) => setDeviceId(e.target.value)}
                    placeholder="Masalan: esp32-meter-01"
                    className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Qurilma nomi</label>
                  <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                    placeholder="Masalan: 1-qavat datchik"
                    className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Turi</label>
                    <select value={utilityType} onChange={(e) => setUtilityType(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium">
                      <option value="electricity">Elektr</option>
                      <option value="water">Suv</option>
                      <option value="gas">Gaz</option>
                      <option value="soil">Yerto'la namligi</option>
                      <option value="sound">Ovoz</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Bino</label>
                    <select value={buildingId} onChange={(e) => setBuildingId(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium">
                      <option value="">Bino tanlang (ixtiyoriy)</option>
                      {buildings?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Hisoblagich turi</label>
                    <input type="text" value={meterType} onChange={(e) => setMeterType(e.target.value)}
                      placeholder="Masalan: TE71 (ixtiyoriy)"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Serial raqami</label>
                    <input type="text" value={meterSerial} onChange={(e) => setMeterSerial(e.target.value)}
                      placeholder="Masalan: SN-12345"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium" />
                  </div>
                </div>
                <div className="flex justify-end gap-3 pt-2">
                  <button type="button" onClick={() => setIsModalOpen(false)}
                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg transition">
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
