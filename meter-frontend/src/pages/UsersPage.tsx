import { useState } from 'react'
import { Plus, X, Users, ShieldAlert, ToggleLeft, ToggleRight, Edit3, KeyRound } from 'lucide-react'
import { RootLayout } from '@/components/layout/RootLayout'
import { useUsers } from '@/hooks/queries'
import { translations } from '@/i18n/translations'
import { useAuth } from '@/contexts/AuthContext'
import { useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import { EmptyBlock, ErrorBlock } from '@/components/StateBlock'
import { getApiErrorMessage } from '@/lib/errors'
import { notify, notifyError, notifySuccess } from '@/lib/toast'
import { TableSkeleton } from '@/components/Skeleton'
import { User } from '@/types/api'

export default function UsersPage() {
  const { data: users, isLoading, isError, error: queryError, refetch } = useUsers()
  const { user: currentUser, isAdmin } = useAuth()
  const queryClient = useQueryClient()

  // Create Modal State
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('user')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Edit Modal State
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [editUserId, setEditUserId] = useState<number | null>(null)
  const [editRole, setEditRole] = useState('user')
  const [editPassword, setEditPassword] = useState('')
  const [editIsActive, setEditIsActive] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return
    setSubmitting(true)
    setError(null)

    try {
      await apiClient.post('/api/auth/users', {
        username,
        password,
        role,
      })
      queryClient.invalidateQueries({ queryKey: ['users'] })
      notifySuccess('Foydalanuvchi yaratildi', username)
      setIsModalOpen(false)
      // Reset form
      setUsername('')
      setPassword('')
      setRole('user')
    } catch (err: any) {
      console.error(err)
      setError(getApiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleToggleActive = async (targetUser: User) => {
    if (targetUser.id === currentUser?.id) {
      notify({ type: 'warning', title: 'Amal bajarilmadi', message: 'O‘zingizning faollik holatingizni o‘zgartira olmaysiz.' })
      return
    }

    try {
      await apiClient.put(`/api/auth/users/${targetUser.id}`, {
        is_active: !targetUser.is_active,
        role: targetUser.role,
      })
      queryClient.invalidateQueries({ queryKey: ['users'] })
      notifySuccess('Foydalanuvchi yangilandi')
    } catch (err) {
      console.error('Error toggling user status:', err)
      notifyError('Foydalanuvchi yangilanmadi', getApiErrorMessage(err))
    }
  }

  const openEditModal = (targetUser: User) => {
    setEditUserId(targetUser.id)
    setEditRole(targetUser.role)
    setEditIsActive(targetUser.is_active)
    setEditPassword('')
    setEditError(null)
    setIsEditModalOpen(true)
  }

  const handleEditUserSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editUserId) return
    setUpdating(true)
    setEditError(null)

    try {
      await apiClient.put(`/api/auth/users/${editUserId}`, {
        role: editRole,
        is_active: editIsActive,
        password: editPassword.trim() || null,
      })
      queryClient.invalidateQueries({ queryKey: ['users'] })
      notifySuccess('Foydalanuvchi tahrirlandi')
      setIsEditModalOpen(false)
    } catch (err: any) {
      console.error(err)
      setEditError(getApiErrorMessage(err))
    } finally {
      setUpdating(false)
    }
  }

  return (
    <RootLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Users className="w-8 h-8 text-blue-500" />
            <h1 className="text-3xl font-bold text-gray-100">{translations.users.title}</h1>
          </div>
          {isAdmin && (
            <button
              onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-700 text-white rounded-lg transition text-sm font-semibold shadow"
            >
              <Plus className="w-4 h-4" />
              {translations.users.createUser}
            </button>
          )}
        </div>

        {/* Users Table */}
        {isLoading ? (
          <TableSkeleton rows={6} />
        ) : isError ? (
          <ErrorBlock message={getApiErrorMessage(queryError)} onRetry={() => refetch()} />
        ) : users && users.length > 0 ? (
          <div className="glass-card rounded-xl overflow-hidden shadow-lg">
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-300 dark:border-gray-700 bg-gray-100/50 dark:bg-gray-800/30 text-gray-600 dark:text-gray-400">
                    <th className="text-left px-6 py-4 font-semibold">
                      {translations.users.username}
                    </th>
                    <th className="text-left px-6 py-4 font-semibold">
                      {translations.users.role}
                    </th>
                    <th className="text-left px-6 py-4 font-semibold">
                      Holat
                    </th>
                    {isAdmin && (
                      <th className="text-right px-6 py-4 font-semibold">
                        Amallar
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-300 dark:divide-gray-800 text-gray-750 dark:text-gray-300">
                  {users.map((u) => (
                    <tr
                      key={u.id}
                      className="border-b border-gray-300 dark:border-gray-700 hover:bg-gray-100/30 dark:hover:bg-gray-850/40 transition"
                    >
                      <td className="px-6 py-4 text-gray-950 dark:text-gray-100 font-bold flex items-center gap-2">
                        <span>{u.username}</span>
                        {u.id === currentUser?.id && (
                          <span className="text-[10px] px-1.5 py-0.5 bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 rounded-full font-semibold">Siz</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-gray-650 dark:text-gray-400 capitalize">
                        {u.role === 'admin' ? translations.users.admin : translations.users.user}
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${
                          u.is_active ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-red-500/10 text-red-550 dark:text-red-400'
                        }`}>
                          {u.is_active ? translations.users.active : translations.users.inactive}
                        </span>
                      </td>
                      {isAdmin && (
                        <td className="px-6 py-4 text-right flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleToggleActive(u)}
                            disabled={u.id === currentUser?.id}
                            title={u.is_active ? 'Faolsizlantirish' : 'Faollashtirish'}
                            className="focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            {u.is_active ? (
                              <ToggleRight className="w-6 h-6 text-green-400" />
                            ) : (
                              <ToggleLeft className="w-6 h-6 text-gray-500" />
                            )}
                          </button>
                          <button
                            onClick={() => openEditModal(u)}
                            title="Tahrirlash / Parolni yangilash"
                            className="p-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded border border-gray-750 transition shadow-sm"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="md:hidden mobile-card-list p-3">
              {users.map((u) => (
                <div key={u.id} className="mobile-data-card">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-bold text-gray-950 dark:text-gray-100 truncate">
                        {u.username}
                        {u.id === currentUser?.id && (
                          <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 rounded-full font-semibold">Siz</span>
                        )}
                      </p>
                      <p className="text-xs text-gray-500">ID: {u.id}</p>
                    </div>
                    <span className={`shrink-0 px-2 py-1 text-[11px] font-bold rounded-full ${
                      u.is_active ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-red-500/10 text-red-550 dark:text-red-400'
                    }`}>
                      {u.is_active ? translations.users.active : translations.users.inactive}
                    </span>
                  </div>
                  <div className="mobile-data-row">
                    <span className="mobile-data-label">{translations.users.role}</span>
                    <span className="mobile-data-value">{u.role === 'admin' ? translations.users.admin : translations.users.user}</span>
                  </div>
                  {isAdmin && (
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <button
                        onClick={() => handleToggleActive(u)}
                        disabled={u.id === currentUser?.id}
                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-gray-100 px-3 py-2 text-xs font-bold text-gray-700 hover:bg-gray-200 disabled:opacity-40 dark:bg-gray-850 dark:text-gray-200 dark:hover:bg-gray-750 transition"
                      >
                        {u.is_active ? <ToggleRight className="w-4 h-4 text-green-500" /> : <ToggleLeft className="w-4 h-4 text-gray-500" />}
                        Status
                      </button>
                      <button
                        onClick={() => openEditModal(u)}
                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700 transition"
                      >
                        <Edit3 className="w-4 h-4" />
                        Tahrirlash
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyBlock title={translations.common.noData} message="Hozircha foydalanuvchilar ro‘yxati bo‘sh." />
        )}

        {/* Create User Modal */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="glass-card rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl relative animate-modal-pop">
              <button
                onClick={() => setIsModalOpen(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-900 dark:hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>

              <h3 className="text-xl font-bold text-gray-905 dark:text-gray-100 flex items-center gap-2">
                <Plus className="w-5 h-5 text-blue-500" />
                {translations.users.createUser}
              </h3>

              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4 text-sm">
                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Foydalanuvchi nomi *</label>
                    <input
                      type="text"
                      required
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="Masalan: boxrom_admin"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Parol *</label>
                    <input
                      type="password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Parol kiriting"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Rol</label>
                    <select
                      value={role}
                      onChange={(e) => setRole(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                      <option value="user">Foydalanuvchi</option>
                      <option value="admin">Administrator</option>
                    </select>
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

        {/* Edit User Modal */}
        {isEditModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="glass-card rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl relative animate-modal-pop">
              <button
                onClick={() => setIsEditModalOpen(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-900 dark:hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>

              <h3 className="text-xl font-bold text-gray-905 dark:text-gray-100 flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-blue-500" />
                Foydalanuvchini Tahrirlash
              </h3>

              {editError && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                  {editError}
                </div>
              )}

              <form onSubmit={handleEditUserSubmit} className="space-y-4 text-sm">
                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Yangi Parol (Ixtiyoriy)</label>
                    <input
                      type="password"
                      value={editPassword}
                      onChange={(e) => setEditPassword(e.target.value)}
                      placeholder="O'zgartirmaslik uchun bo'sh qoldiring"
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Rol</label>
                    <select
                      value={editRole}
                      onChange={(e) => setEditRole(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium"
                    >
                      <option value="user">Foydalanuvchi</option>
                      <option value="admin">Administrator</option>
                    </select>
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Status</label>
                    <select
                      value={editIsActive ? 'true' : 'false'}
                      disabled={editUserId === currentUser?.id}
                      onChange={(e) => setEditIsActive(e.target.value === 'true')}
                      className="w-full px-3.5 py-2 rounded-lg glass-input focus:outline-none text-sm font-medium disabled:opacity-40"
                    >
                      <option value="true">Faol</option>
                      <option value="false">Faolsiz</option>
                    </select>
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
      </div>
    </RootLayout>
  )
}
