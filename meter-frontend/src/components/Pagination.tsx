import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import clsx from 'clsx'

export interface PaginationProps {
  page: number        // 1-based
  totalPages: number
  total: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange?: (size: number) => void
  pageSizeOptions?: number[]
  className?: string
  isLoading?: boolean
}

function pageNumbers(page: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  if (page <= 4) return [1, 2, 3, 4, 5, '…', total]
  if (page >= total - 3) return [1, '…', total - 4, total - 3, total - 2, total - 1, total]
  return [1, '…', page - 1, page, page + 1, '…', total]
}

export function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
  className,
  isLoading,
}: PaginationProps) {
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)
  const pages = pageNumbers(page, totalPages)

  const btnBase =
    'inline-flex items-center justify-center rounded-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/60 disabled:cursor-not-allowed disabled:opacity-35'

  const iconBtn = clsx(
    btnBase,
    'w-7 h-7 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100',
    'hover:bg-gray-200/60 dark:hover:bg-gray-800/70',
  )

  return (
    <div
      className={clsx(
        'flex flex-col sm:flex-row items-center justify-between gap-3 select-none',
        className,
      )}
    >
      {/* ── Info ── */}
      <p className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap order-2 sm:order-1">
        {total === 0 ? (
          'Natija topilmadi'
        ) : (
          <>
            <span className="font-semibold text-gray-700 dark:text-gray-200">{from}–{to}</span>
            {' / '}
            <span className="font-semibold text-gray-700 dark:text-gray-200">{total}</span>
            {' ta'}
          </>
        )}
      </p>

      {/* ── Page buttons ── */}
      <nav
        className="flex items-center gap-0.5 order-1 sm:order-2"
        aria-label="Sahifalar"
      >
        <button
          onClick={() => onPageChange(1)}
          disabled={page === 1 || isLoading}
          className={iconBtn}
          title="Birinchi"
        >
          <ChevronsLeft className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page === 1 || isLoading}
          className={iconBtn}
          title="Oldingi"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>

        <div className="flex items-center gap-0.5 mx-1">
          {pages.map((n, i) =>
            n === '…' ? (
              <span
                key={`ellipsis-${i}`}
                className="w-7 h-7 inline-flex items-center justify-center text-xs text-gray-400 dark:text-gray-600"
              >
                …
              </span>
            ) : (
              <button
                key={n}
                onClick={() => onPageChange(n as number)}
                disabled={isLoading}
                aria-current={page === n ? 'page' : undefined}
                className={clsx(
                  btnBase,
                  'min-w-[28px] h-7 px-1.5 text-xs font-semibold',
                  page === n
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/30'
                    : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 hover:bg-gray-200/60 dark:hover:bg-gray-800/70',
                )}
              >
                {n}
              </button>
            ),
          )}
        </div>

        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page === totalPages || totalPages === 0 || isLoading}
          className={iconBtn}
          title="Keyingi"
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={() => onPageChange(totalPages)}
          disabled={page === totalPages || totalPages === 0 || isLoading}
          className={iconBtn}
          title="Oxirgi"
        >
          <ChevronsRight className="w-3.5 h-3.5" />
        </button>
      </nav>

      {/* ── Page size ── */}
      <div className="flex items-center gap-1.5 order-3">
        {onPageSizeChange && (
          <>
            <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
              Sahifada:
            </span>
            <select
              value={pageSize}
              onChange={(e) => {
                onPageSizeChange(Number(e.target.value))
                onPageChange(1)
              }}
              disabled={isLoading}
              className="px-2 py-1 rounded-lg text-xs font-semibold glass-input focus:outline-none"
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </>
        )}
      </div>
    </div>
  )
}
