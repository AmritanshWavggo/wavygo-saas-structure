import { useEffect, useState } from 'react'
import {
  ArrowUpRight,
  Building2,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  LockKeyhole,
  Mail,
  Phone,
  ShieldCheck,
  Sparkles,
  User,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { authService } from '../services/authService.js'

const fleetHighlights = [
  { label: 'Active Fleet', value: '248+', detail: 'vehicles ready' },
  { label: 'On The Road', value: '36', detail: 'active today' },
  { label: 'Fast Verification', value: 'Instant', detail: 'automated KYC' },
  { label: 'Payouts', value: 'Daily', detail: 'direct to bank' },
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
  const navigate = useNavigate()
  const [mode, setMode] = useState('signin') // 'signin' | 'signup'

  // Common fields
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [keepSignedIn, setKeepSignedIn] = useState(false)

  // Signup fields
  const [businessName, setBusinessName] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState('')

  // State
  const [otpSent, setOtpSent] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)
  const [isSendingOtp, setIsSendingOtp] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errors, setErrors] = useState({})
  const [notice, setNotice] = useState('')
  const [successNotice, setSuccessNotice] = useState('')

  // Cooldown countdown timer for OTP resend
  useEffect(() => {
    if (resendCooldown <= 0) return
    const timer = setInterval(() => {
      setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [resendCooldown])

  function validateEmail(val) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim())
  }

  // Handle Send OTP
  async function handleSendOtp() {
    setNotice('')
    setSuccessNotice('')
    const nextErrors = {}

    if (!email.trim()) {
      nextErrors.email = 'Enter your email address.'
    } else if (!validateEmail(email)) {
      nextErrors.email = 'Enter a valid email address.'
    }

    if (!businessName.trim()) {
      nextErrors.businessName = 'Business name is required.'
    }

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }

    setErrors({})
    setIsSendingOtp(true)

    try {
      await authService.sendSignupOtp({
        email,
        name: ownerName || businessName,
      })
      setOtpSent(true)
      setResendCooldown(30)
      setSuccessNotice(`Verification code sent to ${email}. Check your inbox.`)
    } catch (err) {
      setNotice(err.message || 'Failed to send verification code. Please try again.')
    } finally {
      setIsSendingOtp(false)
    }
  }

  // Handle Submit Form
  async function handleSubmit(event) {
    event.preventDefault()
    setNotice('')
    setSuccessNotice('')

    const nextErrors = {}
    if (!email.trim()) {
      nextErrors.email = 'Enter your email address.'
    } else if (!validateEmail(email)) {
      nextErrors.email = 'Enter a valid email address.'
    }

    if (!password) {
      nextErrors.password = 'Enter your password.'
    } else if (mode === 'signup' && password.length < 8) {
      nextErrors.password = 'Password must be at least 8 characters long.'
    }

    if (mode === 'signup') {
      if (!businessName.trim()) {
        nextErrors.businessName = 'Business name is required.'
      }
      if (!otp.trim()) {
        nextErrors.otp = 'Enter the 6-digit verification code.'
      } else if (otp.trim().length !== 6) {
        nextErrors.otp = 'Verification code must be 6 digits.'
      }
    }

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }

    setIsSubmitting(true)

    try {
      if (mode === 'signin') {
        await authService.login({ email, password })
        navigate('/app/dashboard')
      } else {
        await authService.signup({
          email,
          password,
          otp,
          business_name: businessName,
          owner_name: ownerName,
          phone,
        })
        navigate('/app/dashboard')
      }
    } catch (error) {
      setIsSubmitting(false)
      const msg = error.message || `${mode === 'signin' ? 'Sign in' : 'Registration'} failed.`
      setNotice(msg)
    }
  }

  function switchMode(newMode) {
    setMode(newMode)
    setErrors({})
    setNotice('')
    setSuccessNotice('')
  }

  return (
    <main className="min-h-screen bg-[#0B1020] text-white lg:grid lg:grid-cols-[54fr_46fr]">
      {/* Left Hero Section */}
      <section className="relative isolate flex min-h-[640px] flex-col justify-between overflow-hidden px-6 pb-7 pt-6 sm:px-10 sm:pb-9 sm:pt-8 lg:min-h-screen lg:px-12 lg:pb-10 lg:pt-9 xl:px-16">
        <img
          src="/images/fleet-hero.jpg"
          alt=""
          aria-hidden="true"
          className="absolute inset-0 -z-20 h-full w-full object-cover object-center"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 bg-[linear-gradient(115deg,rgba(4,30,27,0.88)_0%,rgba(5,47,43,0.8)_48%,rgba(8,33,39,0.85)_100%)]"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 bg-[linear-gradient(180deg,rgba(3,21,21,0.15)_0%,transparent_40%,rgba(3,20,22,0.55)_100%)]"
        />

        <header className="flex items-center justify-between gap-4">
          <BrandLogo />
          <span className="hidden items-center gap-2 rounded-full border border-white/20 bg-black/25 px-3.5 py-2 text-[11px] font-medium tracking-[0.12em] text-white/90 backdrop-blur-md sm:inline-flex">
            <span className="h-1.5 w-1.5 rounded-full bg-[#9BE7C4]" />
            VENDOR PLATFORM
          </span>
        </header>

        <div className="my-auto max-w-[620px] py-10 sm:py-14">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.08] px-3.5 py-2 text-xs font-medium text-white/90 backdrop-blur-md">
            <Sparkles size={14} aria-hidden="true" className="text-[#9BE7C4]" />
            Automated fleet operations & verified rentals
          </div>
          <h1 className="text-[clamp(2.5rem,4.8vw,4.2rem)] font-semibold leading-[1.05] tracking-[-0.055em] text-white">
            Your fleet. Your rentals.{' '}
            <span className="text-[#A2E8CA]">Complete control.</span>
          </h1>
          <p className="mt-5 max-w-[480px] text-[15px] leading-7 text-white/75 sm:text-base sm:leading-8">
            Manage online and offline bookings, fleet availability, customer KYC verification,
            and automated payments in one unified vendor dashboard.
          </p>
          <a
            href="#auth-form"
            className="mt-7 inline-flex items-center gap-2 text-sm font-medium text-white transition-colors hover:text-[#A2E8CA]"
          >
            {mode === 'signin' ? 'Sign in to your account' : 'Join as a rental partner'}
            <ArrowUpRight size={16} aria-hidden="true" />
          </a>
        </div>

        <section aria-label="Platform highlights">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-white/75">
              Built for rental operators
            </p>
            <span className="rounded-full border border-white/15 bg-black/20 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.13em] text-[#B8F0D7]">
              WavyGo Fleet OS
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            {fleetHighlights.map((stat) => (
              <StatisticCard key={stat.label} {...stat} />
            ))}
          </div>
        </section>
      </section>

      {/* Right Form Section */}
      <section
        id="auth-form"
        className="flex min-h-[680px] flex-col justify-center bg-[#0B1020] px-6 py-10 sm:px-12 sm:py-14 lg:min-h-screen lg:px-10 xl:px-14"
      >
        <div className="mx-auto w-full max-w-[440px]">
          <div className="mb-8">
            <div className="mb-4 inline-flex items-center gap-2 rounded-xl bg-white/[0.05] p-1 border border-white/10">
              <button
                type="button"
                onClick={() => switchMode('signin')}
                className={`rounded-lg px-4 py-1.5 text-xs font-semibold transition ${
                  mode === 'signin'
                    ? 'bg-[#A2E8CA] text-[#0B2922] shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Sign in
              </button>
              <button
                type="button"
                onClick={() => switchMode('signup')}
                className={`rounded-lg px-4 py-1.5 text-xs font-semibold transition ${
                  mode === 'signup'
                    ? 'bg-[#A2E8CA] text-[#0B2922] shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Create account
              </button>
            </div>

            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.06] text-[#A2E8CA]">
              <KeyRound size={19} strokeWidth={1.8} aria-hidden="true" />
            </div>
            <h2 className="mt-3 text-[28px] font-semibold tracking-[-0.04em] text-white sm:text-[32px]">
              {mode === 'signin' ? 'Welcome back' : 'Start your partner journey'}
            </h2>
            <p className="mt-1 text-sm text-slate-400">
              {mode === 'signin'
                ? 'Sign in to access your vehicles and bookings.'
                : 'Register your rental business with email OTP verification.'}
            </p>
          </div>

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            {/* Business Name (Signup only) */}
            {mode === 'signup' && (
              <div>
                <label htmlFor="businessName" className="mb-1.5 block text-[13px] font-medium text-slate-200">
                  Business name <span className="text-[#A2E8CA]">*</span>
                </label>
                <div
                  className={`flex h-[48px] items-center gap-3 rounded-xl border bg-white/[0.035] px-3.5 transition-colors focus-within:border-[#71CFAB] ${
                    errors.businessName ? 'border-rose-400/75' : 'border-white/[0.12] hover:border-white/25'
                  }`}
                >
                  <Building2 size={17} aria-hidden="true" className="shrink-0 text-slate-500" />
                  <input
                    id="businessName"
                    name="businessName"
                    type="text"
                    placeholder="e.g. Royal Wheels Rentals"
                    value={businessName}
                    onChange={(e) => {
                      setBusinessName(e.target.value)
                      if (errors.businessName) setErrors((prev) => ({ ...prev, businessName: '' }))
                    }}
                    className="h-full min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                  />
                </div>
                {errors.businessName && (
                  <p className="mt-1.5 text-xs text-rose-300">{errors.businessName}</p>
                )}
              </div>
            )}

            {/* Owner Name (Signup only) */}
            {mode === 'signup' && (
              <div>
                <label htmlFor="ownerName" className="mb-1.5 block text-[13px] font-medium text-slate-200">
                  Owner / Contact name
                </label>
                <div className="flex h-[48px] items-center gap-3 rounded-xl border border-white/[0.12] bg-white/[0.035] px-3.5 transition-colors hover:border-white/25 focus-within:border-[#71CFAB]">
                  <User size={17} aria-hidden="true" className="shrink-0 text-slate-500" />
                  <input
                    id="ownerName"
                    name="ownerName"
                    type="text"
                    placeholder="e.g. Garv Agarwal"
                    value={ownerName}
                    onChange={(e) => setOwnerName(e.target.value)}
                    className="h-full min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                  />
                </div>
              </div>
            )}

            {/* Email Address */}
            <div>
              <label htmlFor="email" className="mb-1.5 block text-[13px] font-medium text-slate-200">
                Email address <span className="text-[#A2E8CA]">*</span>
              </label>
              <div
                className={`flex h-[48px] items-center gap-3 rounded-xl border bg-white/[0.035] px-3.5 transition-colors focus-within:border-[#71CFAB] ${
                  errors.email ? 'border-rose-400/75' : 'border-white/[0.12] hover:border-white/25'
                }`}
              >
                <Mail size={17} aria-hidden="true" className="shrink-0 text-slate-500" />
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  autoCapitalize="none"
                  spellCheck="false"
                  placeholder="you@business.com"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    if (errors.email) setErrors((prev) => ({ ...prev, email: '' }))
                  }}
                  className="h-full min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                />
                {mode === 'signup' && (
                  <button
                    type="button"
                    onClick={handleSendOtp}
                    disabled={isSendingOtp || resendCooldown > 0}
                    className="shrink-0 rounded-lg bg-[#A2E8CA]/15 px-2.5 py-1 text-xs font-semibold text-[#A2E8CA] transition hover:bg-[#A2E8CA]/25 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isSendingOtp
                      ? 'Sending…'
                      : resendCooldown > 0
                      ? `${resendCooldown}s`
                      : otpSent
                      ? 'Resend OTP'
                      : 'Send OTP'}
                  </button>
                )}
              </div>
              {errors.email && <p className="mt-1.5 text-xs text-rose-300">{errors.email}</p>}
            </div>

            {/* Phone Number (Signup only) */}
            {mode === 'signup' && (
              <div>
                <label htmlFor="phone" className="mb-1.5 block text-[13px] font-medium text-slate-200">
                  Phone number
                </label>
                <div className="flex h-[48px] items-center gap-3 rounded-xl border border-white/[0.12] bg-white/[0.035] px-3.5 transition-colors hover:border-white/25 focus-within:border-[#71CFAB]">
                  <Phone size={17} aria-hidden="true" className="shrink-0 text-slate-500" />
                  <input
                    id="phone"
                    name="phone"
                    type="tel"
                    placeholder="+91 98765 43210"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="h-full min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                  />
                </div>
              </div>
            )}

            {/* OTP Verification Code (Signup only) */}
            {mode === 'signup' && (
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label htmlFor="otp" className="text-[13px] font-medium text-slate-200">
                    Email Verification Code <span className="text-[#A2E8CA]">*</span>
                  </label>
                  {otpSent && resendCooldown > 0 && (
                    <span className="text-[11px] text-slate-400">
                      Resend in {resendCooldown}s
                    </span>
                  )}
                </div>
                <div
                  className={`flex h-[48px] items-center gap-3 rounded-xl border bg-white/[0.035] px-3.5 transition-colors focus-within:border-[#71CFAB] ${
                    errors.otp ? 'border-rose-400/75' : 'border-white/[0.12] hover:border-white/25'
                  }`}
                >
                  <KeyRound size={17} aria-hidden="true" className="shrink-0 text-slate-500" />
                  <input
                    id="otp"
                    name="otp"
                    type="text"
                    maxLength={6}
                    placeholder="Enter 6-digit OTP from email"
                    value={otp}
                    onChange={(e) => {
                      const clean = e.target.value.replace(/\D/g, '').slice(0, 6)
                      setOtp(clean)
                      if (errors.otp) setErrors((prev) => ({ ...prev, otp: '' }))
                    }}
                    className="h-full min-w-0 flex-1 bg-transparent font-mono text-sm tracking-widest text-white outline-none placeholder:font-sans placeholder:tracking-normal placeholder:text-slate-600"
                  />
                  {otp.length === 6 && (
                    <CheckCircle2 size={18} className="shrink-0 text-[#9BE7C4]" />
                  )}
                </div>
                {errors.otp && <p className="mt-1.5 text-xs text-rose-300">{errors.otp}</p>}
                {!otpSent && (
                  <p className="mt-1 text-[11px] text-slate-400">
                    Click &ldquo;Send OTP&rdquo; above to receive your 6-digit code via email.
                  </p>
                )}
              </div>
            )}

            {/* Password */}
            <div>
              <div className="mb-1.5 flex items-center justify-between gap-3">
                <label htmlFor="password" className="text-[13px] font-medium text-slate-200">
                  Password <span className="text-[#A2E8CA]">*</span>
                </label>
                {mode === 'signin' && (
                  <button
                    type="button"
                    onClick={() =>
                      setNotice('Password reset is available by contacting WavyGo support at garv@wavygo.in')
                    }
                    className="text-xs font-medium text-[#A2E8CA] underline-offset-4 hover:underline"
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <div
                className={`flex h-[48px] items-center gap-3 rounded-xl border bg-white/[0.035] px-3.5 transition-colors focus-within:border-[#71CFAB] ${
                  errors.password ? 'border-rose-400/75' : 'border-white/[0.12] hover:border-white/25'
                }`}
              >
                <LockKeyhole size={17} aria-hidden="true" className="shrink-0 text-slate-500" />
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                  placeholder={mode === 'signin' ? 'Enter your password' : 'Create a secure password (min 8 chars)'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (errors.password) setErrors((prev) => ({ ...prev, password: '' }))
                  }}
                  className="h-full min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="inline-flex h-8 w-8 items-center justify-center text-slate-500 hover:text-slate-200"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && <p className="mt-1.5 text-xs text-rose-300">{errors.password}</p>}
            </div>

            {mode === 'signin' && (
              <label className="flex w-fit cursor-pointer items-center gap-2.5 pt-1 text-[13px] text-slate-400">
                <input
                  type="checkbox"
                  checked={keepSignedIn}
                  onChange={(e) => setKeepSignedIn(e.target.checked)}
                  className="h-4 w-4 cursor-pointer rounded border-white/20 bg-white/[0.06] accent-[#83DBB5]"
                />
                Keep me signed in
              </label>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-6 inline-flex h-[50px] w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#88DFBB] via-[#77D9B2] to-[#9AE4BF] px-4 text-sm font-semibold text-[#0B2922] shadow-[0_10px_26px_rgba(100,207,164,0.16)] transition hover:brightness-105 disabled:cursor-wait disabled:opacity-75"
            >
              {isSubmitting ? (
                <>
                  <span
                    aria-hidden="true"
                    className="h-4 w-4 animate-spin rounded-full border-2 border-[#0B2922]/25 border-t-[#0B2922]"
                  />
                  {mode === 'signin' ? 'Signing in…' : 'Verifying & Registering…'}
                </>
              ) : mode === 'signin' ? (
                'Sign in'
              ) : (
                'Create account'
              )}
            </button>
          </form>

          {/* Switch Tab Link */}
          <div className="mt-5 text-center">
            <button
              type="button"
              onClick={() => switchMode(mode === 'signin' ? 'signup' : 'signin')}
              className="text-xs font-medium text-[#A2E8CA] underline-offset-4 transition hover:text-white hover:underline"
            >
              {mode === 'signin'
                ? "Don't have an account? Sign up with email OTP"
                : 'Already have a registered account? Sign in'}
            </button>
          </div>

          {/* Notices */}
          <div aria-live="polite" className="min-h-10 pt-3">
            {notice && (
              <p className="rounded-xl border border-rose-500/30 bg-rose-500/[0.09] px-3.5 py-2.5 text-xs leading-5 text-rose-200">
                {notice}
              </p>
            )}
            {successNotice && (
              <p className="rounded-xl border border-[#A2E8CA]/30 bg-[#A2E8CA]/[0.08] px-3.5 py-2.5 text-xs leading-5 text-[#C2F3DC]">
                {successNotice}
              </p>
            )}
          </div>

          <div className="mt-6 flex items-center gap-3 border-t border-white/[0.08] pt-5">
            <ShieldCheck size={16} aria-hidden="true" className="shrink-0 text-slate-500" />
            <p className="text-xs text-slate-500">
              WavyGo Vendor OS · Secured with Upstash & Brevo
            </p>
          </div>
        </div>
      </section>
    </main>
  )
}

export default LoginPage
