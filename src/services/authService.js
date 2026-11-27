import { apiFetch } from './apiClient.js'

export const authService = {
  /**
   * Log in vendor with email and password
   * Returns { access_token, token_type }
   */
  async login({ email, password, totp_code }) {
    const data = await apiFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        password,
        totp_code: totp_code || undefined,
      }),
    })
    if (data?.access_token) {
      localStorage.setItem('access_token', data.access_token)
      sessionStorage.setItem('wavygo-demo-access', 'enabled')
      sessionStorage.setItem('wavygo-user-email', email.trim().toLowerCase())
      if (data.business_name) localStorage.setItem('wavygo-business-name', data.business_name)
      if (data.owner_name) localStorage.setItem('wavygo-owner-name', data.owner_name)
    }
    return data
  },

  /**
   * Send 6-digit OTP verification code for vendor signup via Brevo email
   */
  async sendSignupOtp({ email, name }) {
    return await apiFetch('/auth/signup/send-otp', {
      method: 'POST',
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        name: name?.trim() || undefined,
      }),
    })
  },

  /**
   * Register new vendor partner after verifying OTP code from Upstash Redis
   */
  async signup({ email, password, otp, business_name, owner_name, phone, city, state }) {
    const data = await apiFetch('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        password,
        otp: otp.trim(),
        business_name: business_name.trim(),
        owner_name: owner_name?.trim() || undefined,
        phone: phone?.trim() || undefined,
        city: city?.trim() || undefined,
        state: state?.trim() || undefined,
      }),
    })
    if (data?.access_token) {
      localStorage.setItem('access_token', data.access_token)
      sessionStorage.setItem('wavygo-demo-access', 'enabled')
      sessionStorage.setItem('wavygo-user-email', email.trim().toLowerCase())
      if (data.business_name) localStorage.setItem('wavygo-business-name', data.business_name)
      if (data.owner_name) localStorage.setItem('wavygo-owner-name', data.owner_name)
    }
    return data
  },

  logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('wavygo-business-name')
    localStorage.removeItem('wavygo-owner-name')
    sessionStorage.removeItem('wavygo-demo-access')
    sessionStorage.removeItem('wavygo-user-email')
  },

  getToken() {
    return (
      localStorage.getItem('access_token') ||
      sessionStorage.getItem('access_token') ||
      (sessionStorage.getItem('wavygo-demo-access') ? 'wavygo-demo-access' : null)
    )
  },

  isAuthenticated() {
    return Boolean(this.getToken())
  },
}

export default authService
