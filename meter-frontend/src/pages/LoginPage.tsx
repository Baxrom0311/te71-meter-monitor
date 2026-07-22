import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { BarChart3, Shield, Sparkles, Cpu, Lock, BrainCircuit } from 'lucide-react'
import clsx from 'clsx'
import apiClient from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { useTheme } from '@/contexts/ThemeContext'
import { LoginResponse } from '@/types/api'
import { translations } from '@/i18n/translations'
import { getApiErrorMessage } from '@/lib/errors'

const loginSchema = z.object({
  username: z.string().min(1, 'Foydalanuvchi nomi talab qilinadi'),
  password: z.string().min(1, 'Parol talab qilinadi'),
})

type LoginFormData = z.infer<typeof loginSchema>

const FEATURES = [
  { icon: Cpu,       label: 'ESP32 & RS-485 sensorlar' },
  { icon: Sparkles,  label: 'AI tahlil — DeepSeek & Gemini' },
  { icon: Shield,    label: 'Avtomatik ogohlantirishlar' },
  { icon: BarChart3, label: 'Real vaqt grafik va hisobotlar' },
]

export default function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const { isDark } = useTheme()
  const [serverError, setServerError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true)
    setServerError(null)
    try {
      const response = await apiClient.post<LoginResponse>('/api/auth/login', {
        username: data.username,
        password: data.password,
      })
      const { access_token, user } = response.data
      login(access_token, user)
      navigate('/dashboard', { replace: true })
    } catch (error: unknown) {
      setServerError(getApiErrorMessage(error) || translations.login.error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div
      className="relative min-h-screen flex items-center justify-center overflow-hidden px-4"
      style={{ backgroundColor: 'var(--bg-primary)' }}
    >
      {/* Animated background */}
      <div className="absolute inset-0 pointer-events-none dashboard-background">
        <div className="absolute inset-0 bg-dashboard-base" />
        <div className="absolute inset-0 bg-dashboard-grid animate-grid-pulse"
          style={{ color: isDark ? 'rgba(148,163,184,0.12)' : 'rgba(100,116,139,0.11)' }} />
        <div className="absolute inset-0 bg-dashboard-circuit animate-circuit-drift" />
        <div className="absolute inset-x-0 top-0 h-full bg-dashboard-scan animate-scanline" />
        <div className="absolute left-[28%] top-0 h-full w-px bg-signal-column animate-signal-column" />
        <div className="absolute left-[72%] top-0 h-full w-px bg-signal-column animate-signal-column-delayed" />
      </div>

      {/* Card */}
      <div className="relative z-10 w-full max-w-[900px] grid grid-cols-1 md:grid-cols-[1fr_1fr] rounded-3xl border border-gray-200 dark:border-gray-800 bg-white/50 dark:bg-gray-900/60 backdrop-blur-2xl shadow-2xl overflow-hidden">

        {/* ── LEFT SIDE ── */}
        <div className={clsx(
          'hidden md:flex flex-col justify-between px-10 py-10 border-r',
          isDark
            ? 'bg-gradient-to-br from-slate-900 via-blue-950/70 to-slate-900 border-gray-800'
            : 'bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 border-transparent',
        )}>
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className={clsx(
              'w-11 h-11 rounded-2xl flex items-center justify-center',
              isDark ? 'bg-blue-600' : 'bg-white/25',
            )}>
              <BrainCircuit className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-black text-white tracking-tight">AIMonitoring</span>
          </div>

          {/* Headline */}
          <div className="flex-1 flex flex-col justify-center gap-8 py-10">
            <h2 className="text-[28px] font-black text-white leading-tight">
              Elektr, suv va gazni{' '}
              <span className={isDark ? 'text-blue-400' : 'text-blue-200'}>AI</span>{' '}
              bilan nazorat qiling
            </h2>

            <ul className="space-y-4">
              {FEATURES.map(({ icon: Icon, label }) => (
                <li key={label} className="flex items-center gap-4">
                  <div className={clsx(
                    'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0',
                    isDark ? 'bg-white/8' : 'bg-white/20',
                  )}>
                    <Icon className="w-5 h-5 text-white" />
                  </div>
                  <span className={clsx(
                    'text-base font-semibold',
                    isDark ? 'text-gray-200' : 'text-white',
                  )}>{label}</span>
                </li>
              ))}
            </ul>
          </div>

          <p className={clsx('text-xs', isDark ? 'text-gray-600' : 'text-blue-300/60')}>
            © {new Date().getFullYear()} AIMonitoring
          </p>
        </div>

        {/* ── RIGHT SIDE ── */}
        <div className="flex flex-col justify-center px-8 py-12 md:px-12 bg-white/30 dark:bg-gray-900/50">

          {/* Mobile logo */}
          <div className="md:hidden flex items-center justify-center gap-3 mb-8">
            <BrainCircuit className="w-7 h-7 text-blue-500" />
            <span className="text-2xl font-black text-gray-950 dark:text-white">AIMonitoring</span>
          </div>

          {/* Title */}
          <div className="mb-8">
            <h3 className="text-3xl font-black text-gray-950 dark:text-white">Xush kelibsiz</h3>
            <p className="text-base text-gray-500 dark:text-gray-400 mt-1">Hisobingizga kiring</p>
          </div>

          {serverError && (
            <div className="mb-5 p-4 bg-red-500/10 border border-red-500/25 rounded-2xl text-sm text-red-400">
              {serverError}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {/* Username */}
            <div className="space-y-2">
              <label htmlFor="username" className="block text-sm font-bold text-gray-700 dark:text-gray-300">
                Foydalanuvchi nomi
              </label>
              <input
                {...register('username')}
                id="username"
                type="text"
                required
                autoComplete="username"
                placeholder="admin"
                className="w-full px-4 py-3.5 rounded-xl glass-input focus:outline-none text-base font-medium"
              />
              {errors.username && (
                <p className="text-xs text-red-400">{errors.username.message}</p>
              )}
            </div>

            {/* Password */}
            <div className="space-y-2">
              <label htmlFor="password" className="block text-sm font-bold text-gray-700 dark:text-gray-300">
                Parol
              </label>
              <div className="relative">
                <input
                  {...register('password')}
                  id="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className="w-full pl-4 pr-12 py-3.5 rounded-xl glass-input focus:outline-none text-base font-medium"
                />
                <Lock className="absolute right-4 top-4 h-5 w-5 text-gray-400" />
              </div>
              {errors.password && (
                <p className="text-xs text-red-400">{errors.password.message}</p>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3.5 mt-2 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 text-white text-base font-bold rounded-xl transition-all shadow-lg shadow-blue-500/20 flex items-center justify-center gap-2"
            >
              {isLoading && (
                <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent" />
              )}
              {isLoading ? 'Kirilmoqda...' : 'Kirish'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
