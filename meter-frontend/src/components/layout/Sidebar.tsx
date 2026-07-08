import { ReactNode, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Menu,
  X,
  LogOut,
  Zap,
  Bell,
  Moon,
  Sun,
  LayoutDashboard,
  Building2,
  Cpu,
  LineChart,
  Wrench,
  BookOpen,
  Bot,
  Users,
  ClipboardList,
  Settings,
  ChevronLeft,
  ChevronRight,
  Activity,
  ShieldCheck,
  PanelLeft,
  PanelTop,
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { useTheme } from '@/contexts/ThemeContext'
import { useAlerts } from '@/hooks/queries'
import { translations } from '@/i18n/translations'
import clsx from 'clsx'

interface NavItem {
  label: string
  path: string
  icon: ReactNode
  adminOnly?: boolean
  badge?: number
}

interface NavGroup {
  label: string
  items: NavItem[]
}

export type DesktopNavMode = 'sidebar' | 'topbar'

interface NavigationProps {
  desktopMode: DesktopNavMode
  onDesktopModeChange: (mode: DesktopNavMode) => void
}

function useNavigationGroups(openAlertCount: number, isAdmin: boolean): NavGroup[] {
  return useMemo(
    () => {
      const groups: NavGroup[] = [
      {
        label: 'Monitoring',
        items: [
          {
            label: translations.nav.dashboard,
            path: '/dashboard',
            icon: <LayoutDashboard className="w-5 h-5" />,
          },
          {
            label: translations.nav.buildings,
            path: '/buildings',
            icon: <Building2 className="w-5 h-5" />,
          },
          {
            label: translations.nav.devices,
            path: '/devices',
            icon: <Cpu className="w-5 h-5" />,
          },
          {
            label: translations.nav.analytics,
            path: '/analytics',
            icon: <LineChart className="w-5 h-5" />,
          },
        ],
      },
      {
        label: 'Operations',
        items: [
          {
            label: translations.nav.alerts,
            path: '/alerts',
            icon: <Bell className="w-5 h-5" />,
            badge: openAlertCount,
          },
          {
            label: translations.nav.firmware,
            path: '/firmware',
            icon: <Wrench className="w-5 h-5" />,
          },
          {
            label: translations.nav.chat,
            path: '/chat',
            icon: <Bot className="w-5 h-5" />,
          },
          {
            label: translations.nav.guide,
            path: '/guide',
            icon: <BookOpen className="w-5 h-5" />,
          },
        ],
      },
      {
        label: 'Admin',
        items: [
          {
            label: translations.nav.users,
            path: '/users',
            icon: <Users className="w-5 h-5" />,
            adminOnly: true,
          },
          {
            label: translations.nav.audit,
            path: '/audit',
            icon: <ClipboardList className="w-5 h-5" />,
            adminOnly: true,
          },
          {
            label: translations.nav.settings,
            path: '/settings',
            icon: <Settings className="w-5 h-5" />,
            adminOnly: true,
          },
        ],
      },
    ]
      return groups
        .map((group) => ({ ...group, items: group.items.filter((item) => !item.adminOnly || isAdmin) }))
        .filter((group) => group.items.length > 0)
    },
    [openAlertCount, isAdmin],
  )
}

export function Sidebar({ desktopMode, onDesktopModeChange }: NavigationProps) {
  const { user, logout, isAdmin } = useAuth()
  const { theme, toggleTheme, isDark } = useTheme()
  const { data: alerts } = useAlerts(false, 200)
  const [isOpen, setIsOpen] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(false)
  const location = useLocation()

  const openAlertCount = alerts?.length ?? 0

  const visibleGroups = useNavigationGroups(openAlertCount, isAdmin)

  const isActive = (path: string) => location.pathname === path || location.pathname.startsWith(path + '/')

  return (
    <>
      {/* ── Mobile Top Bar (h-16) ── */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-16 glass-sidebar flex items-center justify-between px-4 z-30 shadow-md">
        <div className="flex items-center gap-3">
          {/* Mobile Menu Toggle Button */}
          <button
            onClick={() => setIsOpen(!isOpen)}
            className={clsx(
              'p-2 rounded-lg border transition',
              isDark
                ? 'bg-gray-900 border-gray-700 text-gray-100 hover:bg-gray-800'
                : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-100',
            )}
          >
            {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          
          {/* Logo */}
          <div>
            <span className={clsx('font-bold text-lg leading-none block', isDark ? 'text-gray-100' : 'text-gray-900')}>
              TE71 Meter
            </span>
            <span className="text-[10px] font-semibold uppercase text-blue-500 tracking-widest">Live telemetry</span>
          </div>
        </div>

        {/* User initials on the right */}
        <div className="flex items-center gap-2">
          {openAlertCount > 0 && (
            <Link to="/alerts" className="relative p-2 rounded-lg bg-red-500/10 text-red-500 border border-red-500/20">
              <Bell className="w-4 h-4" />
              <span className="absolute -right-1 -top-1 min-w-4 h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold leading-4 text-center">
                {openAlertCount}
              </span>
            </Link>
          )}
          <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-500 font-bold text-xs ring-1 ring-blue-500/25">
            {user?.username?.[0]?.toUpperCase() || 'U'}
          </div>
        </div>
      </div>

      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-45 md:hidden backdrop-blur-sm transition-all duration-300"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar Drawer */}
      <aside
        className={clsx(
          'fixed left-0 top-0 h-screen w-72 glass-sidebar flex flex-col z-50 transition-[width,transform] duration-300 md:relative md:translate-x-0',
          isCollapsed ? 'md:w-20' : 'md:w-72',
          desktopMode === 'topbar' && 'md:hidden',
          isOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {/* Logo */}
        <div className={clsx('p-4', isCollapsed ? 'md:px-3' : 'md:p-5')} style={{ borderBottom: '1px solid var(--border-primary)' }}>
          <div className="flex items-center justify-between gap-3">
            <Link to="/dashboard" className={clsx('flex items-center gap-3 min-w-0 group', isCollapsed && 'md:justify-center md:w-full')}>
            <div className="relative flex items-center justify-center w-11 h-11 rounded-xl bg-blue-500 shadow-lg shadow-blue-500/20 overflow-hidden">
              <span className="absolute inset-0 bg-white/20 translate-x-[-120%] group-hover:translate-x-[120%] transition-transform duration-700" />
              <Zap className="w-6 h-6 text-white" />
            </div>
            {!isCollapsed && (
              <div className="min-w-0">
                <span className={clsx('text-xl font-bold leading-tight block truncate', isDark ? 'text-gray-100' : 'text-gray-900')}>
                  TE71 Meter
                </span>
                <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.22em] text-blue-500">
                  <Activity className="w-3 h-3" />
                  Live stack
                </span>
              </div>
            )}
            </Link>
            <button
              onClick={() => setIsCollapsed((value) => !value)}
              className={clsx(
                'hidden md:flex h-8 w-8 items-center justify-center rounded-lg border transition',
                isDark
                  ? 'border-gray-800 bg-gray-900/60 text-gray-400 hover:text-gray-100 hover:bg-gray-800'
                  : 'border-gray-200 bg-white/70 text-gray-500 hover:text-gray-900 hover:bg-gray-100',
                isCollapsed && 'md:absolute md:-right-4 md:top-6 md:z-10',
              )}
              title={isCollapsed ? 'Sidebarni ochish' : 'Sidebarni yigish'}
            >
              {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Navigation */}
        <nav className={clsx('flex-1 overflow-y-auto sidebar-scroll p-3 space-y-5', isCollapsed ? 'md:px-2' : 'md:p-4')}>
          {visibleGroups.map((group) => (
            <div key={group.label} className="space-y-1.5">
              {!isCollapsed && (
                <p className="px-3 text-[10px] font-bold uppercase tracking-[0.22em] text-gray-500 dark:text-gray-550">
                  {group.label}
                </p>
              )}
              <div className="space-y-1.5">
                {group.items.map((item, index) => {
                  const active = isActive(item.path)
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      title={isCollapsed ? item.label : undefined}
                      onClick={() => setIsOpen(false)}
                      style={{ animationDelay: `${index * 35}ms` }}
                      className={clsx(
                        'nav-item animate-nav-enter relative flex items-center rounded-xl border transition-all duration-200',
                        isCollapsed ? 'justify-center px-0 py-3' : 'justify-between px-3.5 py-3',
                        active
                          ? 'nav-item-active bg-blue-500/10 text-blue-500 border-blue-500/25 shadow-sm shadow-blue-500/10'
                          : isDark
                            ? 'border-transparent text-gray-400 hover:bg-white/5 hover:text-gray-100'
                            : 'border-transparent text-gray-500 hover:bg-gray-900/5 hover:text-gray-900',
                      )}
                    >
                      <div className={clsx('flex items-center min-w-0', isCollapsed ? 'justify-center' : 'gap-3')}>
                        <span className={clsx('nav-icon shrink-0 transition-transform duration-200', active && 'scale-110')}>
                          {item.icon}
                        </span>
                        {!isCollapsed && <span className="font-semibold truncate">{item.label}</span>}
                      </div>
                      {item.badge && item.badge > 0 && (
                        <span
                          className={clsx(
                            'bg-red-500 text-white text-xs font-bold rounded-full animate-badge-pulse shadow-lg shadow-red-500/20',
                            isCollapsed
                              ? 'absolute -right-0.5 -top-0.5 min-w-5 h-5 px-1 leading-5 text-center'
                              : 'ml-2 px-2 py-0.5',
                          )}
                        >
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* User Profile */}
        <div className={clsx('p-3 space-y-3', isCollapsed ? 'md:px-2' : 'md:p-4')} style={{ borderTop: '1px solid var(--border-primary)' }}>
          <div
            className={clsx(
              'rounded-2xl border bg-white/35 dark:bg-gray-950/25 border-gray-300/60 dark:border-gray-800/70',
              isCollapsed ? 'p-2 md:flex md:justify-center' : 'p-3',
            )}
          >
            <div className={clsx('flex items-center', isCollapsed ? 'justify-center' : 'gap-3')}>
            <div className="relative w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center text-blue-500 font-bold text-sm ring-1 ring-blue-500/25">
              <span className="absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full bg-emerald-500 ring-2 ring-gray-950" />
              {user?.username?.[0]?.toUpperCase() || 'U'}
            </div>
            {!isCollapsed && (
              <div className="flex-1 min-w-0">
              <p className={clsx('text-sm font-semibold truncate', isDark ? 'text-gray-100' : 'text-gray-900')}>
                {user?.username}
              </p>
              <p className={clsx('text-xs truncate flex items-center gap-1.5', isDark ? 'text-gray-400' : 'text-gray-500')}>
                {user?.role === 'admin' && <ShieldCheck className="w-3 h-3 text-blue-500" />}
                {user?.role === 'admin' ? translations.users.admin : translations.users.user}
              </p>
            </div>
            )}
            </div>
          </div>

          {/* Theme Toggle */}
          <div className={clsx('hidden md:grid gap-1 rounded-xl border border-gray-300/60 dark:border-gray-800/70 bg-white/30 dark:bg-gray-950/25 p-1', isCollapsed ? 'grid-cols-1' : 'grid-cols-2')}>
            <button
              onClick={() => onDesktopModeChange('sidebar')}
              className={clsx(
                'inline-flex items-center justify-center gap-2 rounded-lg px-2 py-2 text-xs font-bold transition',
                desktopMode === 'sidebar' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-950 dark:hover:text-gray-100',
              )}
              title="Sidebar"
            >
              <PanelLeft className="w-4 h-4" />
              {!isCollapsed && 'Sidebar'}
            </button>
            <button
              onClick={() => onDesktopModeChange('topbar')}
              className={clsx(
                'inline-flex items-center justify-center gap-2 rounded-lg px-2 py-2 text-xs font-bold transition',
                desktopMode === 'topbar' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-950 dark:hover:text-gray-100',
              )}
              title="Navbar"
            >
              <PanelTop className="w-4 h-4" />
              {!isCollapsed && 'Navbar'}
            </button>
          </div>

          <button
            onClick={toggleTheme}
            className={clsx(
              'w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl transition-all duration-300 text-sm font-medium group',
              isDark
                ? 'bg-gray-800/50 hover:bg-yellow-500/10 text-gray-300 hover:text-yellow-400'
                : 'bg-gray-100 hover:bg-blue-50 text-gray-600 hover:text-blue-600',
            )}
            title={isDark ? "Yorug' rejim" : 'Tungi rejim'}
          >
            <div className="relative w-5 h-5 overflow-hidden">
              <Sun
                className={clsx(
                  'w-5 h-5 absolute transition-all duration-500',
                  isDark ? 'translate-y-0 opacity-100 text-yellow-400' : '-translate-y-6 opacity-0',
                )}
              />
              <Moon
                className={clsx(
                  'w-5 h-5 absolute transition-all duration-500',
                  isDark ? 'translate-y-6 opacity-0' : 'translate-y-0 opacity-100 text-blue-500',
                )}
              />
            </div>
            {!isCollapsed && (isDark ? "Yorug' rejim" : 'Tungi rejim')}
          </button>

          <button
            onClick={() => {
              logout()
              setIsOpen(false)
            }}
            className={clsx(
              'w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl transition-all duration-200 text-sm font-medium',
              isDark
                ? 'bg-gray-800/50 hover:bg-red-500/15 text-gray-400 hover:text-red-400'
                : 'bg-gray-100 hover:bg-red-50 text-gray-500 hover:text-red-500',
            )}
          >
            <LogOut className="w-4 h-4" />
            {!isCollapsed && translations.common.logout}
          </button>
        </div>
      </aside>
    </>
  )
}

export function TopNavbar({ desktopMode, onDesktopModeChange }: NavigationProps) {
  const { user, logout, isAdmin } = useAuth()
  const { toggleTheme, isDark } = useTheme()
  const { data: alerts } = useAlerts(false, 200)
  const location = useLocation()
  const openAlertCount = alerts?.length ?? 0
  const visibleGroups = useNavigationGroups(openAlertCount, isAdmin)
  const navItems = visibleGroups.flatMap((group) => group.items)
  const isActive = (path: string) => location.pathname === path || location.pathname.startsWith(path + '/')

  return (
    <header className="hidden md:block fixed left-0 right-0 top-0 z-40 px-5 pt-4">
      <div className="mx-auto max-w-[1500px] glass-card rounded-2xl px-4 py-3 shadow-2xl">
        <div className="flex items-center gap-4">
          <Link to="/dashboard" className="flex items-center gap-3 shrink-0 group">
            <div className="relative flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl bg-blue-500 shadow-lg shadow-blue-500/20">
              <span className="absolute inset-0 bg-white/20 translate-x-[-120%] group-hover:translate-x-[120%] transition-transform duration-700" />
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-base font-extrabold text-gray-950 dark:text-gray-100 leading-none">TE71 Meter</p>
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-blue-500 mt-1">Live stack</p>
            </div>
          </Link>

          <nav className="flex-1 overflow-x-auto sidebar-scroll">
            <div className="flex items-center gap-1.5 min-w-max px-1">
              {navItems.map((item) => {
                const active = isActive(item.path)
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={clsx(
                      'nav-item relative inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-bold transition',
                      active
                        ? 'nav-item-active bg-blue-500/10 text-blue-500 border-blue-500/25'
                        : 'border-transparent text-gray-500 hover:text-gray-950 hover:bg-gray-900/5 dark:text-gray-400 dark:hover:text-gray-100 dark:hover:bg-white/5',
                    )}
                  >
                    {item.icon}
                    {item.label}
                    {item.badge && item.badge > 0 && (
                      <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-black text-white">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                )
              })}
            </div>
          </nav>

          <div className="flex items-center gap-2 shrink-0">
            <div className="grid grid-cols-2 rounded-xl border border-gray-300/60 dark:border-gray-800/70 bg-white/30 dark:bg-gray-950/25 p-1">
              <button
                onClick={() => onDesktopModeChange('sidebar')}
                className={clsx(
                  'inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-bold transition',
                  desktopMode === 'sidebar' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-950 dark:hover:text-gray-100',
                )}
              >
                <PanelLeft className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => onDesktopModeChange('topbar')}
                className={clsx(
                  'inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-bold transition',
                  desktopMode === 'topbar' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-950 dark:hover:text-gray-100',
                )}
              >
                <PanelTop className="w-3.5 h-3.5" />
              </button>
            </div>
            <button
              onClick={toggleTheme}
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-gray-300/60 dark:border-gray-800/70 bg-white/35 dark:bg-gray-950/25 text-gray-600 dark:text-gray-300 hover:text-blue-500 transition"
              title={isDark ? "Yorug' rejim" : 'Tungi rejim'}
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <div className="flex items-center gap-2 rounded-xl border border-gray-300/60 dark:border-gray-800/70 bg-white/35 dark:bg-gray-950/25 px-2.5 py-2">
              <div className="h-7 w-7 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-500 text-xs font-black ring-1 ring-blue-500/25">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </div>
              <span className="max-w-24 truncate text-xs font-bold text-gray-700 dark:text-gray-250">{user?.username}</span>
            </div>
            <button
              onClick={logout}
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-red-500/15 bg-red-500/10 text-red-500 hover:bg-red-500/15 transition"
              title={translations.common.logout}
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
