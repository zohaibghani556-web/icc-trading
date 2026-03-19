/**
 * app/alerts/page.tsx — Live alerts feed
 *
 * Shows all incoming setup evaluations in reverse-chronological order.
 * Filterable by symbol, verdict, and direction.
 * Click any setup to see the full ICC breakdown.
 */
'use client'
import { useState, useEffect, useCallback } from 'react'
import { api, SetupEvaluation } from '@/lib/api'
import { PageHeader, SetupCard } from '@/components/ui'
import { SetupDetail } from '@/components/ui/SetupDetail'

const SYMBOLS = ['All', 'ES1!', 'MES1!', 'NQ1!', 'MNQ1!', 'YM1!', 'CL1!', 'GC1!']
const VERDICTS = ['All', 'valid_trade', 'watch_only', 'invalid_setup']

export default function AlertsPage() {
  const [setups, setSetups] = useState<SetupEvaluation[]>([])
  const [selected, setSelected] = useState<SetupEvaluation | null>(null)
  const [loading, setLoading] = useState(true)
  const [symbol, setSymbol] = useState('All')
  const [verdict, setVerdict] = useState('All')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (symbol !== 'All') params.symbol = symbol
      if (verdict !== 'All') params.verdict = verdict
      const data = await api.setups.list({ ...params, limit: 200 })
      setSetups(data)
    } finally {
      setLoading(false)
    }
  }, [symbol, verdict])

  useEffect(() => { load() }, [load])

  return (
    <div style={{ maxWidth: '900px' }}>
      <PageHeader
        title="Alert Feed"
        sub="All incoming TradingView webhooks evaluated against the ICC rulebook"
        action={
          <button
            onClick={load}
            style={{
              padding: '7px 14px', fontSize: '12px', cursor: 'pointer',
              background: 'var(--bg-card)', color: 'var(--text-secondary)',
              border: '1px solid var(--border)', borderRadius: '6px',
            }}
          >
            ↻ Refresh
          </button>
        }
      />

      {/* Filters */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
        <FilterGroup label="Symbol" options={SYMBOLS} value={symbol} onChange={setSymbol} />
        <FilterGroup label="Verdict" options={VERDICTS} value={verdict} onChange={setVerdict} />
      </div>

      {/* Results count */}
      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
        {loading ? 'Loading…' : `${setups.length} setups`}
      </div>

      {/* Setup list */}
      {!loading && setups.length === 0 ? (
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: '8px', padding: '60px 20px', textAlign: 'center',
        }}>
          <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
            No setups found
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Send a TradingView webhook to <code style={{ color: 'var(--blue)' }}>POST /api/v1/alerts/webhook</code>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {setups.map(s => (
            <SetupCard key={s.id} setup={s} onClick={() => setSelected(s)} />
          ))}
        </div>
      )}

      {/* Detail panel */}
      {selected && (
        <>
          <div onClick={() => setSelected(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 99 }} />
          <SetupDetail setup={selected} onClose={() => setSelected(null)} />
        </>
      )}
    </div>
  )
}

function FilterGroup({
  label, options, value, onChange,
}: { label: string; options: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{label}:</span>
      {options.map(o => (
        <button
          key={o}
          onClick={() => onChange(o)}
          style={{
            padding: '4px 10px', fontSize: '11px', cursor: 'pointer',
            borderRadius: '4px', border: '1px solid',
            fontFamily: o.includes('!') ? 'IBM Plex Mono' : 'inherit',
            borderColor: value === o ? 'var(--blue)' : 'var(--border)',
            background: value === o ? 'rgba(59,130,246,0.12)' : 'var(--bg-card)',
            color: value === o ? 'var(--blue)' : 'var(--text-secondary)',
          }}
        >
          {o === 'valid_trade' ? 'Valid' : o === 'watch_only' ? 'Watch' : o === 'invalid_setup' ? 'Invalid' : o}
        </button>
      ))}
    </div>
  )
}
