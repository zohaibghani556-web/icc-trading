/**
 * app/paper-trading/page.tsx — Paper trading console
 *
 * Manually open paper trades with full ICC context.
 * Monitor open positions. Close trades with P&L tracking.
 */
'use client'
import { useState, useEffect } from 'react'
import { api, Trade } from '@/lib/api'
import { PageHeader, formatPrice, pnlColor } from '@/components/ui'

const SYMBOLS = ['ES1!', 'MES1!', 'NQ1!', 'MNQ1!', 'YM1!', 'MYM1!', 'CL1!', 'MCL1!', 'GC1!', 'MGC1!']

export default function PaperTradingPage() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)

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

  const openTrades = trades.filter(t => t.status === 'open')
  const recentClosed = trades.filter(t => t.status === 'closed').slice(0, 10)

  // Running P&L for open positions
  const totalClosedPnl = trades.filter(t => t.status === 'closed' && t.pnl_r != null)
    .reduce((sum, t) => sum + (t.pnl_r ?? 0), 0)

  return (
    <div style={{ maxWidth: '1000px' }}>
      <PageHeader
        title="Paper Trading"
        sub="Simulate trades with full ICC context. No real money."
        action={
          <button onClick={() => setShowForm(true)} style={{
            padding: '8px 16px', fontSize: '12px', cursor: 'pointer',
            borderRadius: '6px', border: 'none',
            background: '#3b82f6', color: '#fff', fontWeight: 500,
          }}>
            + New Trade
          </button>
        }
      />

      {/* Summary row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '24px' }}>
        <SummaryCard label="Open Positions" value={openTrades.length} />
        <SummaryCard label="Closed Trades" value={trades.filter(t => t.status === 'closed').length} />
        <SummaryCard
          label="Closed P&L"
          value={`${totalClosedPnl > 0 ? '+' : ''}${totalClosedPnl.toFixed(2)}R`}
          color={pnlColor(totalClosedPnl)}
        />
        <SummaryCard
          label="Needs Review"
          value={trades.filter(t => t.status === 'closed' && !t.has_review).length}
          color="#f59e0b"
        />
      </div>

      {/* Open positions */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '10px' }}>Open Positions</div>
        {loading ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Loading…</div>
        ) : openTrades.length === 0 ? (
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px', padding: '30px', textAlign: 'center', fontSize: '13px', color: 'var(--text-muted)' }}>
            No open positions. Click "New Trade" to enter a paper trade.
          </div>
        ) : (
          openTrades.map(t => <OpenPositionRow key={t.id} trade={t} onClose={load} />)
        )}
      </div>

      {/* Recent closed */}
      {recentClosed.length > 0 && (
        <div>
          <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '10px' }}>Recent Closed</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Symbol', 'Dir', 'Entry', 'Exit', 'P&L', 'RR', 'Exit Reason', 'Review'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '6px 10px', fontSize: '11px', color: 'var(--text-muted)', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recentClosed.map(t => (
                <tr key={t.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={tdStyle}><span style={{ fontFamily: 'IBM Plex Mono', fontWeight: 600 }}>{t.symbol}</span></td>
                  <td style={tdStyle}>
                    <span style={{ color: (t.direction === 'bullish' || t.direction === 'long') ? '#22c55e' : '#ef4444' }}>
                      {(t.direction === 'bullish' || t.direction === 'long') ? '▲' : '▼'}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, fontFamily: 'IBM Plex Mono' }}>{formatPrice(t.entry_price)}</td>
                  <td style={{ ...tdStyle, fontFamily: 'IBM Plex Mono' }}>{formatPrice(t.exit_price)}</td>
                  <td style={{ ...tdStyle, fontFamily: 'IBM Plex Mono', color: pnlColor(t.pnl_r) }}>
                    {t.pnl_r != null ? `${t.pnl_r > 0 ? '+' : ''}${t.pnl_r}R` : '—'}
                  </td>
                  <td style={{ ...tdStyle, fontFamily: 'IBM Plex Mono', color: 'var(--text-secondary)' }}>
                    {t.actual_rr != null ? `${t.actual_rr}:1` : '—'}
                  </td>
                  <td style={{ ...tdStyle, color: 'var(--text-muted)' }}>{t.exit_reason || '—'}</td>
                  <td style={tdStyle}>
                    {t.has_review
                      ? <span style={{ color: '#22c55e', fontSize: '11px' }}>✓</span>
                      : <a href="/journal" style={{ color: '#f59e0b', fontSize: '11px', textDecoration: 'none' }}>Review</a>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* New trade modal */}
      {showForm && (
        <NewTradeModal
          onDone={() => { setShowForm(false); load() }}
          onCancel={() => setShowForm(false)}
        />
      )}
    </div>
  )
}

function OpenPositionRow({ trade, onClose }: { trade: Trade; onClose: () => void }) {
  const [exitPrice, setExitPrice] = useState('')
  const [closing, setClosing] = useState(false)
  const [showClose, setShowClose] = useState(false)
  const isLong = trade.direction === 'bullish' || trade.direction === 'long'
  const dirColor = isLong ? '#22c55e' : '#ef4444'

  const doClose = async () => {
    if (!exitPrice) return
    setClosing(true)
    try {
      await api.trades.close(trade.id, { exit_price: parseFloat(exitPrice), exit_reason: 'manual' })
      onClose()
    } finally {
      setClosing(false)
    }
  }

  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px', padding: '14px 16px', marginBottom: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span style={{ fontFamily: 'IBM Plex Mono', fontWeight: 600 }}>{trade.symbol}</span>
            <span style={{ fontSize: '12px', color: dirColor }}>{isLong ? '▲ LONG' : '▼ SHORT'}</span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{trade.contracts} contract{trade.contracts !== 1 ? 's' : ''}</span>
          </div>
          <div style={{ display: 'flex', gap: '16px', fontFamily: 'IBM Plex Mono', fontSize: '12px', color: 'var(--text-secondary)' }}>
            <span>Entry: {formatPrice(trade.entry_price)}</span>
            <span style={{ color: '#ef4444' }}>Stop: {formatPrice(trade.stop_price)}</span>
            {trade.target_price && <span style={{ color: '#22c55e' }}>Target: {formatPrice(trade.target_price)}</span>}
            {trade.planned_rr && <span style={{ color: '#3b82f6' }}>RR: {trade.planned_rr}:1</span>}
          </div>
        </div>

        {!showClose ? (
          <button onClick={() => setShowClose(true)} style={{
            padding: '6px 14px', fontSize: '12px', cursor: 'pointer',
            borderRadius: '5px', border: '1px solid #ef4444',
            background: 'transparent', color: '#ef4444',
          }}>Close</button>
        ) : (
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <input
              type="number" value={exitPrice} onChange={e => setExitPrice(e.target.value)}
              placeholder="Exit price" autoFocus
              style={{
                background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
                borderRadius: '5px', color: 'var(--text-primary)', padding: '6px 10px',
                fontSize: '12px', fontFamily: 'IBM Plex Mono', width: '130px', outline: 'none',
              }}
            />
            <button onClick={doClose} disabled={!exitPrice || closing} style={{
              padding: '6px 12px', fontSize: '12px', cursor: 'pointer',
              borderRadius: '5px', border: 'none', background: '#ef4444', color: '#fff',
            }}>{closing ? '…' : 'Confirm'}</button>
            <button onClick={() => setShowClose(false)} style={{
              padding: '6px 8px', fontSize: '12px', cursor: 'pointer',
              borderRadius: '5px', border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-muted)',
            }}>✕</button>
          </div>
        )}
      </div>
    </div>
  )
}

function NewTradeModal({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [form, setForm] = useState({
    symbol: 'ES1!', timeframe: '5', direction: 'bullish',
    entry_price: '', stop_price: '', target_price: '',
    contracts: '1', notes: '',
  })
  const [submitting, setSubmitting] = useState(false)

  const set = (k: string) => (e: React.ChangeEvent<any>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  // Live RR preview
  const rr = (() => {
    const e = parseFloat(form.entry_price)
    const s = parseFloat(form.stop_price)
    const t = parseFloat(form.target_price)
    if (!e || !s || !t) return null
    const risk = Math.abs(e - s)
    const reward = Math.abs(t - e)
    if (risk === 0) return null
    return (reward / risk).toFixed(2)
  })()

  const submit = async () => {
    if (!form.entry_price || !form.stop_price) return
    setSubmitting(true)
    try {
      await api.trades.create({
        symbol: form.symbol,
        timeframe: form.timeframe,
        direction: form.direction,
        entry_price: parseFloat(form.entry_price),
        stop_price: parseFloat(form.stop_price),
        target_price: form.target_price ? parseFloat(form.target_price) : undefined,
        contracts: parseInt(form.contracts),
        notes: form.notes || undefined,
      })
      onDone()
    } finally {
      setSubmitting(false)
    }
  }

  const iStyle: React.CSSProperties = {
    background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
    borderRadius: '5px', color: 'var(--text-primary)', padding: '7px 10px',
    fontSize: '13px', fontFamily: 'IBM Plex Mono', outline: 'none', width: '100%',
  }

  return (
    <>
      <div onClick={onCancel} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 200 }} />
      <div style={{
        position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
        width: '420px', background: 'var(--bg-secondary)', border: '1px solid var(--border)',
        borderRadius: '10px', zIndex: 201, padding: '20px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
          <span style={{ fontWeight: 600, fontSize: '14px' }}>New Paper Trade</span>
          <button onClick={onCancel} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '18px' }}>×</button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <label style={lbl}>
              Symbol
              <select value={form.symbol} onChange={set('symbol')} style={iStyle}>
                {SYMBOLS.map(s => <option key={s}>{s}</option>)}
              </select>
            </label>
            <label style={lbl}>
              Timeframe
              <select value={form.timeframe} onChange={set('timeframe')} style={iStyle}>
                {['1', '3', '5', '15', '30', '60'].map(t => <option key={t}>{t}</option>)}
              </select>
            </label>
          </div>

          <label style={lbl}>
            Direction
            <div style={{ display: 'flex', gap: '6px' }}>
              {['bullish', 'bearish'].map(d => (
                <button key={d} onClick={() => setForm(f => ({ ...f, direction: d }))} style={{
                  flex: 1, padding: '7px', fontSize: '12px', cursor: 'pointer', borderRadius: '5px',
                  border: `1px solid ${form.direction === d ? (d === 'bullish' ? '#22c55e' : '#ef4444') : 'var(--border)'}`,
                  background: form.direction === d ? (d === 'bullish' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)') : 'var(--bg-tertiary)',
                  color: form.direction === d ? (d === 'bullish' ? '#22c55e' : '#ef4444') : 'var(--text-muted)',
                }}>{d === 'bullish' ? '▲ Long' : '▼ Short'}</button>
              ))}
            </div>
          </label>

          <label style={lbl}>Entry Price <input type="number" value={form.entry_price} onChange={set('entry_price')} style={iStyle} placeholder="e.g. 5250.00" /></label>
          <label style={lbl}>Stop Price  <input type="number" value={form.stop_price}  onChange={set('stop_price')}  style={iStyle} placeholder="e.g. 5235.00" /></label>
          <label style={lbl}>Target Price (optional) <input type="number" value={form.target_price} onChange={set('target_price')} style={iStyle} placeholder="e.g. 5285.00" /></label>

          {rr && (
            <div style={{ fontSize: '12px', fontFamily: 'IBM Plex Mono', color: parseFloat(rr) >= 2 ? '#22c55e' : '#f59e0b', background: 'var(--bg-tertiary)', padding: '8px 12px', borderRadius: '5px' }}>
              RR: {rr}:1 {parseFloat(rr) < 2 && '⚠ below 2:1 minimum'}
            </div>
          )}

          <label style={lbl}>Notes (optional) <input type="text" value={form.notes} onChange={set('notes')} style={iStyle} placeholder="Setup context, reason for entry…" /></label>

          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '4px' }}>
            <button onClick={onCancel} style={{ padding: '7px 16px', fontSize: '12px', cursor: 'pointer', borderRadius: '6px', border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-muted)' }}>Cancel</button>
            <button onClick={submit} disabled={!form.entry_price || !form.stop_price || submitting} style={{ padding: '7px 16px', fontSize: '12px', cursor: 'pointer', borderRadius: '6px', border: 'none', background: '#3b82f6', color: '#fff', fontWeight: 500 }}>
              {submitting ? 'Opening…' : 'Open Trade'}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

function SummaryCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px', padding: '14px 16px' }}>
      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>{label}</div>
      <div style={{ fontFamily: 'IBM Plex Mono', fontSize: '20px', fontWeight: 600, color: color || 'var(--text-primary)' }}>{value}</div>
    </div>
  )
}

const lbl: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', color: 'var(--text-secondary)' }
const tdStyle: React.CSSProperties = { padding: '8px 10px', color: 'var(--text-secondary)' }
