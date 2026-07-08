import type { CSSProperties } from 'react'
import { cn } from '@/lib/utils'

interface SkeletonProps {
  className?: string
  style?: CSSProperties
}

export function Skeleton({ className, style }: SkeletonProps) {
  return <div className={cn('skeleton', className)} style={style} />
}

export function KPISkeletonGrid() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="glass-card rounded-xl p-4 sm:p-5 space-y-4">
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-9 rounded-lg" />
          </div>
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-3 w-28" />
        </div>
      ))}
    </div>
  )
}

export function ChartSkeleton({ titleWidth = 'w-40' }: { titleWidth?: string }) {
  return (
    <div className="glass-card chart-panel rounded-xl p-4 sm:p-6 shadow space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <Skeleton className={cn('h-5', titleWidth)} />
          <Skeleton className="h-3 w-52 max-w-full" />
        </div>
        <Skeleton className="h-7 w-16 rounded-full" />
      </div>
      <div className="h-[240px] sm:h-[300px] flex items-end gap-2">
        {Array.from({ length: 16 }).map((_, index) => (
          <Skeleton
            key={index}
            className="flex-1 rounded-t-lg"
            style={{ height: `${28 + ((index * 17) % 62)}%` } as CSSProperties}
          />
        ))}
      </div>
    </div>
  )
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="glass-card rounded-xl p-4 sm:p-6 space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="grid grid-cols-[2rem_1fr_5rem] sm:grid-cols-[3rem_1.5fr_1fr_1fr_1fr] gap-3 items-center">
          <Skeleton className="h-3 w-3 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-36 max-w-full" />
            <Skeleton className="h-3 w-24 sm:hidden" />
          </div>
          <Skeleton className="h-4 w-16" />
          <Skeleton className="hidden sm:block h-4 w-20" />
          <Skeleton className="hidden sm:block h-4 w-24" />
        </div>
      ))}
    </div>
  )
}
