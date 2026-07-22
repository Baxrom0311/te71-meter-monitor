import { useMemo, useState } from 'react'
import { Pagination } from '@/components/Pagination'

const FW_PAGE_SIZE = 6
const BATCH_PAGE_SIZE = 10
import { Ban, Cpu, Key, Layers, PlayCircle, RefreshCw, ShieldCheck, UploadCloud, X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { RootLayout } from '@/components/layout/RootLayout'
import { useAuth } from '@/contexts/AuthContext'
import { useBuildings, useDevices, useFirmwareList, useOtaBatches, useProvisioningTokens, qk } from '@/hooks/queries'
import { translations } from '@/i18n/translations'
import apiClient from '@/lib/api'
import { Device, Firmware, OtaBatch, ProvisioningToken } from '@/types/api'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlock'
import { getApiErrorMessage } from '@/lib/errors'
import { notifySuccess } from '@/lib/toast'

function formatTs(ts: number | null | undefined) {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('uz-UZ')
}

function statusClass(status: string) {
  if (status === 'completed') return 'bg-green-500/10 text-green-400 border-green-500/20'
  if (status === 'failed' || status === 'cancelled') return 'bg-red-500/10 text-red-400 border-red-500/20'
  if (status === 'in_progress') return 'bg-blue-500/10 text-blue-400 border-blue-500/20'
  return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
}

export default function FirmwarePage() {
  const { data: firmwareList = [], isLoading, isError, error: firmwareQueryError, refetch: refetchFirmware } = useFirmwareList()
  const { isAdmin } = useAuth()
  const { data: batches = [], isLoading: batchesLoading, isError: batchesError, error: batchesQueryError, refetch: refetchBatches } = useOtaBatches(isAdmin)
  const { data: devices = [] } = useDevices()
  const { data: provTokenData, refetch: refetchProvTokens } = useProvisioningTokens(false)
  const provTokens: ProvisioningToken[] = provTokenData?.tokens ?? []
  const { data: buildings = [] } = useBuildings()
  const queryClient = useQueryClient()

  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [version, setVersion] = useState('')
  const [hardwareVersion, setHardwareVersion] = useState('')
  const [utilityType, setUtilityType] = useState('electricity')
  const [firmwareMode, setFirmwareMode] = useState('auto')
  const [deviceRole, setDeviceRole] = useState('')
  const [sensorType, setSensorType] = useState('')
  const [converterType, setConverterType] = useState('')
  const [minVersion, setMinVersion] = useState('')
  const [rolloutPercentage, setRolloutPercentage] = useState(100)
  const [isStable, setIsStable] = useState(true)
  const [notes, setNotes] = useState('')
  const [file, setFile] = useState<File | null>(null)

  const [batchName, setBatchName] = useState('')
  const [selectedFirmwareId, setSelectedFirmwareId] = useState('')
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<string[]>([])
  const [devicesPerHour, setDevicesPerHour] = useState(100)
  const [scheduledAt, setScheduledAt] = useState('')

  const [fwPage, setFwPage] = useState(1)
  const [batchPage, setBatchPage] = useState(1)

  // Provisioning token state
  const [isProvTokenOpen, setIsProvTokenOpen] = useState(false)
  const [provUtility, setProvUtility] = useState('electricity')
  const [provBuildingId, setProvBuildingId] = useState<string>('')
  const [provTtlDays, setProvTtlDays] = useState(1)
  const [provCreating, setProvCreating] = useState(false)
  const [newTokenValue, setNewTokenValue] = useState('')
  const [provError, setProvError] = useState('')
  const [revokingId, setRevokingId] = useState<number | null>(null)
  const [showAllProvTokens, setShowAllProvTokens] = useState(false)

  const fwTotalPages = Math.max(1, Math.ceil(firmwareList.length / FW_PAGE_SIZE))
  const pagedFirmware = useMemo(
    () => firmwareList.slice((fwPage - 1) * FW_PAGE_SIZE, fwPage * FW_PAGE_SIZE),
    [firmwareList, fwPage],
  )
  const batchTotalPages = Math.max(1, Math.ceil(batches.length / BATCH_PAGE_SIZE))
  const pagedBatches = useMemo(
    () => batches.slice((batchPage - 1) * BATCH_PAGE_SIZE, batchPage * BATCH_PAGE_SIZE),
    [batches, batchPage],
  )

  const [submitting, setSubmitting] = useState(false)
  const [batchSubmitting, setBatchSubmitting] = useState(false)
  const [workingBatchId, setWorkingBatchId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [batchError, setBatchError] = useState<string | null>(null)

  const selectedFirmware = useMemo(
    () => firmwareList.find((fw: Firmware) => String(fw.id) === selectedFirmwareId),
    [firmwareList, selectedFirmwareId],
  )

  const compatibleDevices = useMemo(() => {
    if (!selectedFirmware?.utility_type) return devices
    return devices.filter((device: Device) => device.utility_type === selectedFirmware.utility_type)
  }, [devices, selectedFirmware])

  const resetUploadForm = () => {
    setVersion('')
    setHardwareVersion('')
    setUtilityType('electricity')
    setFirmwareMode('auto')
    setDeviceRole('')
    setSensorType('')
    setConverterType('')
    setMinVersion('')
    setRolloutPercentage(100)
    setIsStable(true)
    setNotes('')
    setFile(null)
  }

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!version.trim() || !file) return
    setSubmitting(true)
    setError(null)

    const formData = new FormData()
    formData.append('version', version.trim())
    formData.append('notes', notes)
    formData.append('hardware_version', hardwareVersion.trim())
    formData.append('firmware_mode', firmwareMode)
    formData.append('utility_type', utilityType)
    formData.append('device_role', deviceRole.trim())
    formData.append('sensor_type', sensorType.trim())
    formData.append('converter_type', converterType.trim())
    formData.append('is_stable', String(isStable))
    formData.append('min_version', minVersion.trim())
    formData.append('rollout_percentage', String(rolloutPercentage))
    formData.append('file', file)

    try {
      await apiClient.post('/api/ota/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      await queryClient.invalidateQueries({ queryKey: qk.firmware() })
      setIsUploadOpen(false)
      resetUploadForm()
      notifySuccess('Firmware yuklandi', `v${version.trim()} katalogga qo‘shildi.`)
    } catch (err: any) {
      setError(getApiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const toggleDevice = (deviceId: string) => {
    setSelectedDeviceIds((current) =>
      current.includes(deviceId) ? current.filter((id) => id !== deviceId) : [...current, deviceId],
    )
  }

  const selectAllCompatible = () => {
    setSelectedDeviceIds(compatibleDevices.map((device: Device) => device.id))
  }

  const clearSelectedDevices = () => {
    setSelectedDeviceIds([])
  }

  const handleCreateBatch = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!selectedFirmwareId || selectedDeviceIds.length === 0) return
    setBatchSubmitting(true)
    setBatchError(null)

    const scheduledTs = scheduledAt ? Math.floor(new Date(scheduledAt).getTime() / 1000) : null
    try {
      await apiClient.post('/api/ota/batches', {
        name: batchName.trim() || `OTA ${selectedFirmware?.version ?? selectedFirmwareId}`,
        firmware_id: Number(selectedFirmwareId),
        device_ids: selectedDeviceIds,
        devices_per_hour: devicesPerHour,
        scheduled_at: scheduledTs,
      })
      await queryClient.invalidateQueries({ queryKey: qk.otaBatches() })
      setBatchName('')
      setSelectedFirmwareId('')
      setSelectedDeviceIds([])
      setDevicesPerHour(100)
      setScheduledAt('')
      notifySuccess('OTA batch yaratildi')
    } catch (err: any) {
      setBatchError(getApiErrorMessage(err))
    } finally {
      setBatchSubmitting(false)
    }
  }

  const processBatch = async (batchId: number) => {
    setWorkingBatchId(batchId)
    try {
      await apiClient.post(`/api/ota/batches/${batchId}/process`)
      await queryClient.invalidateQueries({ queryKey: qk.otaBatches() })
      notifySuccess('OTA batch ishga tushdi')
    } finally {
      setWorkingBatchId(null)
    }
  }

  const cancelBatch = async (batchId: number) => {
    setWorkingBatchId(batchId)
    try {
      await apiClient.post(`/api/ota/batches/${batchId}/cancel`)
      await queryClient.invalidateQueries({ queryKey: qk.otaBatches() })
      notifySuccess('OTA batch bekor qilindi')
    } finally {
      setWorkingBatchId(null)
    }
  }

  const createProvToken = async () => {
    setProvCreating(true)
    setProvError('')
    setNewTokenValue('')
    try {
      const { data } = await apiClient.post('/api/devices/provisioning-tokens', {
        utility_type: provUtility || null,
        building_id: provBuildingId ? parseInt(provBuildingId) : null,
        ttl_sec: provTtlDays * 86400,
      })
      setNewTokenValue(data.provisioning_token)
      await refetchProvTokens()
      notifySuccess('Provisioning token yaratildi')
    } catch (e: unknown) {
      setProvError(getApiErrorMessage(e))
    } finally {
      setProvCreating(false)
    }
  }

  const revokeProvToken = async (tokenId: number) => {
    setRevokingId(tokenId)
    try {
      await apiClient.delete(`/api/devices/provisioning-tokens/${tokenId}`)
      await refetchProvTokens()
      notifySuccess('Token bekor qilindi')
    } catch (e: unknown) {
      setProvError(getApiErrorMessage(e))
    } finally {
      setRevokingId(null)
    }
  }

  return (
    <RootLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <Cpu className="w-8 h-8 text-blue-500" />
            <h1 className="text-3xl font-bold text-gray-100">{translations.firmware.title}</h1>
          </div>
          {isAdmin && (
            <button
              onClick={() => setIsUploadOpen(true)}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-700 text-white rounded-lg transition text-sm font-semibold"
            >
              <UploadCloud className="w-4 h-4" />
              Yangi firmware
            </button>
          )}
        </div>

        <section className="grid grid-cols-1 xl:grid-cols-[1.1fr_0.9fr] gap-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-100">Firmware katalogi</h2>
              <button
                onClick={() => queryClient.invalidateQueries({ queryKey: qk.firmware() })}
                className="p-2 text-gray-400 hover:text-gray-100 hover:bg-gray-800 rounded-lg transition"
                title="Yangilash"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            {isLoading ? (
              <LoadingBlock title="Firmware katalogi yuklanmoqda" />
            ) : isError ? (
              <ErrorBlock message={getApiErrorMessage(firmwareQueryError)} onRetry={() => refetchFirmware()} />
            ) : firmwareList.length > 0 ? (
              <div className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {pagedFirmware.map((fw: Firmware) => (
                  <div
                    key={fw.id}
                    className="glass-card glass-card-hover rounded-xl p-5 space-y-4 shadow"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="text-lg font-bold text-gray-100 flex flex-wrap items-center gap-2">
                          v{fw.version}
                          {fw.is_stable && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-500/10 text-green-400 text-xs font-semibold rounded-full border border-green-500/20">
                              <ShieldCheck className="w-3.5 h-3.5" />
                              Stable
                            </span>
                          )}
                        </h3>
                        <p className="text-xs text-gray-500 font-mono mt-1 break-all">{fw.filename}</p>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${
                          fw.active ? 'bg-blue-500/10 text-blue-400' : 'bg-gray-500/10 text-gray-400'
                        }`}
                      >
                        {fw.active ? 'Faol' : 'Faol emas'}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-xs border-t border-b border-gray-300 dark:border-gray-800 py-3 text-gray-700 dark:text-gray-300">
                      <div className="flex items-center gap-2">
                        <Layers className="w-4 h-4 text-gray-500" />
                        <span>
                          Turi:{' '}
                          <strong className="text-gray-900 dark:text-gray-100">
                            {translations.deviceTypes[fw.utility_type as keyof typeof translations.deviceTypes] ||
                              fw.utility_type ||
                              '-'}
                          </strong>
                        </span>
                      </div>
                      <div>Mode: <strong className="text-gray-900 dark:text-gray-100">{fw.firmware_mode}</strong></div>
                      <div>HW: <strong className="text-gray-900 dark:text-gray-100">{fw.hardware_version || '-'}</strong></div>
                      <div>Rollout: <strong className="text-gray-900 dark:text-gray-100">{fw.rollout_percentage ?? 100}%</strong></div>
                      <div>Min: <strong className="text-gray-900 dark:text-gray-100">{fw.min_version || '-'}</strong></div>
                      <div>Hajm: <strong className="text-gray-900 dark:text-gray-100">{fw.size ? `${(fw.size / 1024).toFixed(1)} KB` : '-'}</strong></div>
                    </div>

                    {fw.notes && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 bg-gray-100/40 dark:bg-gray-950/40 p-3 rounded-lg border border-gray-300 dark:border-gray-800">
                        <span className="font-semibold text-gray-800 dark:text-gray-300 block mb-1">Changelog:</span>
                        {fw.notes}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {firmwareList.length > FW_PAGE_SIZE && (
                <Pagination
                  page={fwPage}
                  totalPages={fwTotalPages}
                  total={firmwareList.length}
                  pageSize={FW_PAGE_SIZE}
                  onPageChange={setFwPage}
                />
              )}
              </div>
            ) : (
              <EmptyBlock title={translations.common.noData} message="Hozircha yuklangan firmware fayllari mavjud emas" />
            )}
          </div>

          <div className="glass-card rounded-xl p-5 h-fit shadow">
            <h2 className="text-lg font-semibold text-gray-100 mb-4">OTA batch yaratish</h2>
            {!isAdmin ? (
              <p className="text-sm text-gray-400">Batch boshqaruvi faqat admin uchun.</p>
            ) : (
              <form onSubmit={handleCreateBatch} className="space-y-4 text-sm">
                {batchError && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                    {batchError}
                  </div>
                )}

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Batch nomi</label>
                    <input
                      type="text"
                      value={batchName}
                      onChange={(event) => setBatchName(event.target.value)}
                      placeholder="Masalan: Suv node v2.0 rollout"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Firmware</label>
                    <select
                      required
                      value={selectedFirmwareId}
                      onChange={(event) => {
                        setSelectedFirmwareId(event.target.value)
                        setSelectedDeviceIds([])
                      }}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                    <option value="">Firmware tanlang</option>
                    {firmwareList.map((fw: Firmware) => (
                      <option key={fw.id} value={fw.id}>
                        v{fw.version} - {fw.utility_type || 'any'} / {fw.firmware_mode}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Soatiga qurilmalar soni</label>
                    <input
                      type="number"
                      min={1}
                      max={10000}
                      value={devicesPerHour}
                      onChange={(event) => setDevicesPerHour(Number(event.target.value))}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Boshlash vaqti</label>
                    <input
                      type="datetime-local"
                      value={scheduledAt}
                      onChange={(event) => setScheduledAt(event.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                    <p className="mt-1 text-[11px] leading-relaxed text-gray-500 dark:text-gray-450">
                      Bo‘sh qoldirilsa OTA batch darhol boshlanadi.
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Qurilmalar</label>
                    <div className="flex gap-2">
                      <button type="button" onClick={selectAllCompatible} className="text-xs text-blue-400 hover:text-blue-300">
                        Hammasi
                      </button>
                      <button type="button" onClick={clearSelectedDevices} className="text-xs text-gray-400 hover:text-gray-300">
                        Tozalash
                      </button>
                    </div>
                  </div>
                  <div className="max-h-56 overflow-y-auto border border-gray-800 rounded-lg divide-y divide-gray-800">
                    {compatibleDevices.length > 0 ? (
                      compatibleDevices.map((device: Device) => (
                        <label
                          key={device.id}
                          className="flex items-center justify-between gap-3 px-3 py-2 hover:bg-gray-800/50 cursor-pointer"
                        >
                          <span className="min-w-0">
                            <span className="block text-gray-100 truncate">{device.name || device.id}</span>
                            <span className="block text-xs text-gray-500">
                              {device.utility_type} / {device.fw_version || device.software_version || '-'}
                            </span>
                          </span>
                          <input
                            type="checkbox"
                            checked={selectedDeviceIds.includes(device.id)}
                            onChange={() => toggleDevice(device.id)}
                            className="w-4 h-4 rounded border-gray-700 bg-gray-950 text-blue-500 focus:ring-0 focus:ring-offset-0"
                          />
                        </label>
                      ))
                    ) : (
                      <p className="p-3 text-gray-500">Mos qurilma topilmadi.</p>
                    )}
                  </div>
                  <p className="text-xs text-gray-500">{selectedDeviceIds.length} ta qurilma tanlandi</p>
                </div>

                <button
                  type="submit"
                  disabled={batchSubmitting || !selectedFirmwareId || selectedDeviceIds.length === 0}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white rounded-lg transition font-medium"
                >
                  <PlayCircle className="w-4 h-4" />
                  {batchSubmitting ? 'Yaratilmoqda...' : 'Batch yaratish'}
                </button>
              </form>
            )}
          </div>
        </section>

        <section className="glass-card rounded-xl overflow-hidden shadow">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
            <h2 className="text-lg font-semibold text-gray-100">OTA batchlar</h2>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: qk.otaBatches() })}
              className="p-2 text-gray-400 hover:text-gray-100 hover:bg-gray-800 rounded-lg transition"
              title="Yangilash"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
          <div className="overflow-x-auto">
            {batchesLoading ? (
              <div className="p-5">
                <LoadingBlock title="OTA batchlar yuklanmoqda" />
              </div>
            ) : batchesError ? (
              <div className="p-5">
                <ErrorBlock message={getApiErrorMessage(batchesQueryError)} onRetry={() => refetchBatches()} />
              </div>
            ) : batches.length > 0 ? (
              <>
              <table className="w-full text-sm">
                <thead className="bg-gray-100/50 dark:bg-gray-800/30 border-b border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400">
                  <tr>
                    <th className="text-left px-5 py-3 font-semibold">Nomi</th>
                    <th className="text-left px-5 py-3 font-semibold">Holat</th>
                    <th className="text-left px-5 py-3 font-semibold">Progress</th>
                    <th className="text-left px-5 py-3 font-semibold">Qurilmalar</th>
                    <th className="text-left px-5 py-3 font-semibold">Boshlash vaqti</th>
                    <th className="text-right px-5 py-3 font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-300 dark:divide-gray-850 text-gray-750 dark:text-gray-300">
                  {pagedBatches.map((batch: OtaBatch) => (
                    <tr key={batch.id} className="hover:bg-gray-100/30 dark:hover:bg-gray-800/40 transition">
                      <td className="px-5 py-4">
                        <p className="font-bold text-gray-950 dark:text-gray-100">{batch.name}</p>
                        <p className="text-xs text-gray-500">Firmware #{batch.firmware_id}</p>
                      </td>
                      <td className="px-5 py-4">
                        <span className={`px-2 py-1 rounded-full text-xs border ${statusClass(batch.status)}`}>
                          {batch.status}
                        </span>
                      </td>
                      <td className="px-5 py-4 min-w-48">
                        <div className="flex items-center gap-3">
                          <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-850 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-500"
                              style={{ width: `${Math.min(batch.progress_percentage || 0, 100)}%` }}
                            />
                          </div>
                          <span className="text-gray-700 dark:text-gray-300 text-xs w-12 font-semibold">{batch.progress_percentage || 0}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-gray-700 dark:text-gray-300">
                        {batch.success_count} ok / {batch.failure_count} fail / {batch.pending_count} pending
                        <p className="text-xs text-gray-500">Jami: {batch.total_devices}</p>
                      </td>
                      <td className="px-5 py-4 text-gray-600 dark:text-gray-400">{formatTs(batch.scheduled_at)}</td>
                      <td className="px-5 py-4">
                        {isAdmin && (
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() => processBatch(batch.id)}
                              disabled={workingBatchId === batch.id || ['completed', 'cancelled'].includes(batch.status)}
                              className="p-2 text-blue-500 hover:text-blue-600 hover:bg-blue-500/10 disabled:opacity-40 rounded-lg transition"
                              title="Process"
                            >
                              <PlayCircle className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => cancelBatch(batch.id)}
                              disabled={workingBatchId === batch.id || ['completed', 'cancelled'].includes(batch.status)}
                              className="p-2 text-red-500 hover:text-red-650 hover:bg-red-500/10 disabled:opacity-40 rounded-lg transition"
                              title="Cancel"
                            >
                              <Ban className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {batches.length > BATCH_PAGE_SIZE && (
                <div className="border-t border-gray-300 dark:border-gray-800 px-4 py-3">
                  <Pagination
                    page={batchPage}
                    totalPages={batchTotalPages}
                    total={batches.length}
                    pageSize={BATCH_PAGE_SIZE}
                    onPageChange={setBatchPage}
                  />
                </div>
              )}
              </>
            ) : (
              <div className="p-5">
                <EmptyBlock title="OTA batchlar mavjud emas" message="Hozircha hech qanday rollout batch yaratilmagan." />
              </div>
            )}
          </div>
        </section>

        {/* ── Provisioning Tokens ─────────────────────────────────────────── */}
        {isAdmin && (
          <section className="glass-card rounded-xl p-5 shadow space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Key className="w-5 h-5 text-purple-400" />
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Provisioning Tokenlar</h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 font-medium">
                  {provTokens.filter(t => !t.revoked_at && !t.used_at && t.expires_at > Date.now() / 1000).length} faol
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowAllProvTokens(v => !v)}
                  className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 underline transition"
                >
                  {showAllProvTokens ? 'Faqat faollarni ko\'rsat' : 'Barchasini ko\'rsat'}
                </button>
                <button
                  onClick={() => { setIsProvTokenOpen(true); setNewTokenValue(''); setProvError(''); setProvBuildingId('') }}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-semibold transition"
                >
                  <Key className="w-3.5 h-3.5" />
                  Yangi token
                </button>
              </div>
            </div>

            {provError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">{provError}</div>
            )}

            {provTokens.length === 0 ? (
              <EmptyBlock title="Tokenlar yo'q" message="Hali hech qanday provisioning token yaratilmagan." />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
                <table className="w-full text-sm text-left">
                  <thead className="bg-gray-50 dark:bg-gray-900/60 text-xs text-gray-500 uppercase">
                    <tr>
                      <th className="px-4 py-3">ID</th>
                      <th className="px-4 py-3">Muddati</th>
                      <th className="px-4 py-3">Tur</th>
                      <th className="px-4 py-3">Holat</th>
                      <th className="px-4 py-3">Yaratuvchi</th>
                      <th className="px-4 py-3 text-right">Amal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                    {provTokens
                      .filter(t => showAllProvTokens || (!t.revoked_at && !t.used_at && t.expires_at > Date.now() / 1000))
                      .map(t => {
                        const now = Date.now() / 1000
                        const isUsed = !!t.used_at
                        const isRevoked = !!t.revoked_at
                        const isExpired = t.expires_at < now
                        const isActive = !isUsed && !isRevoked && !isExpired
                        return (
                          <tr key={t.id} className="hover:bg-gray-50 dark:hover:bg-gray-900/40 transition">
                            <td className="px-4 py-3 font-mono text-xs text-gray-600 dark:text-gray-400">#{t.id}</td>
                            <td className="px-4 py-3 text-gray-700 dark:text-gray-300 whitespace-nowrap">
                              {new Date(t.expires_at * 1000).toLocaleString('uz-UZ')}
                            </td>
                            <td className="px-4 py-3">
                              <span className="px-1.5 py-0.5 rounded text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                {t.utility_type ?? 'barcha'}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              {isRevoked ? (
                                <span className="px-2 py-0.5 rounded text-xs bg-gray-500/10 text-gray-400 border border-gray-500/20">Bekor qilingan</span>
                              ) : isUsed ? (
                                <span className="px-2 py-0.5 rounded text-xs bg-green-500/10 text-green-400 border border-green-500/20">
                                  Ishlatildi → {t.used_by_device_id}
                                </span>
                              ) : isExpired ? (
                                <span className="px-2 py-0.5 rounded text-xs bg-orange-500/10 text-orange-400 border border-orange-500/20">Muddati o'tgan</span>
                              ) : (
                                <span className="px-2 py-0.5 rounded text-xs bg-purple-500/10 text-purple-400 border border-purple-500/20 font-semibold">Faol</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-gray-600 dark:text-gray-400 text-xs">{t.created_by_username ?? '—'}</td>
                            <td className="px-4 py-3 text-right">
                              {isActive && (
                                <button
                                  onClick={() => revokeProvToken(t.id)}
                                  disabled={revokingId === t.id}
                                  className="p-1.5 text-red-500 hover:text-red-600 hover:bg-red-500/10 disabled:opacity-40 rounded-lg transition"
                                  title="Bekor qilish"
                                >
                                  <X className="w-4 h-4" />
                                </button>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {isProvTokenOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="glass-card rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl relative animate-modal-pop">
              <button
                onClick={() => setIsProvTokenOpen(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-900 dark:hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>
              <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2.5">
                <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  <Key className="w-5 h-5" />
                </div>
                Yangi Provisioning Token
              </h3>

              {newTokenValue ? (
                <div className="space-y-3">
                  <p className="text-sm text-gray-600 dark:text-gray-400">Token muvaffaqiyatli yaratildi. Uni ESP32 WiFiManager sahifasida kiriting:</p>
                  <div className="flex items-center gap-2 p-3 bg-gray-100 dark:bg-gray-900 rounded-lg border border-gray-300 dark:border-gray-700">
                    <code className="flex-1 font-mono text-sm text-purple-400 break-all">{newTokenValue}</code>
                    <button
                      onClick={() => { navigator.clipboard.writeText(newTokenValue); notifySuccess('Nusxalandi!') }}
                      className="shrink-0 px-3 py-1.5 text-xs bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition"
                    >
                      Nusxa
                    </button>
                  </div>
                  <p className="text-xs text-orange-400">⚠ Bu token faqat bir marta ko'rsatiladi — saqlang!</p>
                  <button
                    onClick={() => setIsProvTokenOpen(false)}
                    className="w-full py-2 bg-gray-200 dark:bg-gray-800 hover:bg-gray-300 dark:hover:bg-gray-700 rounded-lg text-sm font-medium transition"
                  >
                    Yopish
                  </button>
                </div>
              ) : (
                <div className="space-y-4 text-sm">
                  {provError && (
                    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">{provError}</div>
                  )}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Qurilma turi</label>
                    <select
                      value={provUtility}
                      onChange={e => setProvUtility(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                      <option value="electricity">⚡ Elektr</option>
                      <option value="water">💧 Suv</option>
                      <option value="gas">🔥 Gaz</option>
                      <option value="soil">🌱 Yerto'la</option>
                      <option value="sound">🔊 Ovoz</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Bino <span className="text-gray-400 font-normal">(ixtiyoriy)</span></label>
                    <select
                      value={provBuildingId}
                      onChange={e => setProvBuildingId(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                      <option value="">— Bino tanlanmagan —</option>
                      {buildings.map(b => (
                        <option key={b.id} value={b.id}>{b.name}</option>
                      ))}
                    </select>
                    {provBuildingId && (
                      <p className="mt-1 text-xs text-green-400">ESP32 ro'yxatdan o'tganda shu binoga avtomatik ulanadi</p>
                    )}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      Amal qilish muddati: <span className="text-purple-400 font-bold">{provTtlDays} kun</span>
                    </label>
                    <input
                      type="range" min={1} max={30} value={provTtlDays}
                      onChange={e => setProvTtlDays(Number(e.target.value))}
                      className="w-full accent-purple-500"
                    />
                    <div className="flex justify-between text-xs text-gray-400 mt-1">
                      <span>1 kun</span><span>30 kun</span>
                    </div>
                  </div>
                  <button
                    onClick={createProvToken}
                    disabled={provCreating}
                    className="w-full py-2.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-60 text-white rounded-lg font-semibold transition"
                  >
                    {provCreating ? 'Yaratilmoqda...' : 'Token yaratish'}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {isUploadOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="glass-card rounded-xl max-w-2xl w-full p-6 space-y-4 shadow-2xl relative max-h-[90vh] overflow-y-auto animate-modal-pop">
              <button
                onClick={() => setIsUploadOpen(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-900 dark:hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>

              <h3 className="text-xl font-bold text-gray-905 dark:text-gray-100 flex items-center gap-2.5">
                <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-500 border border-blue-500/20">
                  <UploadCloud className="w-5 h-5" />
                </div>
                Yangi firmware yuklash
              </h3>

              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                  {error}
                </div>
              )}

              <form onSubmit={handleUpload} className="space-y-4 text-sm">
                <div>
                  <label className="block text-gray-750 dark:text-gray-300 font-medium mb-1.5">Firmware fayli (.bin) *</label>
                  <input
                    type="file"
                    required
                    accept=".bin"
                    onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                    className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-gray-750 dark:text-gray-300 font-medium mb-1.5">Versiya *</label>
                    <input
                      type="text"
                      required
                      value={version}
                      onChange={(event) => setVersion(event.target.value)}
                      placeholder="Masalan: 3.3.0"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-750 dark:text-gray-300 font-medium mb-1.5">Min versiya</label>
                    <input
                      type="text"
                      value={minVersion}
                      onChange={(event) => setMinVersion(event.target.value)}
                      placeholder="Masalan: 1.0.0"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-750 dark:text-gray-300 font-medium mb-1.5">Rollout %</label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={rolloutPercentage}
                      onChange={(event) => setRolloutPercentage(Number(event.target.value))}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-gray-750 dark:text-gray-300 font-medium mb-1.5">Utility</label>
                    <select
                      value={utilityType}
                      onChange={(event) => setUtilityType(event.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                      <option value="electricity">Elektr</option>
                      <option value="water">Suv</option>
                      <option value="gas">Gaz</option>
                      <option value="soil">Yerto'la</option>
                      <option value="sound">Ovoz</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-gray-750 dark:text-gray-300 font-medium mb-1.5">Firmware mode</label>
                    <select
                      value={firmwareMode}
                      onChange={(event) => setFirmwareMode(event.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                      <option value="auto">Auto</option>
                      <option value="electricity">Elektr</option>
                      <option value="water">Suv</option>
                      <option value="gas">Gaz</option>
                      <option value="soil">Yerto'la</option>
                      <option value="sound">Ovoz</option>
                      <option value="lora_gateway">LoRa Gateway</option>
                      <option value="display">Display</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-gray-750 dark:text-gray-300 font-medium mb-1.5">Device role</label>
                    <input
                      type="text"
                      value={deviceRole}
                      onChange={(event) => setDeviceRole(event.target.value)}
                      placeholder="water_node"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-gray-750 dark:text-gray-300 font-medium mb-1.5">Hardware</label>
                    <input
                      type="text"
                      value={hardwareVersion}
                      onChange={(event) => setHardwareVersion(event.target.value)}
                      placeholder="HW-1.0"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-750 dark:text-gray-300 font-medium mb-1.5">Sensor</label>
                    <input
                      type="text"
                      value={sensorType}
                      onChange={(event) => setSensorType(event.target.value)}
                      placeholder="pressure_4_20ma"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-750 dark:text-gray-300 font-medium mb-1.5">Converter</label>
                    <input
                      type="text"
                      value={converterType}
                      onChange={(event) => setConverterType(event.target.value)}
                      placeholder="ADS1115"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                  </div>
                </div>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={isStable}
                    onChange={(event) => setIsStable(event.target.checked)}
                    className="w-4 h-4 rounded border-gray-300 dark:border-gray-700 bg-white/10 dark:bg-gray-950 text-blue-500 focus:ring-0 focus:ring-offset-0"
                  />
                  <span className="text-gray-750 dark:text-gray-350 font-medium select-none">Stable release</span>
                </label>

                <div>
                  <label className="block text-gray-750 dark:text-gray-300 font-medium mb-1.5">Changelog / Izohlar</label>
                  <textarea
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    placeholder="Qanday yangilanishlar kiritildi..."
                    rows={3}
                    className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium resize-none"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsUploadOpen(false)}
                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg transition"
                  >
                    {translations.common.cancel}
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white rounded-lg transition font-medium"
                  >
                    {submitting ? 'Yuklanmoqda...' : 'Yuklash'}
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
