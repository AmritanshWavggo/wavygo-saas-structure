import { useState } from 'react'
import { Search, X } from 'lucide-react'

export function PageHeader({
  eyebrow = 'VENDOR WORKSPACE',
  title,
  description,
  action,
  children,
}) {
  return (
    <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-700">
          {eyebrow}
        </p>
        <h1 className="text-[26px] font-semibold tracking-[-0.035em] text-slate-900 sm:text-[30px]">
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-500">
            {description}
          </p>
        )}
      </div>
      {action || children}
    </div>
  )
}

export function Card({ children, className = '', ...props }) {
  return (
    <section
      className={`rounded-2xl border border-slate-200/85 bg-white shadow-[0_2px_8px_rgba(15,23,42,0.025)] ${className}`}
      {...props}
    >
      {children}
    </section>
  )
}

export function MetricCard({ label, value, caption, icon: Icon, tone = 'green' }) {
  const tones = {
    green: 'bg-emerald-50 text-emerald-700',
    blue: 'bg-blue-50 text-blue-700',
    amber: 'bg-amber-50 text-amber-700',
    red: 'bg-rose-50 text-rose-700',
    navy: 'bg-slate-100 text-slate-700',
    violet: 'bg-violet-50 text-violet-700',
  }
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500">{label}</p>
          <p className="mt-2 text-[24px] font-semibold tracking-tight text-slate-900">
            {value}
          </p>
          {caption && <p className="mt-1 text-[11px] text-slate-400">{caption}</p>}
        </div>
        {Icon && (
          <span
            className={`grid size-10 shrink-0 place-items-center rounded-xl ${tones[tone] || tones.green}`}
          >
            <Icon size={18} aria-hidden="true" />
          </span>
        )}
      </div>
    </Card>
  )
}

const badgeStyles = {
  Active: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15',
  Available: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15',
  Online: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15',
  Paid: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15',
  Verified: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15',
  Completed: 'bg-slate-100 text-slate-600 ring-slate-500/10',
  Offline: 'bg-slate-100 text-slate-600 ring-slate-500/10',
  Inactive: 'bg-slate-100 text-slate-600 ring-slate-500/10',
  'In review': 'bg-amber-50 text-amber-700 ring-amber-600/15',
  Review: 'bg-amber-50 text-amber-700 ring-amber-600/15',
  'Expires soon': 'bg-amber-50 text-amber-700 ring-amber-600/15',
  Pending: 'bg-amber-50 text-amber-700 ring-amber-600/15',
  Partial: 'bg-amber-50 text-amber-700 ring-amber-600/15',
  Ongoing: 'bg-blue-50 text-blue-700 ring-blue-600/15',
  Rented: 'bg-blue-50 text-blue-700 ring-blue-600/15',
  Maintenance: 'bg-violet-50 text-violet-700 ring-violet-600/15',
  Cancelled: 'bg-rose-50 text-rose-700 ring-rose-600/15',
}

export function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ring-inset ${badgeStyles[status] || 'bg-slate-100 text-slate-600 ring-slate-500/10'}`}
    >
      {status}
    </span>
  )
}

export function SearchField({ value, onChange, placeholder = 'Search…' }) {
  return (
    <label className="flex h-10 min-w-0 items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3 text-slate-400 transition focus-within:border-emerald-400 focus-within:ring-2 focus-within:ring-emerald-100">
      <Search size={16} aria-hidden="true" />
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="min-w-0 flex-1 bg-transparent text-sm text-slate-800 outline-none placeholder:text-slate-400"
      />
    </label>
  )
}

export function Button({
  children,
  variant = 'primary',
  className = '',
  ...props
}) {
  const variants = {
    primary:
      'border border-emerald-800 bg-emerald-800 text-white hover:bg-emerald-900 focus-visible:outline-emerald-700',
    secondary:
      'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 focus-visible:outline-slate-400',
    quiet:
      'border border-transparent bg-transparent text-slate-600 hover:bg-slate-100 focus-visible:outline-slate-400',
    danger:
      'border border-rose-200 bg-white text-rose-700 hover:bg-rose-50 focus-visible:outline-rose-500',
  }
  return (
    <button
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant] || variants.primary} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

export function FilterSelect({ label, value, options, onChange }) {
  return (
    <label className="flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3">
      {label && <span className="text-xs text-slate-400">{label}</span>}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-w-20 bg-transparent text-sm text-slate-700 outline-none"
      >
        {options.map((option) => (
          <option key={option.value || option} value={option.value || option}>
            {option.label || option}
          </option>
        ))}
      </select>
    </label>
  )
}

export function DataTable({ columns, rows, emptyTitle = 'Nothing to show yet', emptyText = 'Try adjusting the search or filters.' }) {
  if (rows.length === 0) {
    return (
      <div className="px-6 py-14 text-center">
        <p className="font-medium text-slate-800">{emptyTitle}</p>
        <p className="mt-1 text-sm text-slate-500">{emptyText}</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-y border-slate-100 bg-slate-50/80 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`px-4 py-3 first:pl-5 last:pr-5 ${column.className || ''}`}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row, index) => (
            <tr key={row.id || row.key || index} className="transition-colors hover:bg-slate-50/70">
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-4 py-3.5 text-slate-600 first:pl-5 last:pr-5 ${column.cellClassName || ''}`}
                >
                  {column.render ? column.render(row) : row[column.key] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Tabs({ items, value, onChange }) {
  return (
    <div className="flex max-w-full gap-1 overflow-x-auto border-b border-slate-200 px-4 sm:px-5">
      {items.map((item) => {
        const label = typeof item === 'string' ? item : item.label
        const key = typeof item === 'string' ? item : item.value
        const count = typeof item === 'string' ? null : item.count
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            aria-current={value === key ? 'page' : undefined}
            className={`-mb-px inline-flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-3 text-xs font-medium transition ${value === key ? 'border-emerald-700 text-emerald-800' : 'border-transparent text-slate-500 hover:text-slate-800'}`}
          >
            {label}
            {count != null && <span className="text-[10px] text-slate-400">{count}</span>}
          </button>
        )
      })}
    </div>
  )
}

export function Modal({ title, children, onClose, footer }) {
  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-[2px]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="max-h-[calc(100vh-2rem)] w-full max-w-lg overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h2 id="modal-title" className="font-semibold text-slate-900">{title}</h2>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X size={17} aria-hidden="true" />
          </button>
        </header>
        <div className="p-5">{children}</div>
        {footer && <footer className="border-t border-slate-100 bg-slate-50/70 px-5 py-4">{footer}</footer>}
      </section>
    </div>
  )
}

export function Field({ label, error, className = '', ...props }) {
  const id = props.id || props.name
  return (
    <label htmlFor={id} className={`block ${className}`}>
      <span className="mb-1.5 block text-xs font-medium text-slate-600">
        {label}{props.required && <span className="ml-0.5 text-rose-500">*</span>}
      </span>
      {props.as === 'textarea' ? (
        <textarea
          {...props}
          id={id}
          className="min-h-24 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
        />
      ) : (
        <input
          {...props}
          id={id}
          className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
        />
      )}
      {error && <span className="mt-1.5 block text-xs text-rose-600">{error}</span>}
    </label>
  )
}

export function BarChart({ data, label = 'Chart', height = 220, color = '#059669' }) {
  const max = Math.max(...data.map((point) => point.value), 1)
  const points = data.map((point, index) => ({
    ...point,
    x: 42 + (index * 626) / Math.max(data.length - 1, 1),
    y: 170 - (point.value / max) * 130,
  }))
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
  const area = `${path} L ${points[points.length - 1]?.x || 668} 178 L ${points[0]?.x || 42} 178 Z`

  return (
    <div className="w-full">
      <svg
        viewBox="0 0 710 220"
        role="img"
        aria-label={label}
        className="h-auto w-full overflow-visible"
        style={{ maxHeight: height }}
      >
        {[45, 88, 131, 174].map((y) => (
          <line key={y} x1="34" x2="692" y1={y} y2={y} stroke="#e8edf1" strokeDasharray="3 5" />
        ))}
        <defs>
          <linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity=".18" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#chart-fill)" />
        <path d={path} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((point) => (
          <g key={point.label}>
            <circle cx={point.x} cy={point.y} r="4" fill="white" stroke={color} strokeWidth="2" />
            <text x={point.x} y="207" fill="#94a3b8" fontSize="10" textAnchor="middle">{point.label}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}

export function ComparisonChart({ data, label = 'Revenue compared with expenses' }) {
  const maximum = Math.max(...data.flatMap((point) => [point.revenue, point.expenses]), 1)
  const getCoordinates = (key) =>
    data.map((point, index) => ({
      ...point,
      x: 42 + (index * 626) / Math.max(data.length - 1, 1),
      y: 166 - (point[key] / maximum) * 126,
    }))
  const revenuePoints = getCoordinates('revenue')
  const expensePoints = getCoordinates('expenses')
  const pathFor = (points) =>
    points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')

  return (
    <div>
      <div className="mb-3 flex gap-4 text-[11px] font-medium text-slate-500">
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-emerald-600" />Revenue</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-amber-500" />Expenses</span>
      </div>
      <svg viewBox="0 0 710 210" role="img" aria-label={label} className="h-auto w-full">
        {[40, 82, 124, 166].map((y) => (
          <line key={y} x1="34" x2="692" y1={y} y2={y} stroke="#e8edf1" strokeDasharray="3 5" />
        ))}
        <path d={pathFor(revenuePoints)} fill="none" stroke="#059669" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        <path d={pathFor(expensePoints)} fill="none" stroke="#f59e0b" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {data.map((point, index) => (
          <g key={point.label}>
            <circle cx={revenuePoints[index].x} cy={revenuePoints[index].y} r="3.5" fill="white" stroke="#059669" strokeWidth="2" />
            <circle cx={expensePoints[index].x} cy={expensePoints[index].y} r="3.5" fill="white" stroke="#f59e0b" strokeWidth="2" />
            <text x={revenuePoints[index].x} y="198" fill="#94a3b8" fontSize="10" textAnchor="middle">{point.label}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}
