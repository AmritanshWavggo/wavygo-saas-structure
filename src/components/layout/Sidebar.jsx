import {
  Activity,
  BarChart3,
  Bike,
  CalendarDays,
  ChevronLeft,
  ClipboardList,
  FileText,
  LayoutDashboard,
  Settings,
  Users,
  Wallet,
  X,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

const links = [
  { label: 'Dashboard', to: '/app/dashboard', icon: LayoutDashboard },
  { label: 'Vehicles', to: '/app/vehicles', icon: Bike },
  { label: 'Customers', to: '/app/customers', icon: Users },
  { label: 'Bookings', to: '/app/bookings', icon: CalendarDays },
  { label: 'Payments', to: '/app/payments', icon: Wallet },
  { label: 'Documents', to: '/app/documents', icon: FileText },
  { label: 'Maintenance', to: '/app/maintenance', icon: Activity },
  { label: 'Staff', to: '/app/staff', icon: Users },
  { label: 'Reports', to: '/app/reports', icon: BarChart3 },
  { label: 'Settings', to: '/app/settings', icon: Settings },
]

function Sidebar({ collapsed, onToggleCollapse, mobileOpen, onCloseMobile }) {
  return (
    <>
      {mobileOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={onCloseMobile}
          className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-[1px] lg:hidden"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[264px] shrink-0 flex-col border-r border-white/[0.08] bg-[#102C25] text-white shadow-2xl transition-[transform,width] duration-200 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 lg:shadow-none ${collapsed ? 'lg:w-[76px]' : 'lg:w-[264px]'} ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className={`flex h-[74px] items-center border-b border-white/[0.08] ${collapsed ? 'justify-center px-3' : 'justify-between px-4'}`}>
          <NavLink to="/app/dashboard" onClick={onCloseMobile} aria-label="WavyGo Vendor dashboard" className={`flex min-w-0 items-center ${collapsed ? 'justify-center' : ''}`}>
            <span className={`grid h-10 shrink-0 place-items-center rounded-xl bg-white ${collapsed ? 'w-12 px-0.5' : 'w-[168px] px-1.5'}`}>
              <img src="/images/logo.jpeg" alt="WavyGo" className={`object-contain ${collapsed ? 'h-auto w-11' : 'h-8 w-[156px]'}`} />
            </span>
          </NavLink>
          <button
            type="button"
            aria-label={mobileOpen ? 'Close navigation' : collapsed ? 'Expand navigation' : 'Collapse navigation'}
            onClick={mobileOpen ? onCloseMobile : onToggleCollapse}
            className={`hidden h-8 w-8 shrink-0 place-items-center rounded-lg text-emerald-100/70 transition hover:bg-white/10 hover:text-white lg:grid ${collapsed ? 'absolute -right-3 top-5 rounded-full border border-white/10 bg-[#173d33] shadow' : ''}`}
          >
            {mobileOpen ? <X size={17} /> : <ChevronLeft size={17} className={collapsed ? 'rotate-180' : ''} />}
          </button>
          <button type="button" aria-label="Close navigation" onClick={onCloseMobile} className="grid size-8 place-items-center rounded-lg text-emerald-100/70 hover:bg-white/10 lg:hidden">
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {!collapsed && (
          <div className="mx-3 mt-4 rounded-xl border border-white/[0.08] bg-white/[0.055] px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-100/50">Workspace</p>
            <p className="mt-1 truncate text-xs font-medium text-white/90">WavyGo Mobility</p>
          </div>
        )}
        {collapsed && (
          <div className="mx-auto mt-4 grid size-9 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.055] text-[11px] font-semibold text-emerald-100" title="WavyGo Mobility">
            WG
          </div>
        )}

        <nav aria-label="Main navigation" className="mt-5 flex-1 space-y-1 overflow-y-auto px-2.5 pb-4">
          {!collapsed && <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-100/45">Manage</p>}
          {links.map(({ label, to, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/app/dashboard'}
              onClick={onCloseMobile}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `group flex min-h-10 items-center gap-3 rounded-xl px-3 text-[13px] font-medium transition ${collapsed ? 'justify-center px-0' : ''} ${
                  isActive
                    ? 'bg-[#D8F4E7] text-[#123B2D] shadow-[0_4px_14px_rgba(0,0,0,0.12)]'
                    : 'text-emerald-50/70 hover:bg-white/[0.085] hover:text-white'
                }`
              }
            >
              <Icon size={18} strokeWidth={1.8} aria-hidden="true" className="shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className={`border-t border-white/[0.08] p-3 ${collapsed ? 'flex justify-center' : ''}`}>
          <div className={`flex items-center gap-3 rounded-xl bg-white/[0.055] p-2.5 ${collapsed ? 'justify-center bg-transparent p-0' : ''}`}>
            <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-[#D8F4E7] text-[11px] font-bold text-[#123B2D]">WM</span>
            {!collapsed && <div className="min-w-0"><p className="truncate text-xs font-medium text-white/90">WavyGo Vendor</p><p className="mt-0.5 text-[10px] text-emerald-100/50">Demo workspace</p></div>}
          </div>
        </div>
      </aside>
    </>
  )
}

export default Sidebar
