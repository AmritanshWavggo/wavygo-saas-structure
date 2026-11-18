import { useMemo, useState } from 'react'
import {
  Activity,
  Bell,
  Bike,
  CalendarDays,
  Check,
  CheckCheck,
  Clock,
  Filter,
  Trash2,
  Wallet,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useDemoData } from '../data/DemoDataContext.jsx'
import { Button, Card, PageHeader, StatusBadge } from '../components/ui/Workspace.jsx'

function formatFullTime(dateString) {
  if (!dateString) return 'Just now'
  const date = new Date(dateString)
  return date.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function NotificationsPage() {
  const {
    notifications = [],
    unreadNotificationsCount = 0,
    markNotificationRead,
    markAllNotificationsRead,
    deleteNotification,
    syncNotifications,
  } = useDemoData()

  const [activeTab, setActiveTab] = useState('All') // 'All' | 'Unread' | 'vehicle' | 'booking' | 'maintenance'

  const filtered = useMemo(() => {
    return notifications.filter((item) => {
      if (activeTab === 'Unread') return !item.is_read
      if (activeTab === 'All') return true
      return item.type === activeTab
    })
  }, [notifications, activeTab])

  function getNotificationIcon(type) {
    switch (type) {
      case 'booking':
        return <CalendarDays size={18} className="text-blue-600" />
      case 'maintenance':
        return <Activity size={18} className="text-amber-600" />
      case 'payment':
        return <Wallet size={18} className="text-emerald-600" />
      case 'vehicle':
      default:
        return <Bike size={18} className="text-emerald-600" />
    }
  }

  function getEntityLink(item) {
    if (item.type === 'vehicle') return '/app/vehicles'
    if (item.type === 'booking') return '/app/bookings'
    if (item.type === 'maintenance') return '/app/maintenance'
    if (item.type === 'payment') return '/app/payments'
    return null
  }

  return (
    <div>
      <PageHeader
        eyebrow="ACTIVITY LOG"
        title="Notifications"
        description="Real-time alerts for vehicle status changes, bookings, and fleet maintenance."
        action={
          <div className="flex flex-wrap gap-2">
            {unreadNotificationsCount > 0 && (
              <Button
                variant="secondary"
                onClick={() => markAllNotificationsRead && markAllNotificationsRead()}
              >
                <CheckCheck size={16} />
                Mark all as read
              </Button>
            )}
            <Button variant="secondary" onClick={() => syncNotifications && syncNotifications()}>
              Refresh
            </Button>
          </div>
        }
      />

      {/* Tabs */}
      <div className="mb-5 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        {[
          { label: 'All', value: 'All', count: notifications.length },
          { label: 'Unread', value: 'Unread', count: unreadNotificationsCount },
          { label: 'Vehicles', value: 'vehicle' },
          { label: 'Bookings', value: 'booking' },
          { label: 'Maintenance', value: 'maintenance' },
        ].map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => setActiveTab(tab.value)}
            className={`inline-flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition ${
              activeTab === tab.value
                ? 'bg-emerald-800 text-white shadow-sm'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            {tab.label}
            {typeof tab.count === 'number' && tab.count > 0 && (
              <span
                className={`rounded-full px-1.5 py-0.2 text-[10px] ${
                  activeTab === tab.value ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Notifications List Card */}
      <Card className="overflow-hidden">
        <div className="divide-y divide-slate-100">
          {filtered.map((item) => {
            const link = getEntityLink(item)
            return (
              <div
                key={item.id}
                className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 transition ${
                  !item.is_read ? 'bg-emerald-50/40' : 'hover:bg-slate-50/60'
                }`}
              >
                <div className="flex items-start gap-3 min-w-0 flex-1">
                  <div
                    className={`mt-0.5 grid size-10 shrink-0 place-items-center rounded-xl ${
                      !item.is_read ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {getNotificationIcon(item.type)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p
                        className={`text-sm ${
                          !item.is_read ? 'font-semibold text-slate-900' : 'font-medium text-slate-800'
                        }`}
                      >
                        {item.title}
                      </p>
                      {!item.is_read && (
                        <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white">
                          New
                        </span>
                      )}
                      <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 capitalize">
                        {item.type}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-600 leading-relaxed">{item.message}</p>
                    <div className="mt-2 flex items-center gap-3 text-[11px] text-slate-400">
                      <span className="inline-flex items-center gap-1">
                        <Clock size={12} />
                        {formatFullTime(item.created_at)}
                      </span>
                      {link && (
                        <Link
                          to={link}
                          className="font-medium text-emerald-800 hover:text-emerald-950 hover:underline"
                        >
                          View in {item.type} →
                        </Link>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                  {!item.is_read && (
                    <button
                      type="button"
                      title="Mark as read"
                      onClick={() => markNotificationRead && markNotificationRead(item.id)}
                      className="grid size-8 place-items-center rounded-lg border border-slate-200 text-slate-500 hover:bg-emerald-50 hover:text-emerald-800 hover:border-emerald-300 transition"
                    >
                      <Check size={15} />
                    </button>
                  )}
                  <button
                    type="button"
                    title="Delete notification"
                    onClick={() => deleteNotification && deleteNotification(item.id)}
                    className="grid size-8 place-items-center rounded-lg border border-slate-200 text-slate-400 hover:bg-rose-50 hover:text-rose-600 hover:border-rose-200 transition"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            )
          })}

          {filtered.length === 0 && (
            <div className="py-16 text-center">
              <Bell size={36} className="mx-auto text-slate-300 mb-3" />
              <p className="text-sm font-semibold text-slate-800">No notifications found</p>
              <p className="mt-1 text-xs text-slate-500">
                {activeTab === 'Unread'
                  ? 'All caught up! No unread notifications.'
                  : 'Activity updates and status changes will appear here.'}
              </p>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}

export default NotificationsPage

