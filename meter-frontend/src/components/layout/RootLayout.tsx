import { ReactNode, useEffect, useState } from 'react'
import { Sidebar, TopNavbar, type DesktopNavMode } from './Sidebar'
interface RootLayoutProps {
  children: ReactNode
}

export function RootLayout({ children }: RootLayoutProps) {
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
