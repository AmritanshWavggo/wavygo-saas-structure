import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar.jsx'
import Topbar from '../components/layout/Topbar.jsx'

function VendorLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 lg:flex">
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((current) => !current)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />
      <div className="min-w-0 flex-1">
        <Topbar onOpenMobileSidebar={() => setMobileOpen(true)} />
        <main className="mx-auto min-h-[calc(100vh-70px)] w-full max-w-[1680px] px-4 py-5 sm:px-6 sm:py-7 xl:px-9">
          <Outlet />
          <footer className="mx-auto mt-10 flex max-w-[1680px] flex-wrap items-center justify-between gap-2 border-t border-slate-200/80 pt-4 text-[10px] text-slate-400">
            <span>WavyGo Vendor workspace</span>
            <span>Interactive demo · Sample data only · Not connected to production services</span>
          </footer>
        </main>
      </div>
    </div>
  )
}

export default VendorLayout
