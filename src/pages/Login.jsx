import { useState } from 'react'
import {
  ArrowUpRight,
  Eye,
  EyeOff,
  KeyRound,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { Link } from 'react-router-dom'

const demoStatistics = [
  { label: 'Total vehicles', value: '248', detail: 'in your fleet' },
  { label: 'Active bookings', value: '36', detail: 'on the road today' },
  { label: 'Available vehicles', value: '72', detail: 'ready to ride' },
  { label: 'Monthly revenue', value: '₹4.8L', detail: 'this month' },
]

function BrandLogo({ className = '' }) {
  return (
    <span
      className={`inline-flex rounded-xl bg-white p-2 shadow-[0_8px_24px_rgba(8,24,22,0.12)] ${className}`}
    >
      <img
        src="/images/logo.jpeg"
        alt="WavyGo"
        width="162"
        height="40"
        className="h-10 w-[162px] max-w-full object-contain"
      />
    </span>
  )
}

function StatisticCard({ label, value, detail }) {
  return (
    <article className="min-w-0 rounded-2xl border border-white/15 bg-white/[0.09] p-4 shadow-[0_12px_36px_rgba(0,20,17,0.1)] backdrop-blur-xl sm:p-5">
      <p className="text-xs font-medium tracking-wide text-white/65 sm:text-[13px]">
        {label}
      </p>
      <p className="mt-3 text-[26px] font-semibold tracking-tight text-white sm:text-[30px]">
        {value}
      </p>
      <p className="mt-1 text-xs text-white/55">{detail}</p>
    </article>
  )
}

function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [keepSignedIn, setKeepSignedIn] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [notice, setNotice] = useState('')

  // Validate locally because this demo has no authentication endpoint to accept credentials.
  function validateForm() {
    const nextErrors = {}
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

    if (!email.trim()) {
      nextErrors.email = 'Enter your email address.'
    } else if (!emailPattern.test(email.trim())) {
      nextErrors.email = 'Enter a valid email address.'
    }

    if (!password) {
      nextErrors.password = 'Enter your password.'
    }

    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  function handleSubmit(event) {
    event.preventDefault()
    setNotice('')

    if (!validateForm()) return

    // Simulate the pending state for feedback without transmitting or retaining credentials.
    setIsSubmitting(true)
    window.setTimeout(() => {
      setIsSubmitting(false)
      setNotice(
        'Sign-in is not connected yet. Your credentials were not sent.',
      )
    }, 650)
  }

  function updateEmail(value) {
    setEmail(value)
    setNotice('')
    if (errors.email) setErrors((current) => ({ ...current, email: '' }))
  }

  function updatePassword(value) {
    setPassword(value)
    setNotice('')
    if (errors.password) {
      setErrors((current) => ({ ...current, password: '' }))
    }
  }

  return (
    <main className="min-h-screen bg-[#0B1020] text-white lg:grid lg:grid-cols-[58fr_42fr]">
      <section className="relative isolate flex min-h-[720px] flex-col overflow-hidden px-6 pb-7 pt-6 sm:px-10 sm:pb-9 sm:pt-8 lg:min-h-screen lg:px-12 lg:pb-10 lg:pt-9 xl:px-16">
        <img
          src="/images/fleet-hero.jpg"
          alt=""
          aria-hidden="true"
          className="absolute inset-0 -z-20 h-full w-full object-cover object-center"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 bg-[linear-gradient(115deg,rgba(4,30,27,0.85)_0%,rgba(5,47,43,0.75)_48%,rgba(8,33,39,0.8)_100%)]"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 bg-[linear-gradient(180deg,rgba(3,21,21,0.1)_0%,transparent_40%,rgba(3,20,22,0.45)_100%)]"
        />

        <header className="flex items-center justify-between gap-4">
          <BrandLogo />
          <span className="hidden items-center gap-2 rounded-full border border-white/20 bg-black/15 px-3.5 py-2 text-[11px] font-medium tracking-[0.12em] text-white/80 backdrop-blur-md sm:inline-flex">
            <span className="h-1.5 w-1.5 rounded-full bg-[#9BE7C4]" />
            VENDOR PORTAL
          </span>
        </header>

        <div className="my-auto max-w-[660px] py-14 sm:py-16 lg:py-20">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.08] px-3.5 py-2 text-xs font-medium text-white/85 backdrop-blur-md">
            <Sparkles size={14} aria-hidden="true" className="text-[#9BE7C4]" />
            Made for the people who keep us moving
          </div>
          <h1 className="max-w-[620px] text-[clamp(2.65rem,5.1vw,4.45rem)] font-semibold leading-[1.04] tracking-[-0.055em] text-white">
            Your fleet. Your business.{' '}
            <span className="text-[#A2E8CA]">One powerful platform.</span>
          </h1>
          <p className="mt-6 max-w-[480px] text-[15px] leading-7 text-white/72 sm:text-base sm:leading-8">
            Bring vehicles, bookings, customers and payments together. Spend
            less time keeping up and more time growing your rental business.
          </p>
          <a
            href="#sign-in"
            className="mt-8 inline-flex items-center gap-2 text-sm font-medium text-white transition-colors hover:text-[#A2E8CA] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#A2E8CA]"
          >
            Get back to business
            <ArrowUpRight size={16} aria-hidden="true" />
          </a>
        </div>

        <section aria-label="Illustrative demo statistics">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-white/75">
              A clearer view of your day
            </p>
            <p className="rounded-full border border-white/15 bg-black/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.13em] text-[#B8F0D7]">
              Illustrative demo data
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            {demoStatistics.map((statistic) => (
              <StatisticCard key={statistic.label} {...statistic} />
            ))}
          </div>
          <p className="mt-4 text-[11px] text-white/50">
            Sample figures for demonstration only — not live business data.
          </p>
        </section>
      </section>

      <section
        id="sign-in"
        className="flex min-h-[680px] flex-col justify-center bg-[#0B1020] px-6 py-12 sm:px-12 sm:py-16 lg:min-h-screen lg:px-10 xl:px-16"
      >
        <div className="mx-auto w-full max-w-[420px]">
          <BrandLogo className="mb-12 sm:mb-14" />

          <div className="mb-8">
            <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.06] text-[#A2E8CA]">
              <KeyRound size={19} strokeWidth={1.8} aria-hidden="true" />
            </div>
            <p className="mb-2 text-sm font-medium text-[#A2E8CA]">
              Your business, in good hands
            </p>
            <h2 className="text-[32px] font-semibold tracking-[-0.045em] text-white sm:text-[36px]">
              Welcome to WavyGo
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Sign in to manage your rental business.
            </p>
          </div>

          <form onSubmit={handleSubmit} noValidate>
            <div className="mb-5">
              <label
                htmlFor="email"
                className="mb-2 block text-[13px] font-medium text-slate-200"
              >
                Email address
              </label>
              <div
                className={`flex h-[50px] items-center gap-3 rounded-xl border bg-white/[0.035] px-3.5 transition-colors focus-within:border-[#71CFAB] ${
                  errors.email
                    ? 'border-rose-400/75'
                    : 'border-white/[0.12] hover:border-white/25'
                }`}
              >
                <Mail
                  size={17}
                  aria-hidden="true"
                  className="shrink-0 text-slate-500"
                />
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  autoCapitalize="none"
                  spellCheck="false"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(event) => updateEmail(event.target.value)}
                  aria-invalid={Boolean(errors.email)}
                  aria-describedby={errors.email ? 'email-error' : undefined}
                  className="h-full min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                />
              </div>
              {errors.email && (
                <p
                  id="email-error"
                  role="alert"
                  className="mt-2 text-xs text-rose-300"
                >
                  {errors.email}
                </p>
              )}
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between gap-3">
                <label
                  htmlFor="password"
                  className="text-[13px] font-medium text-slate-200"
                >
                  Password
                </label>
                <button
                  type="button"
                  onClick={() =>
                    setNotice(
                      'Password recovery is not connected yet. Contact your WavyGo administrator for help.',
                    )
                  }
                  className="text-xs font-medium text-[#A2E8CA] underline-offset-4 transition-colors hover:text-white hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#A2E8CA]"
                >
                  Forgot password?
                </button>
              </div>
              <div
                className={`flex h-[50px] items-center gap-3 rounded-xl border bg-white/[0.035] px-3.5 transition-colors focus-within:border-[#71CFAB] ${
                  errors.password
                    ? 'border-rose-400/75'
                    : 'border-white/[0.12] hover:border-white/25'
                }`}
              >
                <LockKeyhole
                  size={17}
                  aria-hidden="true"
                  className="shrink-0 text-slate-500"
                />
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(event) => updatePassword(event.target.value)}
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={
                    errors.password ? 'password-error' : undefined
                  }
                  className="h-full min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-white/[0.06] hover:text-slate-200 focus-visible:outline-2 focus-visible:outline-[#A2E8CA]"
                >
                  {showPassword ? (
                    <EyeOff size={17} aria-hidden="true" />
                  ) : (
                    <Eye size={17} aria-hidden="true" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p
                  id="password-error"
                  role="alert"
                  className="mt-2 text-xs text-rose-300"
                >
                  {errors.password}
                </p>
              )}
            </div>

            <label className="mt-5 flex w-fit cursor-pointer items-center gap-2.5 text-[13px] text-slate-400">
              <input
                type="checkbox"
                name="keepSignedIn"
                checked={keepSignedIn}
                onChange={(event) => setKeepSignedIn(event.target.checked)}
                className="h-4 w-4 cursor-pointer rounded border-white/20 bg-white/[0.06] accent-[#83DBB5] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#A2E8CA]"
              />
              Keep me signed in
            </label>

            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-7 inline-flex h-[52px] w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#88DFBB] via-[#77D9B2] to-[#9AE4BF] px-4 text-sm font-semibold text-[#0B2922] shadow-[0_10px_26px_rgba(100,207,164,0.16)] transition hover:brightness-105 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#A2E8CA] disabled:cursor-wait disabled:opacity-75"
            >
              {isSubmitting ? (
                <>
                  <span
                    aria-hidden="true"
                    className="h-4 w-4 animate-spin rounded-full border-2 border-[#0B2922]/25 border-t-[#0B2922]"
                  />
                  Signing in…
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          <div className="mt-5 text-center">
            <Link
              to="/app/dashboard"
              onClick={() => sessionStorage.setItem('wavygo-demo-access', 'enabled')}
              className="text-xs font-medium text-[#A2E8CA] underline-offset-4 transition-colors hover:text-white hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#A2E8CA]"
            >
              Explore the interactive demo workspace
            </Link>
            <p className="mt-1.5 text-[10px] text-slate-500">
              Sample data only · No authentication service is connected
            </p>
          </div>

          <div aria-live="polite" className="min-h-12 pt-3">
            {notice && (
              <p className="rounded-xl border border-[#A2E8CA]/20 bg-[#A2E8CA]/[0.07] px-3.5 py-3 text-xs leading-5 text-[#C2F3DC]">
                {notice}
              </p>
            )}
          </div>

          <div className="mt-7 flex items-center gap-3 border-t border-white/[0.08] pt-6">
            <ShieldCheck
              size={16}
              aria-hidden="true"
              className="shrink-0 text-slate-500"
            />
            <p className="text-xs text-slate-500">
              WavyGo Vendor · Interactive demo preview
            </p>
          </div>
        </div>
      </section>
    </main>
  )
}

export default LoginPage
