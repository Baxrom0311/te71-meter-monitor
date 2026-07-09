import { Columns3 } from 'lucide-react'
import type { TableColumn } from '@/lib/table'

interface TableColumnsMenuProps {
  columns: TableColumn[]
  isColumnVisible: (key: string) => boolean
  toggleColumn: (key: string) => void
}

export function TableColumnsMenu({ columns, isColumnVisible, toggleColumn }: TableColumnsMenuProps) {
  return (
    <details className="relative">
      <summary className="surface-button cursor-pointer select-none gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold marker:content-none">
        <Columns3 className="h-3.5 w-3.5" />
        Ustunlar
      </summary>
      <div className="absolute right-0 z-30 mt-2 w-56 rounded-xl border border-gray-300 bg-white/95 p-2 shadow-xl backdrop-blur dark:border-gray-800 dark:bg-gray-950/95">
        {columns.map((column) => (
          <label
            key={column.key}
            className="flex cursor-pointer items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-900"
          >
            <span>{column.label}</span>
            <input
              type="checkbox"
              checked={isColumnVisible(column.key)}
              onChange={() => toggleColumn(column.key)}
              className="h-4 w-4 accent-blue-600"
            />
          </label>
        ))}
      </div>
    </details>
  )
}
