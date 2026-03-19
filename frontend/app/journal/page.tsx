/**
 * app/journal/page.tsx — Trade journal and review workflow
 *
 * Shows all paper trades with P&L, and lets you:
 * - Close open trades with exit price
 * - Submit a post-trade review with labels
 * - Track which trades still need review
 */
'use client'
import { useState, useEffect } from 'react'
import { api, Trade } from '@/lib/api'
import { PageHeader, VerdictBadge, formatPrice, pnlColor } from '@/components/ui'

const FAILURE_REASONS = [
  'chop', 'news', 'weak_indication', 'poor_correction', 'no_real_continuation',
  'late_entry', 'early_entry', 'stop_too_tight', 'target_unrealistic',
  'countertrend', 'low_liquidity',
]

export default function JournalPage() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'open' | 'closed' | 'needs_review'>('all')
  const [closing, setClosing] = useState<string | null>(null)
  const [reviewing, setReviewing] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.trades.list({ mode: 'paper' })
      setTrades(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filtered = trades.filter(t => {
    if (filter === 'open') return t.status === 'open'
    if (filter === 'closed') return t.status === 'closed'
    if (filter === 'needs_review') return t.status === 'closed' && !t.has_review
    return true
  })

  const needsReview = trades.filter(t => t.status === 'closed' && !t.has_review).length

  return (
    <div style={{ maxWidth: '1000px' }}>
      <PageHeader title="Trade Journal" sub="All paper trades with full ICC context" />

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: '2px', marginBottom: '20px', background: 'var(--bg-card)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border)', width: 'fit-content' }}>
        {([
          ['all', 'All', null],
          ['open', 'Open', null],
          ['closed', 'Closed', null],
          ['needs_review', 'Needs Review', needsReview > 0 ? needsReview : null],
        ] as const).map(([key, label, badge]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            style={{
              padding: '6px 14px', fontSize: '12px', cursor: 'pointer',
              borderRadius: '6px', border: 'none',
              background: filter === key ? 'var(--bg-tertiary)' : 'transparent',
              color: filter === key ? 'var(--text-primary)' : 'var(--text-muted)',
              display: 'flex', alignItems: 'center', gap: '6px',
            }}
          >
            {label}
            {badge != null && (
              <span style={{
                background: '#f59e0b', color: '#000', borderRadius: '10px',
                fontSize: '10px', fontWeight: 600, padding: '1px 5px',
                fontFamily: 'IBM Plex Mono',
              }}>{badge}</span>
            )}
          </button>
        ))}
      </div>

      {/* Trade table */}
      {loading ? (
        <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Loading…</div>
      ) : filtered.length === 0 ? (
        <EmptyJournal />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {filtered.map(t => (
            <TradeRow
              key={t.id}
              trade={t}
              onClose={() => setClosing(t.id)}
              onReview={() => setReviewing(t.id)}
            />
          ))}
        </div>
      )}

      {/* Close trade modal */}
      {closing && (
        <CloseModal
          tradeId={closing}
          onDone={() => { setClosing(null); load() }}
          onCancel={() => setClosing(null)}
        />
      )}

      {/* Review modal */}
      {reviewing && (
        <ReviewModal
          tradeId={reviewing}
          onDone={() => { setReviewing(null); load() }}
          onCancel={() => setReviewing(null)}
        />
      )}
    </div>
  )
}

function TradeRow({ trade, onClose, onReview }: { trade: Trade; onClose: () => void; onReview: () => void }) {
  const isLong = trade.direction === 'bullish' || trade.direction === 'long'
  const dirColor = isLong ? '#22c55e' : '#ef4444'

  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: '8px', padding: '14px 16px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        {/* Symbol + direction */}
        <span style={{ fontFamily: 'IBM Plex Mono', fontWeight: 600, fontSize: '14px', minWidth: '60px' }}>
          {trade.symbol}
        </span>
        <span style={{ fontSize: '12px', color: dirColor }}>{isLong ? '▲' : '▼'} {trade.direction}</span>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{trade.timeframe}m</span>

        {/* Status badge */}
        <span style={{
          fontFamily: 'IBM Plex Mono', fontSize: '10px', fontWeight: 600,
          padding: '2px 7px', borderRadius: '4px',
          background: trade.status === 'open' ? 'rgba(59,130,246,0.12)' : 'rgba(139,144,153,0.1)',
          color: trade.status === 'open' ? '#3b82f6' : 'var(--text-muted)',
          border: `1px solid ${trade.status === 'open' ? 'rgba(59,130,246,0.3)' : 'var(--border)'}`,
        }}>{trade.status.toUpperCase()}</span>

        {/* Prices */}
        <div style={{ display: 'flex', gap: '12px', fontSize: '11px', fontFamily: 'IBM Plex Mono', color: 'var(--text-secondary)', flex: 1 }}>
          <span>E: {formatPrice(trade.entry_price)}</span>
          <span>S: <span style={{ color: '#ef4444' }}>{formatPrice(trade.stop_price)}</span></span>
          {trade.target_price && <span>T: <span style={{ color: '#22c55e' }}>{formatPrice(trade.target_price)}</span></span>}
          {trade.exit_price && <span>X: {formatPrice(trade.exit_price)}</span>}
        </div>

        {/* P&L */}
        {trade.pnl_r != null && (
          <span style={{
            fontFamily: 'IBM Plex Mono', fontWeight: 600, fontSize: '13px',
            color: pnlColor(trade.pnl_r),
          }}>
            {trade.pnl_r > 0 ? '+' : ''}{trade.pnl_r}R
          </span>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: '6px', marginLeft: 'auto' }}>
          {trade.status === 'open' && (
            <ActionButton onClick={onClose} label="Close" color="var(--blue)" />
          )}
          {trade.status === 'closed' && !trade.has_review && (
            <ActionButton onClick={onReview} label="Review ★" color="#f59e0b" />
          )}
          {trade.has_review && (
            <span style={{ fontSize: '11px', color: '#22c55e' }}>✓ Reviewed</span>
          )}
        </div>
      </div>

      {/* ICC context */}
      {(trade.indication_type || trade.correction_zone_type) && (
        <div style={{ display: 'flex', gap: '8px', marginTop: '8px', flexWrap: 'wrap' }}>
          {trade.indication_type && <Tag label={trade.indication_type} />}
          {trade.correction_zone_type && <Tag label={trade.correction_zone_type} />}
          {trade.continuation_trigger_type && <Tag label={trade.continuation_trigger_type} />}
          {trade.confidence_score && (
            <Tag label={`${Math.round(trade.confidence_score * 100)}% conf`} color="var(--blue)" />
          )}
        </div>
      )}
    </div>
  )
}

function ActionButton({ onClick, label, color }: { onClick: () => void; label: string; color: string }) {
  return (
    <button onClick={onClick} style={{
      padding: '5px 12px', fontSize: '11px', cursor: 'pointer',
      borderRadius: '5px', border: `1px solid ${color}`,
      background: 'transparent', color, fontWeight: 500,
    }}>{label}</button>
  )
}

function Tag({ label, color }: { label: string; color?: string }) {
  return (
    <span style={{
      fontSize: '10px', fontFamily: 'IBM Plex Mono',
      padding: '2px 7px', borderRadius: '3px',
      background: 'var(--bg-tertiary)', color: color || 'var(--text-muted)',
      border: '1px solid var(--border)',
    }}>{label}</span>
  )
}

function CloseModal({ tradeId, onDone, onCancel }: { tradeId: string; onDone: () => void; onCancel: () => void }) {
  const [exitPrice, setExitPrice] = useState('')
  const [reason, setReason] = useState('manual')
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    if (!exitPrice) return
    setSubmitting(true)
    try {
      await api.trades.close(tradeId, { exit_price: parseFloat(exitPrice), exit_reason: reason })
      onDone()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal title="Close Trade" onClose={onCancel}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <label style={labelStyle}>
          Exit Price
          <input
            type="number" value={exitPrice} onChange={e => setExitPrice(e.target.value)}
            style={inputStyle} placeholder="e.g. 5250.25"
            autoFocus
          />
        </label>
        <label style={labelStyle}>
          Exit Reason
          <select value={reason} onChange={e => setReason(e.target.value)} style={inputStyle}>
            <option value="stop_hit">Stop Hit</option>
            <option value="target_hit">Target Hit</option>
            <option value="manual">Manual Close</option>
            <option value="trailing">Trailing Stop</option>
          </select>
        </label>
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '8px' }}>
          <button onClick={onCancel} style={cancelBtnStyle}>Cancel</button>
          <button onClick={submit} disabled={!exitPrice || submitting} style={submitBtnStyle}>
            {submitting ? 'Closing…' : 'Close Trade'}
          </button>
        </div>
      </div>
    </Modal>
  )
}

function ReviewModal({ tradeId, onDone, onCancel }: { tradeId: string; onDone: () => void; onCancel: () => void }) {
  const [form, setForm] = useState({
    icc_was_valid: null as boolean | null,
    bias_was_correct: null as boolean | null,
    was_execution_mistake: false,
    was_model_mistake: false,
    failure_reasons: [] as string[],
    what_went_well: '',
    what_went_wrong: '',
    lesson_learned: '',
  })
  const [submitting, setSubmitting] = useState(false)

  const toggleReason = (r: string) => {
    setForm(f => ({
      ...f,
      failure_reasons: f.failure_reasons.includes(r)
        ? f.failure_reasons.filter(x => x !== r)
        : [...f.failure_reasons, r],
    }))
  }

  const submit = async () => {
    setSubmitting(true)
    try {
      await api.trades.submitReview(tradeId, form as any)
      onDone()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal title="Post-Trade Review" onClose={onCancel} wide>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {/* Boolean flags */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <BoolToggle label="ICC setup was valid?" value={form.icc_was_valid}
            onChange={v => setForm(f => ({ ...f, icc_was_valid: v }))} />
          <BoolToggle label="Bias was correct?" value={form.bias_was_correct}
            onChange={v => setForm(f => ({ ...f, bias_was_correct: v }))} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <Checkbox label="Execution mistake" checked={form.was_execution_mistake}
            onChange={v => setForm(f => ({ ...f, was_execution_mistake: v }))} />
          <Checkbox label="Model/strategy mistake" checked={form.was_model_mistake}
            onChange={v => setForm(f => ({ ...f, was_model_mistake: v }))} />
        </div>

        {/* Failure reasons */}
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px' }}>Failure reasons (select all that apply)</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {FAILURE_REASONS.map(r => (
              <button key={r} onClick={() => toggleReason(r)} style={{
                padding: '4px 9px', fontSize: '11px', cursor: 'pointer',
                borderRadius: '4px', border: '1px solid',
                borderColor: form.failure_reasons.includes(r) ? '#ef4444' : 'var(--border)',
                background: form.failure_reasons.includes(r) ? 'rgba(239,68,68,0.12)' : 'var(--bg-tertiary)',
                color: form.failure_reasons.includes(r) ? '#ef4444' : 'var(--text-muted)',
              }}>{r.replace(/_/g, ' ')}</button>
            ))}
          </div>
        </div>

        {/* Notes */}
        <label style={labelStyle}>
          What went well
          <textarea value={form.what_went_well} onChange={e => setForm(f => ({ ...f, what_went_well: e.target.value }))}
            style={{ ...inputStyle, height: '60px', resize: 'vertical' }} placeholder="e.g. Entry was precise, waited for confirmation" />
        </label>
        <label style={labelStyle}>
          What went wrong
          <textarea value={form.what_went_wrong} onChange={e => setForm(f => ({ ...f, what_went_wrong: e.target.value }))}
            style={{ ...inputStyle, height: '60px', resize: 'vertical' }} placeholder="e.g. Entered before continuation confirmed" />
        </label>
        <label style={labelStyle}>
          Lesson learned
          <textarea value={form.lesson_learned} onChange={e => setForm(f => ({ ...f, lesson_learned: e.target.value }))}
            style={{ ...inputStyle, height: '50px', resize: 'vertical' }} placeholder="One actionable takeaway" />
        </label>

        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={cancelBtnStyle}>Cancel</button>
          <button onClick={submit} disabled={submitting} style={submitBtnStyle}>
            {submitting ? 'Saving…' : 'Save Review'}
          </button>
        </div>
      </div>
    </Modal>
  )
}

function BoolToggle({ label, value, onChange }: { label: string; value: boolean | null; onChange: (v: boolean) => void }) {
  return (
    <div>
      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '5px' }}>{label}</div>
      <div style={{ display: 'flex', gap: '6px' }}>
        {[true, false].map(v => (
          <button key={String(v)} onClick={() => onChange(v)} style={{
            flex: 1, padding: '5px', fontSize: '12px', cursor: 'pointer',
            borderRadius: '5px', border: '1px solid',
            borderColor: value === v ? (v ? '#22c55e' : '#ef4444') : 'var(--border)',
            background: value === v ? (v ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)') : 'var(--bg-tertiary)',
            color: value === v ? (v ? '#22c55e' : '#ef4444') : 'var(--text-muted)',
          }}>{v ? 'Yes' : 'No'}</button>
        ))}
      </div>
    </div>
  )
}

function Checkbox({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '12px', color: 'var(--text-secondary)' }}>
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)}
        style={{ accentColor: '#3b82f6' }} />
      {label}
    </label>
  )
}

function Modal({ title, onClose, wide, children }: { title: string; onClose: () => void; wide?: boolean; children: React.ReactNode }) {
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 200 }} />
      <div style={{
        position: 'fixed', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        width: wide ? '560px' : '380px',
        maxHeight: '85vh', overflowY: 'auto',
        background: 'var(--bg-secondary)', border: '1px solid var(--border)',
        borderRadius: '10px', zIndex: 201, padding: '20px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <span style={{ fontWeight: 600, fontSize: '14px' }}>{title}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '18px' }}>×</button>
        </div>
        {children}
      </div>
    </>
  )
}

function EmptyJournal() {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px', padding: '60px 20px', textAlign: 'center' }}>
      <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '6px' }}>No trades yet</div>
      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
        Open a paper trade from the Paper Trading page or from a valid setup evaluation.
      </div>
    </div>
  )
}

// Shared styles
const labelStyle: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: '5px', fontSize: '12px', color: 'var(--text-secondary)' }
const inputStyle: React.CSSProperties = {
  background: 'var(--bg-tertiary)', border: '1px solid var(--border)', borderRadius: '5px',
  color: 'var(--text-primary)', fontSize: '13px', padding: '7px 10px', fontFamily: 'IBM Plex Mono', outline: 'none',
}
const cancelBtnStyle: React.CSSProperties = {
  padding: '7px 16px', fontSize: '12px', cursor: 'pointer',
  borderRadius: '6px', border: '1px solid var(--border)',
  background: 'transparent', color: 'var(--text-muted)',
}
const submitBtnStyle: React.CSSProperties = {
  padding: '7px 16px', fontSize: '12px', cursor: 'pointer',
  borderRadius: '6px', border: 'none',
  background: '#3b82f6', color: '#fff', fontWeight: 500,
}
