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
    <div className="glass-card glass-card-hover kpi-card rounded-2xl p-6 cursor-default animate-card-rise">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 tracking-wide">{title}</h3>
        <div className={`kpi-icon p-2.5 rounded-lg border ${colorClasses[color]}`}>{icon}</div>
      </div>

      <div>
        <p className={`text-3xl font-extrabold mb-1 tracking-tight ${valueColors[color]}`}>{value}</p>
        {subtitle && <p className="text-xs text-gray-600 dark:text-gray-500 font-medium">{subtitle}</p>}
      </div>
    </div>
  )
}
