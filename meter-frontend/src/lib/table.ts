import { useMemo, useState } from 'react'

export interface TableColumn {
  key: string
  label: string
  defaultVisible?: boolean
}

function escapeCsv(value: unknown) {
  return `"${String(value ?? '').replace(/"/g, '""')}"`
}

export function downloadCsv(filename: string, headers: string[], rows: unknown[][]) {
  const csv = [headers.map(escapeCsv).join(','), ...rows.map((row) => row.map(escapeCsv).join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export function useColumnVisibility(columns: TableColumn[], storageKey: string) {
  const defaults = useMemo(
    () => Object.fromEntries(columns.map((column) => [column.key, column.defaultVisible !== false])),
    [columns],
  )
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(() => {
    try {
      const saved = window.localStorage.getItem(storageKey)
      return saved ? { ...defaults, ...JSON.parse(saved) } : defaults
    } catch {
      return defaults
    }
  })

  const toggleColumn = (key: string) => {
    setVisibleColumns((current) => {
      const next = { ...current, [key]: !current[key] }
      window.localStorage.setItem(storageKey, JSON.stringify(next))
      return next
    })
  }

  const isColumnVisible = (key: string) => visibleColumns[key] !== false

  return { visibleColumns, toggleColumn, isColumnVisible }
}
