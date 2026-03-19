/**
 * lib/api.ts — Frontend API client
 *
 * All API calls go through this file. Never call fetch() directly from components.
 * Change NEXT_PUBLIC_API_URL in .env.local to point at your backend.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `API error ${res.status}`)
  }
  return res.json()
}

// ── Setups ────────────────────────────────────────────────────────────────
export const api = {
  setups: {
    list: (params?: { symbol?: string; verdict?: string; limit?: number }) => {
      const q = new URLSearchParams(params as any).toString()
      return request<SetupEvaluation[]>(`/setups/?${q}`)
    },
    get: (id: string) => request<SetupEvaluation>(`/setups/${id}`),
    updateNotes: (id: string, notes: string) =>
      request(`/setups/${id}/notes`, {
        method: 'PATCH',
        body: JSON.stringify({ notes }),
      }),
  },

  alerts: {
    recent: (params?: { symbol?: string; verdict?: string }) => {
      const q = new URLSearchParams(params as any).toString()
      return request<SetupEvaluation[]>(`/alerts/recent?${q}`)
    },
  },

  trades: {
    list: (params?: { status?: string; symbol?: string; mode?: string }) => {
      const q = new URLSearchParams({ mode: 'paper', ...params } as any).toString()
      return request<Trade[]>(`/trades/?${q}`)
    },
    get: (id: string) => request<Trade>(`/trades/${id}`),
    create: (data: TradeCreatePayload) =>
      request<Trade>('/trades/', { method: 'POST', body: JSON.stringify(data) }),
    close: (id: string, data: TradeClosePayload) =>
      request(`/trades/${id}/close`, { method: 'PATCH', body: JSON.stringify(data) }),
    submitReview: (id: string, data: TradeReviewPayload) =>
      request(`/trades/${id}/review`, { method: 'POST', body: JSON.stringify(data) }),
    getReview: (id: string) => request(`/trades/${id}/review`),
  },

  analytics: {
    summary: (mode = 'paper') => request<AnalyticsSummary>(`/analytics/summary?mode=${mode}`),
    bySymbol: (mode = 'paper') => request<SymbolPerf[]>(`/analytics/by-symbol?mode=${mode}`),
    byScore: (mode = 'paper') => request(`/analytics/by-setup-score?mode=${mode}`),
    verdictCounts: () => request<VerdictCount[]>('/analytics/setup-verdicts'),
  },

  config: {
    get: () => request<ICCConfig>('/config/active'),
    update: (data: Partial<ICCConfig>) =>
      request('/config/active', { method: 'PATCH', body: JSON.stringify(data) }),
  },
}

// ── Types ─────────────────────────────────────────────────────────────────
export interface SetupEvaluation {
  id: string
  symbol: string
  timeframe: string
  direction: string
  verdict: 'valid_trade' | 'watch_only' | 'invalid_setup'
  environment_score: number
  indication_score: number
  correction_score: number
  continuation_score: number
  risk_score: number
  confidence_score: number
  indication_type?: string
  correction_zone_type?: string
  continuation_trigger_type?: string
  entry_price?: number
  stop_price?: number
  target_price?: number
  risk_reward?: number
  explanation: {
    verdict: string
    summary: string
    confidence: number
    passed_rules: string[]
    failed_rules: string[]
    warnings: string[]
    phase_summaries: Record<string, { passed: boolean; score: number; summary: string }>
    suggested_review_note: string
  }
  score_breakdown: Record<string, any>
  is_countertrend: boolean
  has_htf_alignment: boolean
  htf_bias?: string
  session?: string
  evaluated_at: string
  notes?: string
}

export interface Trade {
  id: string
  symbol: string
  timeframe: string
  direction: string
  mode: string
  status: 'open' | 'closed' | 'cancelled'
  entry_price: number
  stop_price: number
  target_price?: number
  exit_price?: number
  exit_time?: string
  exit_reason?: string
  contracts: number
  pnl_dollars?: number
  pnl_r?: number
  actual_rr?: number
  planned_rr?: number
  mae?: number
  mfe?: number
  confidence_score?: number
  indication_type?: string
  correction_zone_type?: string
  continuation_trigger_type?: string
  entry_time: string
  notes?: string
  has_review: boolean
}

export interface AnalyticsSummary {
  total_trades: number
  winners: number
  losers: number
  win_rate: number
  avg_rr: number
  expectancy_r: number
  total_pnl_r: number
  avg_winner_r: number
  avg_loser_r: number
  profit_factor: number
}

export interface SymbolPerf {
  symbol: string
  trades: number
  win_rate: number
  total_pnl_r: number
}

export interface VerdictCount {
  verdict: string
  count: number
}

export interface ICCConfig {
  id: string
  name: string
  min_retracement_pct: number
  max_retracement_pct: number
  min_risk_reward: number
  daily_max_loss_pct: number
  max_consecutive_losses: number
  max_open_positions: number
  require_htf_bias: boolean
  allowed_sessions: string[]
  require_correction_zone: boolean
  countertrend_score_penalty: number
  max_risk_per_trade_pct: number
}

export interface TradeCreatePayload {
  symbol: string
  timeframe: string
  direction: string
  entry_price: number
  stop_price: number
  target_price?: number
  contracts?: number
  notes?: string
  setup_id?: string
}

export interface TradeClosePayload {
  exit_price: number
  exit_reason?: string
  mae?: number
  mfe?: number
}

export interface TradeReviewPayload {
  icc_was_valid?: boolean
  bias_was_correct?: boolean
  was_execution_mistake?: boolean
  was_model_mistake?: boolean
  failure_reasons?: string[]
  what_went_well?: string
  what_went_wrong?: string
  lesson_learned?: string
  indication_rating?: number
  correction_rating?: number
  continuation_rating?: number
  execution_rating?: number
}
