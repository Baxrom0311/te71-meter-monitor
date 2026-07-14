import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Cpu, FlaskConical, Play, RefreshCw, Search, ShieldCheck, Timer, Wifi, WifiOff } from 'lucide-react'
import clsx from 'clsx'
import { RootLayout } from '@/components/layout/RootLayout'
import { Pagination } from '@/components/Pagination'
import { EmptyBlock, ErrorBlock } from '@/components/StateBlock'
import { TableSkeleton } from '@/components/Skeleton'
import { qk, useDevicesList } from '@/hooks/queries'
import apiClient from '@/lib/api'
import { getApiErrorMessage } from '@/lib/errors'
import { notifyError, notifySuccess } from '@/lib/toast'
import type { Device } from '@/types/api'

const PAGE_SIZE_OPTIONS = [10, 20, 50]
const DEFAULT_PAGE_SIZE = 20
const TEST_METER_SERIAL = '202032000525'

interface SimulationResponse {
  ok: boolean
  saved: boolean
  guarded: boolean
  message: string
  ts?: number | null
  device?: Device | null
}

function formatTime(ts?: number | null) {
  return ts ? new Date(ts * 1000).toLocaleString('uz-UZ') : '-'
}

function Countdown({ ts }: { ts?: number | null }) {
  const [secondsLeft, setSecondsLeft] = useState<number>(0)

  useEffect(() => {
    if (!ts) return
    const calculateSeconds = () => {
      const left = ts - Math.floor(Date.now() / 1000)
      setSecondsLeft(left > 0 ? left : 0)
    }

    calculateSeconds()
    const interval = setInterval(calculateSeconds, 1000)
    return () => clearInterval(interval)
  }, [ts])

  if (!ts) return <span>-</span>
  if (secondsLeft <= 0) {
    return <span className="text-red-500 font-bold">muddati tugagan</span>
  }

  const minutes = Math.floor(secondsLeft / 60)
  const seconds = secondsLeft % 60
  return (
    <span>
      {minutes}:{seconds.toString().padStart(2, '0')}
    </span>
  )
}

export default function TestDevicesPage() {
  const queryClient = useQueryClient()
  const [macQuery, setMacQuery] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [simDeviceId, setSimDeviceId] = useState('')
  const [simMeterSerial, setSimMeterSerial] = useState(TEST_METER_SERIAL)
  const [simEnergy, setSimEnergy] = useState('1')
  const [lastSimulation, setLastSimulation] = useState<SimulationResponse | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)

  const { data, isLoading, isFetching, isError, error, refetch } = useDevicesList({
    page,
    pageSize,
    deviceId: macQuery.trim() || undefined,
    q: searchQuery.trim() || undefined,
    isTestDevice: true,
    sortBy: 'last_seen',
    sortOrder: 'desc',
  })

  const devices = data?.devices ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const onlineCount = devices.filter((device) => device.online).length
  const canSimulate = simDeviceId.trim().length > 0 && simMeterSerial.trim().length > 0

  const simulationMutation = useMutation({
    mutationFn: async (productionGuardOnly: boolean) => {
      const { data: result } = await apiClient.post<SimulationResponse>('/api/test-devices/simulate-reading', {
        device_id: simDeviceId.trim(),
        meter_serial: simMeterSerial.trim(),
        utility_type: 'electricity',
        energy_kwh: Number(simEnergy) || 1,
        production_guard_only: productionGuardOnly,
      })
      return result
    },
    onSuccess: (result) => {
      setLastSimulation(result)
      queryClient.invalidateQueries({ queryKey: qk.devices() })
      if (result.saved) {
        setMacQuery(simDeviceId.trim())
        setPage(1)
        notifySuccess('Test reading yuborildi', result.message)
      } else {
        notifySuccess('Guard tekshirildi', result.message)
      }
    },
    onError: (err) => {
      notifyError('Test flow bajarilmadi', getApiErrorMessage(err))
    },
  })

  return (
    <RootLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="h-11 w-11 rounded-xl bg-blue-500/10 text-blue-500 border border-blue-500/20 flex items-center justify-center">
              <FlaskConical className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-950 dark:text-gray-100">Test qurilmalar</h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Test hisoblagichlar production binolarga biriktirilmaydi va 5 minutdan keyin o'chiriladi.
              </p>
            </div>
          </div>
          <button
            onClick={() => refetch()}
            className="surface-button gap-2 px-3.5 py-2 text-sm font-semibold self-start lg:self-auto"
          >
            <RefreshCw className={clsx('w-4 h-4', isFetching && 'animate-spin')} />
            Yangilash
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="glass-card rounded-xl p-4">
            <p className="text-xs uppercase font-bold text-gray-500">Jami test</p>
            <p className="text-2xl font-extrabold text-gray-950 dark:text-gray-100 mt-1">{total}</p>
          </div>
          <div className="glass-card rounded-xl p-4">
            <p className="text-xs uppercase font-bold text-gray-500">Online</p>
            <p className="text-2xl font-extrabold text-green-500 mt-1">{onlineCount}</p>
          </div>
          <div className="glass-card rounded-xl p-4">
            <p className="text-xs uppercase font-bold text-gray-500">Test serial</p>
            <p className="text-2xl font-extrabold text-blue-500 mt-1">202032000525</p>
          </div>
        </div>

        <div className="glass-card rounded-xl p-4">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end">
            <label className="space-y-1.5 xl:w-80">
              <span className="text-xs font-bold uppercase text-gray-500">Simulate MAC / Device ID</span>
              <input
                type="text"
                value={simDeviceId}
                onChange={(event) => setSimDeviceId(event.target.value)}
                placeholder="ESP32 MAC yoki device_id"
                className="w-full px-3 py-2 rounded-lg glass-input focus:outline-none text-sm font-mono"
              />
            </label>
            <label className="space-y-1.5 xl:w-56">
              <span className="text-xs font-bold uppercase text-gray-500">Hisoblagich serial</span>
              <input
                type="text"
                value={simMeterSerial}
                onChange={(event) => setSimMeterSerial(event.target.value)}
                className="w-full px-3 py-2 rounded-lg glass-input focus:outline-none text-sm font-mono"
              />
            </label>
            <label className="space-y-1.5 xl:w-32">
              <span className="text-xs font-bold uppercase text-gray-500">kWh</span>
              <input
                type="number"
                min="0"
                step="0.001"
                value={simEnergy}
                onChange={(event) => setSimEnergy(event.target.value)}
                className="w-full px-3 py-2 rounded-lg glass-input focus:outline-none text-sm"
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={!canSimulate || simulationMutation.isPending}
                onClick={() => simulationMutation.mutate(false)}
                className="surface-button gap-2 px-3.5 py-2 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Play className="w-4 h-4" />
                Test reading
              </button>
              <button
                type="button"
                disabled={!canSimulate || simulationMutation.isPending}
                onClick={() => simulationMutation.mutate(true)}
                className="surface-button gap-2 px-3.5 py-2 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ShieldCheck className="w-4 h-4" />
                Guard tekshir
              </button>
            </div>
          </div>

          {lastSimulation && (
            <div
              className={clsx(
                'mt-4 rounded-lg border px-3 py-2 text-sm',
                lastSimulation.guarded
                  ? 'border-green-500/25 bg-green-500/10 text-green-600 dark:text-green-400'
                  : 'border-blue-500/25 bg-blue-500/10 text-blue-600 dark:text-blue-400',
              )}
            >
              <div className="flex items-center gap-2 font-semibold">
                <CheckCircle2 className="w-4 h-4" />
                {lastSimulation.message}
              </div>
              {lastSimulation.device && (
                <p className="mt-1 text-xs font-mono opacity-80">
                  {lastSimulation.device.id} | cleanup: <Countdown ts={lastSimulation.device.auto_cleanup_at} />
                </p>
              )}
            </div>
          )}
        </div>

        <div className="glass-card rounded-xl p-4">
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,320px)_minmax(0,420px)]">
            <label className="space-y-1.5">
              <span className="text-xs font-bold uppercase text-gray-500">MAC / Device ID</span>
              <div className="relative">
                <Cpu className="absolute left-3 top-2.5 h-4.5 w-4.5 text-gray-500" />
                <input
                  type="text"
                  value={macQuery}
                  onChange={(event) => {
                    setMacQuery(event.target.value)
                    setPage(1)
                  }}
                  placeholder="Masalan: esp32-... yoki MAC"
                  className="w-full pl-10 pr-4 py-2 rounded-lg glass-input focus:outline-none text-sm font-mono"
                />
              </div>
            </label>
            <label className="space-y-1.5">
              <span className="text-xs font-bold uppercase text-gray-500">Qo'shimcha qidiruv</span>
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4.5 w-4.5 text-gray-500" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(event) => {
                    setSearchQuery(event.target.value)
                    setPage(1)
                  }}
                  placeholder="Nom, serial, IP yoki turi bo'yicha..."
                  className="w-full pl-10 pr-4 py-2 rounded-lg glass-input focus:outline-none text-sm"
                />
              </div>
            </label>
          </div>
        </div>

        {isLoading ? (
          <TableSkeleton rows={6} />
        ) : isError ? (
          <ErrorBlock title="Test qurilmalar olinmadi" message={getApiErrorMessage(error)} onRetry={() => refetch()} />
        ) : devices.length > 0 ? (
          <div className={clsx('glass-card rounded-xl overflow-hidden shadow transition-opacity', isFetching && 'opacity-70')}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-300 dark:border-gray-800 bg-gray-100/50 dark:bg-gray-800/30">
                    <th className="text-left px-5 py-4 text-gray-600 dark:text-gray-400 font-semibold">Holat</th>
                    <th className="text-left px-5 py-4 text-gray-600 dark:text-gray-400 font-semibold">Qurilma</th>
                    <th className="text-left px-5 py-4 text-gray-600 dark:text-gray-400 font-semibold">Hisoblagich</th>
                    <th className="text-left px-5 py-4 text-gray-600 dark:text-gray-400 font-semibold">IP</th>
                    <th className="text-left px-5 py-4 text-gray-600 dark:text-gray-400 font-semibold">Oxirgi ko'rilgan</th>
                    <th className="text-left px-5 py-4 text-gray-600 dark:text-gray-400 font-semibold">Cleanup</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-300 dark:divide-gray-800">
                  {devices.map((device) => (
                    <tr key={device.id} className="hover:bg-gray-100/40 dark:hover:bg-gray-850/50">
                      <td className="px-5 py-4">
                        <span className="inline-flex items-center gap-2 font-semibold">
                          {device.online ? <Wifi className="w-4 h-4 text-green-500" /> : <WifiOff className="w-4 h-4 text-red-500" />}
                          {device.online ? 'Online' : 'Offline'}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <Link to={`/devices/${device.id}`} className="font-bold text-gray-950 dark:text-gray-100 hover:text-blue-500">
                          {device.name ?? device.id}
                        </Link>
                        <p className="text-xs text-gray-500 font-mono mt-0.5">{device.id}</p>
                      </td>
                      <td className="px-5 py-4">
                        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-blue-500/10 text-blue-500 text-xs font-bold border border-blue-500/20">
                          <Cpu className="w-3.5 h-3.5" />
                          {device.meter_serial ?? '-'}
                        </span>
                      </td>
                      <td className="px-5 py-4 font-mono text-gray-600 dark:text-gray-400">{device.ip ?? '-'}</td>
                      <td className="px-5 py-4 text-gray-700 dark:text-gray-300">{formatTime(device.last_seen)}</td>
                      <td className="px-5 py-4">
                        <span className="inline-flex items-center gap-1.5 text-xs font-bold text-orange-500">
                          <Timer className="w-3.5 h-3.5" />
                          <Countdown ts={device.auto_cleanup_at} />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="border-t border-gray-300 dark:border-gray-800 px-4">
              <Pagination
                page={page}
                totalPages={totalPages}
                total={total}
                pageSize={pageSize}
                onPageChange={setPage}
                onPageSizeChange={(size) => {
                  setPageSize(size)
                  setPage(1)
                }}
                pageSizeOptions={PAGE_SIZE_OPTIONS}
                isLoading={isFetching}
                className="py-3"
              />
            </div>
          </div>
        ) : (
          <EmptyBlock title="Test qurilma yo'q" message="Test token yoki 202032000525 seriali bilan reading kelganda shu yerda chiqadi." />
        )}
      </div>
    </RootLayout>
  )
}
