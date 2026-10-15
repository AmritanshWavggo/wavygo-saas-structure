import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Bell,
  Building2,
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
  X,
} from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

const destinations = [
  { label: 'Dashboard', to: '/app/dashboard' },
  { label: 'Vehicles', to: '/app/vehicles' },
  { label: 'Customers', to: '/app/customers' },
  { label: 'Bookings', to: '/app/bookings' },
  { label: 'Payments', to: '/app/payments' },
  { label: 'Documents', to: '/app/documents' },
  { label: 'Maintenance', to: '/app/maintenance' },
  { label: 'Staff', to: '/app/staff' },
  { label: 'Reports', to: '/app/reports' },
  { label: 'Settings', to: '/app/settings' },
]

const createActions = [
  { label: 'Add a vehicle', to: '/app/vehicles/new', icon: Building2 },
  { label: 'Create an offline booking', to: '/app/bookings/new', icon: Plus },
  { label: 'Add a customer', to: '/app/customers?new=1', icon: UserRound },
]

function Topbar({ onOpenMobileSidebar }) {
  const [menu, setMenu] = useState('')
  const [query, setQuery] = useState('')
  const [vendor, setVendor] = useState('WavyGo Mobility')
  const [notificationsRead, setNotificationsRead] = useState(false)
  const headerRef = useRef(null)
  const navigate = useNavigate()
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

  function goToSearchResult(item) {
    navigate(item.to)
    setQuery('')
    setMenu('')
  }

  function handleSearchKey(event) {
    if (event.key === 'Escape') setMenu('')
    if (event.key === 'Enter' && matches[0]) goToSearchResult(matches[0])
    if (event.key === 'ArrowDown' && matches.length) {
      event.preventDefault()
      document.getElementById('jump-result-0')?.focus()
    }
  }

  return (
    <header ref={headerRef} className="sticky top-0 z-30 flex min-h-[70px] items-center gap-2 border-b border-slate-200/80 bg-white/95 px-3 backdrop-blur-xl sm:gap-3 sm:px-5 xl:px-7">
      <button
        type="button"
        aria-label="Open navigation menu"
        onClick={onOpenMobileSidebar}
        className="grid size-10 shrink-0 place-items-center rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 lg:hidden"
      >
        <Menu size={19} aria-hidden="true" />
      </button>

      <div className="hidden items-center gap-2.5 border-r border-slate-100 pr-4 sm:flex">
        <label className="flex items-center gap-1.5">
          <Building2 size={15} aria-hidden="true" className="shrink-0 text-emerald-800" />
          <select
            aria-label="Select business"
            value={vendor}
            onChange={(event) => setVendor(event.target.value)}
            className="max-w-[146px] cursor-pointer truncate bg-transparent text-xs font-semibold text-slate-800 outline-none"
          >
            <option>WavyGo Mobility</option>
            <option>Partner demo store</option>
          </select>
        </label>
        <span className="hidden items-center gap-1 text-[11px] text-slate-400 lg:inline-flex">
          <MapPin size={13} aria-hidden="true" />
          Ahmedabad
        </span>
      </div>

      <div className="relative min-w-0 max-w-[390px] flex-1">
        <label className="flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-slate-50/80 px-3 text-slate-400 transition focus-within:border-emerald-400 focus-within:bg-white focus-within:ring-2 focus-within:ring-emerald-100">
          <Search size={16} aria-hidden="true" className="shrink-0" />
          <input
            type="search"
            role="combobox"
            aria-label="Jump to a page"
            aria-expanded={menu === 'search'}
            aria-controls="jump-results"
            aria-autocomplete="list"
            placeholder="Jump to a page…"
            value={query}
            onFocus={() => setMenu('search')}
            onChange={(event) => { setQuery(event.target.value); setMenu('search') }}
            onKeyDown={handleSearchKey}
            className="min-w-0 flex-1 bg-transparent text-xs text-slate-800 outline-none placeholder:text-slate-400"
          />
          {query ? (
            <button type="button" aria-label="Clear search" onClick={() => setQuery('')} className="grid size-6 place-items-center text-slate-400 hover:text-slate-700"><X size={14} /></button>
          ) : (
            <span className="hidden items-center gap-0.5 rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] text-slate-400 md:inline-flex"><Command size={10} /> K</span>
          )}
        </label>
        {menu === 'search' && (
          <div id="jump-results" role="listbox" className="absolute left-0 right-0 top-12 z-50 overflow-hidden rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl">
            <p className="px-3 pb-1.5 pt-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Go to</p>
            {matches.length ? matches.slice(0, 6).map((item, index) => (
              <button key={item.to} id={`jump-result-${index}`} role="option" type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => goToSearchResult(item)} className="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs font-medium text-slate-700 hover:bg-emerald-50 hover:text-emerald-900">
                {item.label}<ChevronRight size={14} className="text-slate-400" />
              </button>
            )) : <p className="px-3 py-3 text-xs text-slate-500">No matching pages.</p>}
          </div>
        )}
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
        <span className="hidden rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.08em] text-amber-800 md:inline-flex">Demo</span>
        <div className="relative">
          <button type="button" aria-expanded={menu === 'create'} onClick={() => setMenu(menu === 'create' ? '' : 'create')} className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-emerald-800 px-3 text-xs font-semibold text-white transition hover:bg-emerald-900 sm:px-3.5">
            <Plus size={16} aria-hidden="true" /><span className="hidden sm:inline">Create</span><ChevronDown size={13} aria-hidden="true" className="hidden sm:block" />
          </button>
          {menu === 'create' && <div className="absolute right-0 top-12 z-50 w-60 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl"><p className="px-3 pb-1.5 pt-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Quick actions</p>{createActions.map(({ label, to, icon: Icon }) => <Link key={to} to={to} onClick={() => setMenu('')} className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-700 hover:bg-emerald-50 hover:text-emerald-900"><Icon size={16} aria-hidden="true" className="text-emerald-800" />{label}</Link>)}</div>}
        </div>
        <div className="relative">
          <button type="button" aria-label="Notifications" aria-expanded={menu === 'notifications'} onClick={() => setMenu(menu === 'notifications' ? '' : 'notifications')} className="relative grid size-10 place-items-center rounded-xl text-slate-500 hover:bg-slate-100 hover:text-slate-800">
            <Bell size={18} aria-hidden="true" />
            {!notificationsRead && <span className="absolute right-[9px] top-[8px] size-2 rounded-full border-2 border-white bg-rose-500" />}
          </button>
          {menu === 'notifications' && <div className="absolute right-0 top-12 z-50 w-[min(330px,calc(100vw-24px))] rounded-2xl border border-slate-200 bg-white p-4 shadow-xl"><div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-slate-900">Notifications</h2><button type="button" onClick={() => setNotificationsRead(true)} className="text-[11px] font-medium text-emerald-800 hover:underline">Mark read</button></div><div className="mt-3 space-y-2.5"><div className="flex gap-2.5 rounded-xl bg-amber-50 p-3"><span className="mt-1 size-2 shrink-0 rounded-full bg-amber-500" /><p className="text-xs leading-5 text-slate-700">One vehicle document is due for review.<span className="mt-0.5 block text-[10px] text-slate-400">Sample reminder · Today</span></p></div><div className="flex gap-2.5 rounded-xl bg-emerald-50 p-3"><span className="mt-1 size-2 shrink-0 rounded-full bg-emerald-500" /><p className="text-xs leading-5 text-slate-700">A new sample booking was added to the demo workspace.<span className="mt-0.5 block text-[10px] text-slate-400">Demo notification · Today</span></p></div></div><p className="mt-3 text-[10px] text-slate-400">Illustrative notifications only.</p></div>}
        </div>
        <div className="mx-0.5 h-7 w-px bg-slate-200 sm:mx-1" />
        <div className="relative">
          <button type="button" aria-label="Open profile menu" aria-expanded={menu === 'profile'} onClick={() => setMenu(menu === 'profile' ? '' : 'profile')} className="flex items-center gap-2 rounded-xl p-1 hover:bg-slate-50">
            <span className="grid size-8 place-items-center rounded-xl bg-[#D8F4E7] text-[10px] font-bold text-[#123B2D]">WM</span>
            <span className="hidden text-left sm:block"><span className="block text-[11px] font-semibold text-slate-800">WavyGo Vendor</span><span className="block text-[10px] text-slate-400">Demo workspace</span></span>
            <ChevronDown size={13} aria-hidden="true" className="hidden text-slate-400 sm:block" />
          </button>
          {menu === 'profile' && <div className="absolute right-0 top-12 z-50 w-56 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl"><div className="border-b border-slate-100 px-3 py-2.5"><p className="text-xs font-semibold text-slate-800">WavyGo Vendor</p><p className="mt-1 text-[10px] text-slate-400">Frontend-only demo session</p></div><Link to="/app/settings" onClick={() => setMenu('')} className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-xs text-slate-600 hover:bg-slate-50"><Settings size={15} />Workspace settings</Link><button type="button" onClick={() => { sessionStorage.removeItem('wavygo-demo-access'); setMenu(''); navigate('/login') }} className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-xs text-slate-600 hover:bg-rose-50 hover:text-rose-700"><LogOut size={15} />Exit demo workspace</button></div>}
        </div>
        <button type="button" aria-label="Help" onClick={() => setMenu(menu === 'help' ? '' : 'help')} className="hidden size-9 place-items-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700 xl:grid"><CircleHelp size={18} aria-hidden="true" /></button>
        {menu === 'help' && <div className="absolute right-4 top-[60px] z-50 max-w-[260px] rounded-xl border border-slate-200 bg-white p-3 text-xs leading-5 text-slate-600 shadow-xl">This is an interactive demo workspace. No live services or support integrations are connected.</div>}
      </div>
    </header>
  )
}

export default Topbar
