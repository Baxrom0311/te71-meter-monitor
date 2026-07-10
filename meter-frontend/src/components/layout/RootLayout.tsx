import { ReactNode, useEffect, useState } from 'react'
import { Sidebar, TopNavbar, type DesktopNavMode } from './Sidebar'
import { useTheme } from '@/contexts/ThemeContext'

interface RootLayoutProps {
  children: ReactNode
}

export function RootLayout({ children }: RootLayoutProps) {
  const { isDark } = useTheme()
  const [desktopNavMode, setDesktopNavMode] = useState<DesktopNavMode>(() => {
    const saved = localStorage.getItem('meter-desktop-nav')
    return saved === 'topbar' ? 'topbar' : 'sidebar'
  })

  useEffect(() => {
    localStorage.setItem('meter-desktop-nav', desktopNavMode)
  }, [desktopNavMode])

  return (
    <div
      className="flex h-screen overflow-hidden relative"
      style={{ backgroundColor: 'var(--bg-primary)' }}
    >
      {/* ── Background Layer ── */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden dashboard-background">
        <div className="absolute inset-0 bg-dashboard-base" />

        <div
          className="absolute inset-0 bg-dashboard-grid animate-grid-pulse"
          style={{ color: isDark ? 'rgba(148,163,184,0.11)' : 'rgba(100,116,139,0.10)' }}
        />

        <div className="absolute inset-0 bg-dashboard-circuit animate-circuit-drift" />
        <div className="absolute inset-x-0 top-0 h-full bg-dashboard-scan animate-scanline" />
        <div className="absolute left-[18%] top-0 h-full w-px bg-signal-column animate-signal-column" />
        <div className="absolute left-[58%] top-0 h-full w-px bg-signal-column animate-signal-column-delayed" />

        <div
          className="absolute top-0 left-0 right-0 h-[260px] animate-aurora"
          style={{
            background: isDark
              ? 'linear-gradient(180deg, rgba(37,99,235,0.11) 0%, rgba(16,185,129,0.04) 45%, transparent 100%)'
              : 'linear-gradient(180deg, rgba(37,99,235,0.12) 0%, rgba(16,185,129,0.05) 45%, transparent 100%)',
          }}
        />
      </div>

      {/* Sidebar */}
      <Sidebar desktopMode={desktopNavMode} onDesktopModeChange={setDesktopNavMode} />
      {desktopNavMode === 'topbar' && (
        <TopNavbar desktopMode={desktopNavMode} onDesktopModeChange={setDesktopNavMode} />
      )}

      {/* Main Content */}
      <main className="flex-1 overflow-auto relative z-10">
        <div className={desktopNavMode === 'topbar' ? 'container-custom pt-24 pb-8 md:pt-28 md:pb-8 animate-fade-in' : 'container-custom pt-24 pb-8 md:py-8 animate-fade-in'}>
          {children}
        </div>
      </main>
    </div>
  )
}
