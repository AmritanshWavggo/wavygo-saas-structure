import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  Bell,
  Bike,
  Building2,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Command,
  LogOut,
  MapPin,
  Menu,
  Plus,
  Search,
  Settings,
  UserRound,
  Wallet,
  X,
} from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useDemoData } from '../../data/DemoDataContext.jsx'
import { authService } from '../../services/authService.js'
import { tenantService } from '../../services/tenantService.js'

const destinations = [
  { label: 'Dashboard', to: '/app/dashboard' },
  { label: 'Vehicles', to: '/app/vehicles' },
  { label: 'Customers', to: '/app/customers' },
  { label: 'Bookings', to: '/app/bookings' },
  { label: 'Payments', to: '/app/payments' },
  { label: 'Documents', to: '/app/documents' },
  { label: 'Maintenance', to: '/app/maintenance' },
  { label: 'Notifications', to: '/app/notifications' },
  { label: 'Staff', to: '/app/staff' },
  { label: 'Reports', to: '/app/reports' },
  { label: 'Settings', to: '/app/settings' },
]

const createActions = [
  { label: 'Add a vehicle', to: '/app/vehicles/new', icon: Building2 },
  { label: 'Create an offline booking', to: '/app/bookings/new', icon: Plus },
  { label: 'Add a customer', to: '/app/customers?new=1', icon: UserRound },
]

function formatTimeAgo(dateString) {
  if (!dateString) return 'Just now'
  const date = new Date(dateString)
  const seconds = Math.floor((new Date() - date) / 1000)
  if (seconds < 60) return 'Just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function Topbar({ onOpenMobileSidebar }) {
  const [menu, setMenu] = useState('')
  const [query, setQuery] = useState('')
  const [profile, setProfile] = useState(null)
  const headerRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    let active = true
    tenantService
      .getCurrentTenant()
      .then((data) => {
        if (active && data) setProfile(data)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  const storedBusiness = localStorage.getItem('wavygo-business-name') || ''
  const storedOwner = localStorage.getItem('wavygo-owner-name') || ''
  const userEmail = sessionStorage.getItem('wavygo-user-email') || ''
  const emailName = userEmail ? userEmail.split('@')[0] : ''

  const businessName =
    profile?.businessName ||
    profile?.business_name ||
    storedBusiness ||
    (emailName ? `${emailName}'s Fleet` : 'Fleet Workspace')
  const ownerName =
    profile?.ownerName ||
    profile?.owner_name ||
    storedOwner ||
    profile?.businessName ||
    storedBusiness ||
    emailName ||
    'Vendor'
  const partnerInitials = (businessName || ownerName || 'WG')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join('') || 'WG'

  const {
    notifications = [],
    unreadNotificationsCount = 0,
    markNotificationRead,
    markAllNotificationsRead,
  } = useDemoData()

  const matches = useMemo(
    () => destinations.filter((item) => item.label.toLowerCase().includes(query.toLowerCase())),
    [query],
  )

  useEffect(() => {
    function handlePointerDown(event) {
      if (!headerRef.current?.contains(event.target)) setMenu('')
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') setMenu('')
    }
    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  function handleLogout() {
    authService.logout()
    setMenu('')
    navigate('/login')
  }

  function getNotificationIcon(type) {
    switch (type) {
      case 'booking':
        return <CalendarDays size={14} className="text-blue-600" />
      case 'maintenance':
        return <Activity size={14} className="text-amber-600" />
      case 'payment':
        return <Wallet size={14} className="text-emerald-600" />
      case 'vehicle':
      default:
        return <Bike size={14} className="text-emerald-600" />
    }
  }

  return (
    <header
      ref={headerRef}
      className="sticky top-0 z-30 flex h-[74px] items-center gap-3 border-b border-slate-200/80 bg-white/95 px-4 backdrop-blur-md sm:px-6"
    >
      <button
        type="button"
        aria-label="Open navigation sidebar"
        onClick={onOpenMobileSidebar}
        className="grid size-10 place-items-center rounded-xl text-slate-600 hover:bg-slate-100 lg:hidden"
      >
        <Menu size={20} aria-hidden="true" />
      </button>

      {/* Global Quick Search */}
      <div className="relative max-w-xs flex-1 sm:max-w-sm">
        <label htmlFor="global-search" className="sr-only">
          Search destination pages
        </label>
        <div className="flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-500 focus-within:border-emerald-500 focus-within:bg-white focus-within:ring-2 focus-within:ring-emerald-100">
          <Search size={15} aria-hidden="true" className="shrink-0 text-slate-400" />
          <input
            id="global-search"
            type="search"
            placeholder="Search fleet, bookings, pages…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="h-full w-full bg-transparent text-slate-800 outline-none placeholder:text-slate-400"
          />
        </div>

        {query && (
          <div className="absolute left-0 top-12 z-50 w-full rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
            {matches.length ? (
              matches.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setQuery('')}
                  className="flex items-center justify-between rounded-xl px-3 py-2 text-xs font-medium text-slate-700 hover:bg-emerald-50 hover:text-emerald-950"
                >
                  {item.label}
                  <ChevronRight size={14} aria-hidden="true" className="text-slate-400" />
                </Link>
              ))
            ) : (
              <p className="px-3 py-2 text-xs text-slate-400">No destinations match “{query}”.</p>
            )}
          </div>
        )}
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
        <span className="hidden rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.08em] text-emerald-800 md:inline-flex">
          Live Hub
        </span>

        {/* Quick Create Menu */}
        <div className="relative">
          <button
            type="button"
            aria-expanded={menu === 'create'}
            onClick={() => setMenu(menu === 'create' ? '' : 'create')}
            className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-emerald-800 px-3 text-xs font-semibold text-white transition hover:bg-emerald-900 sm:px-3.5"
          >
            <Plus size={16} aria-hidden="true" />
            <span className="hidden sm:inline">Create</span>
            <ChevronDown size={13} aria-hidden="true" className="hidden sm:block" />
          </button>
          {menu === 'create' && (
            <div className="absolute right-0 top-12 z-50 w-60 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl">
              <p className="px-3 pb-1.5 pt-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                Quick actions
              </p>
              {createActions.map(({ label, to, icon: Icon }) => (
                <Link
                  key={to}
                  to={to}
                  onClick={() => setMenu('')}
                  className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-700 hover:bg-emerald-50 hover:text-emerald-900"
                >
                  <Icon size={16} aria-hidden="true" className="text-emerald-800" />
                  {label}
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Real-time Notifications Bell */}
        <div className="relative">
          <button
            type="button"
            aria-label="Notifications"
            aria-expanded={menu === 'notifications'}
            onClick={() => setMenu(menu === 'notifications' ? '' : 'notifications')}
            className="relative grid size-10 place-items-center rounded-xl text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            <Bell size={18} aria-hidden="true" />
            {unreadNotificationsCount > 0 && (
              <span className="absolute right-[4px] top-[4px] flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white shadow-sm">
                {unreadNotificationsCount > 9 ? '9+' : unreadNotificationsCount}
              </span>
            )}
          </button>

          {menu === 'notifications' && (
            <div className="absolute right-0 top-12 z-50 w-[min(360px,calc(100vw-24px))] rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold text-slate-900">Notifications</h2>
                  {unreadNotificationsCount > 0 && (
                    <span className="rounded-full bg-rose-100 px-1.5 py-0.5 text-[10px] font-semibold text-rose-700">
                      {unreadNotificationsCount} new
                    </span>
                  )}
                </div>
                {unreadNotificationsCount > 0 && (
                  <button
                    type="button"
                    onClick={() => markAllNotificationsRead && markAllNotificationsRead()}
                    className="text-[11px] font-medium text-emerald-800 hover:underline"
                  >
                    Mark all read
                  </button>
                )}
              </div>

              <div className="mt-2.5 max-h-[300px] divide-y divide-slate-100 overflow-y-auto">
                {notifications.slice(0, 6).map((item) => (
                  <div
                    key={item.id}
                    onClick={() => !item.is_read && markNotificationRead && markNotificationRead(item.id)}
                    className={`flex items-start gap-3 py-2.5 cursor-pointer rounded-lg px-1.5 transition ${
                      !item.is_read ? 'bg-emerald-50/50 hover:bg-emerald-50' : 'hover:bg-slate-50'
                    }`}
                  >
                    <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-slate-100">
                      {getNotificationIcon(item.type)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-1">
                        <p className={`text-xs ${!item.is_read ? 'font-semibold text-slate-900' : 'font-medium text-slate-700'}`}>
                          {item.title}
                        </p>
                        {!item.is_read && <span className="size-1.5 shrink-0 rounded-full bg-emerald-600" />}
                      </div>
                      <p className="mt-0.5 text-[11px] leading-4 text-slate-500 line-clamp-2">
                        {item.message}
                      </p>
                      <p className="mt-1 text-[9px] text-slate-400">
                        {formatTimeAgo(item.created_at)}
                      </p>
                    </div>
                  </div>
                ))}

                {notifications.length === 0 && (
                  <div className="py-8 text-center">
                    <Bell size={24} className="mx-auto text-slate-300 mb-2" />
                    <p className="text-xs font-medium text-slate-600">No notifications yet</p>
                    <p className="mt-1 text-[11px] text-slate-400">
                      Vehicle status changes and bookings will appear here.
                    </p>
                  </div>
                )}
              </div>

              <div className="mt-2.5 border-t border-slate-100 pt-2 text-center">
                <Link
                  to="/app/notifications"
                  onClick={() => setMenu('')}
                  className="text-xs font-semibold text-emerald-800 hover:text-emerald-950"
                >
                  View all activity & notifications →
                </Link>
              </div>
            </div>
          )}
        </div>

        <div className="mx-0.5 h-7 w-px bg-slate-200 sm:mx-1" />

        {/* Profile Menu */}
        <div className="relative">
          <button
            type="button"
            aria-label="Open profile menu"
            aria-expanded={menu === 'profile'}
            onClick={() => setMenu(menu === 'profile' ? '' : 'profile')}
            className="flex items-center gap-2 rounded-xl p-1 hover:bg-slate-50"
          >
            <span className="grid size-8 place-items-center rounded-xl bg-[#D8F4E7] text-[10px] font-bold text-[#123B2D]">
              {partnerInitials}
            </span>
            <span className="hidden text-left sm:block">
              <span className="block max-w-[130px] truncate text-[11px] font-semibold text-slate-800">{businessName}</span>
              <span className="block max-w-[130px] truncate text-[10px] text-emerald-600 font-medium">{ownerName}</span>
            </span>
            <ChevronDown size={13} aria-hidden="true" className="hidden text-slate-400 sm:block" />
          </button>
          {menu === 'profile' && (
            <div className="absolute right-0 top-12 z-50 w-56 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl">
              <div className="border-b border-slate-100 px-3 py-2.5">
                <p className="truncate text-xs font-semibold text-slate-800">{businessName}</p>
                <p className="mt-0.5 truncate text-[10px] text-emerald-700 font-medium">{ownerName}</p>
              </div>
              <Link
                to="/app/notifications"
                onClick={() => setMenu('')}
                className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-xs text-slate-600 hover:bg-slate-50"
              >
                <Bell size={15} />
                Notifications
              </Link>
              <Link
                to="/app/settings"
                onClick={() => setMenu('')}
                className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-xs text-slate-600 hover:bg-slate-50"
              >
                <Settings size={15} />
                Workspace settings
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-xs text-rose-600 hover:bg-rose-50"
              >
                <LogOut size={15} />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

export default Topbar
