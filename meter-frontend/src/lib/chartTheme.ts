export function chartTheme(isDark: boolean) {
  return {
    grid: isDark ? 'rgba(71, 85, 105, 0.34)' : 'rgba(148, 163, 184, 0.42)',
    axis: isDark ? '#94A3B8' : '#475569',
    label: isDark ? '#F8FAFC' : '#0F172A',
    tooltip: {
      backgroundColor: isDark ? 'rgba(2, 6, 23, 0.92)' : 'rgba(255, 255, 255, 0.96)',
      backdropFilter: 'blur(14px)',
      border: isDark ? '1px solid rgba(59, 130, 246, 0.24)' : '1px solid rgba(148, 163, 184, 0.45)',
      borderRadius: '0.875rem',
      color: isDark ? '#F8FAFC' : '#0F172A',
      boxShadow: isDark ? '0 18px 48px rgba(0, 0, 0, 0.38)' : '0 18px 48px rgba(15, 23, 42, 0.12)',
    },
    cursor: {
      stroke: isDark ? 'rgba(59, 130, 246, 0.22)' : 'rgba(37, 99, 235, 0.16)',
      strokeWidth: 1,
    },
  }
}
