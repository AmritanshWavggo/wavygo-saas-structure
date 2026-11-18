import { apiFetch } from './apiClient.js'

/**
 * Service to interact with the backend Finance API
 */
export const financeService = {
  /**
   * Get high-level finance overview, monthly trends, and expense breakdown
   */
  async getOverview() {
    return apiFetch('/finance/overview')
  },

  /**
   * Get cash flow statement by payment method
   */
  async getCashflow() {
    return apiFetch('/finance/cashflow')
  },

  /**
   * Get Profit & Loss (P&L) statement
   */
  async getPnL() {
    return apiFetch('/finance/pnl')
  },

  /**
   * List operational expenses with filtering
   */
  async listExpenses({ category, status, query, skip = 0, limit = 50 } = {}) {
    const params = new URLSearchParams()
    if (category && category !== 'All') params.append('category', category)
    if (status && status !== 'All') params.append('status', status)
    if (query && query.trim()) params.append('query', query.trim())
    if (skip > 0) params.append('skip', String(skip))
    if (limit) params.append('limit', String(limit))

    const qs = params.toString() ? `?${params.toString()}` : ''
    return apiFetch(`/finance/expenses${qs}`)
  },

  /**
   * Get single expense details
   */
  async getExpense(expenseId) {
    return apiFetch(`/finance/expenses/${encodeURIComponent(expenseId)}`)
  },

  /**
   * Record a new expense
   */
  async createExpense(payload) {
    return apiFetch('/finance/expenses', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  /**
   * Update expense
   */
  async updateExpense(expenseId, updates) {
    return apiFetch(`/finance/expenses/${encodeURIComponent(expenseId)}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    })
  },

  /**
   * Delete expense
   */
  async deleteExpense(expenseId) {
    return apiFetch(`/finance/expenses/${encodeURIComponent(expenseId)}`, {
      method: 'DELETE',
    })
  },
}

export default financeService

