import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Zap, Shield, Sparkles, Cpu, Lock } from 'lucide-react'
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

export default function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const { isDark } = useTheme()
  const [serverError, setServerError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
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
      console.error('[v0] Login error:', error)
      setServerError(getApiErrorMessage(error) || translations.login.error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden px-4" style={{ backgroundColor: 'var(--bg-primary)' }}>
      <div className="absolute inset-0 pointer-events-none dashboard-background">
        <div className="absolute inset-0 bg-dashboard-base" />
        <div
          className="absolute inset-0 bg-dashboard-grid animate-grid-pulse"
          style={{ color: isDark ? 'rgba(148,163,184,0.12)' : 'rgba(100,116,139,0.11)' }}
        />
        <div className="absolute inset-0 bg-dashboard-circuit animate-circuit-drift" />
        <div className="absolute inset-0 utility-atmosphere" />
        <div className="absolute inset-x-0 top-0 h-full bg-dashboard-scan animate-scanline" />
        <div className="absolute left-[28%] top-0 h-full w-px bg-signal-column animate-signal-column" />
        <div className="absolute left-[72%] top-0 h-full w-px bg-signal-column animate-signal-column-delayed" />
      </div>

      {/* Main Grid Wrapper */}
      <div className="relative z-10 w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 rounded-2xl border border-gray-300 dark:border-gray-800 bg-white/40 dark:bg-gray-900/50 backdrop-blur-xl shadow-2xl overflow-hidden min-h-[500px]">
        {/* Left Side: Marketing / App Pitch */}
        <div
          className={clsx(
            "hidden md:flex flex-col justify-between p-8 border-r text-gray-200 transition-all duration-300",
            isDark
              ? "bg-gradient-to-br from-blue-950/90 to-slate-900/95 border-gray-850"
              : "bg-gradient-to-br from-blue-600 to-indigo-700 border-transparent text-white"
          )}
        >
          <div className="flex items-center gap-2">
            <div className={clsx("w-9 h-9 rounded-lg flex items-center justify-center shadow-lg", isDark ? "bg-blue-600 shadow-blue-500/20" : "bg-white/20 shadow-black/10")}>
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg tracking-wider text-white">TE71 Meter</span>
          </div>

          <div className="space-y-6 my-auto">
            <h2 className="text-3xl font-extrabold leading-tight text-white">
              Aqlli <span className={isDark ? "text-blue-400" : "text-blue-200"}>Monitoring</span> & <span className={isDark ? "text-purple-400" : "text-pink-300"}>AI</span> Tahlil Platformasi
            </h2>
            <p className={clsx("text-sm leading-relaxed", isDark ? "text-gray-400" : "text-blue-100")}>
              Binolar va datchiklardan kelayotgan elektr, suv va gaz sarflarini real-vaqt rejimida nazorat qiling, AI yordamida tahlil qiling va hisobotlar oling.
            </p>

            <div className="space-y-3 pt-2 text-xs">
              <div className="flex items-center gap-3">
                <Cpu className={clsx("w-4 h-4", isDark ? "text-blue-400" : "text-blue-200")} />
                <span className={isDark ? "" : "text-blue-50"}>ESP32 & RS-485 Modbus integratsiyasi</span>
              </div>
              <div className="flex items-center gap-3">
                <Sparkles className={clsx("w-4 h-4", isDark ? "text-purple-400" : "text-pink-300")} />
                <span className={isDark ? "" : "text-blue-50"}>DeepSeek va Gemini yordamida AI tahlil</span>
              </div>
              <div className="flex items-center gap-3">
                <Shield className={clsx("w-4 h-4", isDark ? "text-green-400" : "text-green-200")} />
                <span className={isDark ? "" : "text-blue-50"}>Avtomatik ogohlantirishlar tizimi</span>
              </div>
            </div>
          </div>

          <p className={clsx("text-xs", isDark ? "text-gray-500" : "text-blue-200")}>© {new Date().getFullYear()} TE71 Meter. Barcha huquqlar himoyalangan.</p>
        </div>

        <div className="flex flex-col justify-center p-8 md:p-12 bg-white/20 dark:bg-gray-900/40">
          <div className="mb-8">
            <div className="md:hidden flex items-center gap-2 mb-4 justify-center">
              <Zap className="w-6 h-6 text-blue-500" />
              <span className="font-bold text-xl text-gray-950 dark:text-white">TE71 Meter</span>
            </div>
            <h3 className="text-2xl font-bold text-gray-950 dark:text-gray-100">{translations.login.title}</h3>
            <p className="text-gray-500 dark:text-gray-450 text-sm mt-1">{translations.login.subtitle}</p>
          </div>

          {serverError && (
            <div className="mb-6 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
              {serverError}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 text-sm">
            <div>
              <label htmlFor="username" className="block text-gray-700 dark:text-gray-300 font-medium mb-2">
                {translations.login.username}
              </label>
              <input
                {...register('username')}
                id="username"
                type="text"
                required
                placeholder="Foydalanuvchi nomi"
                className="w-full px-4 py-2.5 rounded-lg glass-input focus:outline-none text-sm font-medium"
              />
              {errors.username && (
                <p className="mt-1 text-xs text-red-400">{errors.username.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="block text-gray-700 dark:text-gray-300 font-medium mb-2">
                {translations.login.password}
              </label>
              <div className="relative">
                <input
                  {...register('password')}
                  id="password"
                  type="password"
                  required
                  placeholder="••••••••"
                  className="w-full pl-4 pr-10 py-2.5 rounded-lg glass-input focus:outline-none text-sm font-medium"
                />
                <Lock className="absolute right-3.5 top-3.5 h-4 w-4 text-gray-400" />
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full px-4 py-2.5 mt-6 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold rounded-lg transition shadow-lg shadow-blue-500/10 flex items-center justify-center gap-2"
            >
              {isLoading && (
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              )}
              {isLoading ? translations.login.loading : translations.login.signIn}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
