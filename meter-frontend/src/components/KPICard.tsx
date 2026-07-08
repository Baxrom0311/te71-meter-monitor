import { ReactNode } from 'react'

interface KPICardProps {
  title: string
  value: number | string
  icon: ReactNode
  subtitle?: string
  color?: 'primary' | 'green' | 'red' | 'yellow'
}

const colorClasses = {
  primary: 'bg-blue-500/10 text-blue-600 dark:text-blue-450 border-blue-500/20',
  green: 'bg-green-500/10 text-green-650 dark:text-green-400 border-green-500/20',
  red: 'bg-red-500/10 text-red-650 dark:text-red-400 border-red-500/20',
  yellow: 'bg-yellow-500/10 text-yellow-650 dark:text-yellow-400 border-yellow-500/20',
}

const valueColors = {
  primary: 'text-blue-650 dark:text-blue-400',
  green: 'text-green-650 dark:text-green-450',
  red: 'text-red-650 dark:text-red-400',
  yellow: 'text-yellow-655 dark:text-yellow-450',
}

export function KPICard({
  title,
  value,
  icon,
  subtitle,
  color = 'primary',
}: KPICardProps) {
  return (
    <div className="glass-card glass-card-hover kpi-card rounded-2xl p-4 sm:p-6 cursor-default animate-card-rise overflow-hidden relative">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-blue-500/35 to-transparent" />
      <div className="flex items-start justify-between gap-3 mb-4">
        <h3 className="text-xs sm:text-sm font-bold text-gray-500 dark:text-gray-400 tracking-wide leading-tight">{title}</h3>
        <div className={`kpi-icon p-2 sm:p-2.5 rounded-lg border shrink-0 ${colorClasses[color]}`}>{icon}</div>
      </div>

      <div>
        <p className={`text-2xl sm:text-3xl font-extrabold mb-1 tracking-tight ${valueColors[color]}`}>{value}</p>
        {subtitle && <p className="text-[11px] sm:text-xs text-gray-600 dark:text-gray-500 font-semibold leading-tight">{subtitle}</p>}
      </div>
    </div>
  )
}
