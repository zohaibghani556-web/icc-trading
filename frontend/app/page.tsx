/**
 * app/page.tsx — Main Dashboard
 *
 * Live overview of recent setups with plain-English trade instructions.
 */

'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { api, SetupEvaluation, AnalyticsSummary } from '@/lib/api'
import {
  VerdictBadge, DirectionBadge, ConfidenceRing,
  StatCard, ScoreBar, Card, EmptyState, LoadingSpinner, PageHeader,
} from '@/components/ui'

export default function DashboardPage() {
  const [setups, setSetups]   = useState<SetupEvaluation[]>([])
  const [stats, setStats]     = useState<AnalyticsSummary | null>(null)
  const [selected, setSelected] = useState<SetupEvaluation | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.alerts.recent({}), api.analytics.summary()])
      .then(([s, a]) => { setSetups(s); setStats(a) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selected && setups.length > 0)
      setSelected(setups.find(s => s.verdict === 'valid_trade') || setups[0])
  }, [setups])

  const validCount = setups.filter(s => s.verdict === 'valid_trade').length
  const watchCount = setups.filter(s => s.verdict === 'watch_only').length

  return (
    <div>
      <PageHeader title="Dashboard" sub="ICC futures decision-support platform" />

      {/* Stat row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '12px', marginBottom: '24px' }}>
        <StatCard label="Valid setups today" value={validCount} color="var(--green)" />
        <StatCard label="Watch only" value={watchCount} color="var(--amber)" />
        <StatCard label="Paper trades" value={stats?.total_trades ?? '—'} />
        <StatCard
          label="Win rate"
          value={stats?.win_rate ? `${(stats.win_rate * 100).toFixed(0)}%` : '—'}
          sub={stats && stats.total_trades > 0 ? `${stats.winners}W / ${stats.losers}L` : undefined}
          color={stats && stats.win_rate >= 0.5 ? 'var(--green)' : 'var(--red)'}
        />
      </div>

      {/* Feed + detail split */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: '16px' }}>

        {/* Feed */}
        <Card>
          <div style={{
            display: 'grid', gridTemplateColumns: '70px 70px 110px 120px 55px 1fr 50px',
            gap: '12px', padding: '8px 16px', borderBottom: '1px solid var(--border)',
            fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.06em', textTransform: 'uppercase',
          }}>
            {['Symbol','Dir','Verdict','Indication','TF','Summary','Time'].map(h => <span key={h}>{h}</span>)}
          </div>

          {loading && <LoadingSpinner />}
          {!loading && setups.length === 0 && (
            <EmptyState message="No alerts yet" sub="Connect TradingView webhooks to start receiving alerts" />
          )}

          {setups.slice(0, 30).map(s => (
            <div key={s.id} onClick={() => setSelected(s)} style={{
              display: 'grid', gridTemplateColumns: '70px 70px 110px 120px 55px 1fr 50px',
              alignItems: 'center', gap: '12px', padding: '10px 16px',
              borderBottom: '1px solid var(--border)', cursor: 'pointer',
              background: selected?.id === s.id ? 'var(--bg-tertiary)' : 'transparent',
              borderLeft: selected?.id === s.id ? '2px solid var(--blue)' : '2px solid transparent',
            }}>
              <span className="mono" style={{ fontWeight: 600, fontSize: '13px' }}>{s.symbol}</span>
              <DirectionBadge direction={s.direction} />
              <VerdictBadge verdict={s.verdict} />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {s.indication_type?.replace(/_/g, ' ') || '—'}
              </span>
              <span className="mono" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{s.timeframe}m</span>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {s.explanation?.summary?.slice(0, 60) || '—'}
              </span>
              <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'right' }}>
                {new Date(s.evaluated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}

          <div style={{ padding: '10px 16px', borderTop: '1px solid var(--border)' }}>
            <Link href="/alerts" style={{ fontSize: '12px', color: 'var(--blue)', textDecoration: 'none' }}>View all →</Link>
          </div>
        </Card>

        {/* Right panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {selected ? (
            <>
              {/* If valid trade — show execution instructions first */}
              {selected.verdict === 'valid_trade' && selected.entry_price ? (
                <ExecutionPanel setup={selected} />
              ) : (
                <SetupDetailPanel setup={selected} />
              )}
              {/* For valid trades also show score breakdown below */}
              {selected.verdict === 'valid_trade' && (
                <SetupDetailPanel setup={selected} compact />
              )}
            </>
          ) : (
            <Card style={{ padding: '24px' }}>
              <EmptyState message="Select a setup" sub="Click any row to see trade instructions" />
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Plain English Execution Panel ─────────────────────────────────────────

function ExecutionPanel({ setup }: { setup: SetupEvaluation }) {
  const isLong = setup.direction === 'bullish'
  const action = isLong ? 'BUY' : 'SELL'
  const dirWord = isLong ? 'LONG' : 'SHORT'
  const dirColor = isLong ? '#22c55e' : '#ef4444'
  const entry = setup.entry_price!
  const stop = setup.stop_price!
  const target = setup.target_price
  const rr = setup.risk_reward
  const conf = Math.round(setup.confidence_score * 100)

  // Estimate MES dollar risk (MES = $5 per point, 0.25 tick)
  const riskPoints = Math.abs(entry - stop)
  const mesDollarRisk = Math.round(riskPoints * 5)
  const mesDollarReward = target ? Math.round(Math.abs(target - entry) * 5) : null

  const steps = [
    {
      num: '1',
      title: 'Open Tradovate',
      body: 'Go to app.tradovate.com and make sure you are in Paper Trading mode (blue banner at top).',
      color: '#3b82f6',
    },
    {
      num: '2',
      title: `Place a ${dirWord} order on ${setup.symbol}`,
      body: `Click "${action}" → select "Limit" order → enter price ${entry.toFixed(2)} → 1 contract → submit.`,
      color: dirColor,
    },
    {
      num: '3',
      title: 'Set your Stop Loss',
      body: `Immediately after entry, place a Stop order at ${stop.toFixed(2)}. This is your maximum loss. Do not skip this step.`,
      color: '#ef4444',
    },
    ...(target ? [{
      num: '4',
      title: 'Set your Take Profit',
      body: `Place a Limit ${isLong ? 'Sell' : 'Buy'} order at ${target.toFixed(2)} to lock in your profit automatically.`,
      color: '#22c55e',
    }] : []),
    {
      num: target ? '5' : '4',
      title: 'Walk away and let it run',
      body: `You are risking ~$${mesDollarRisk} to make ~$${mesDollarReward ?? '?'} on 1 MES contract. Do not move your stop. Let price hit your target or stop.`,
      color: '#f59e0b',
    },
  ]

  return (
    <Card style={{ overflow: 'hidden' }}>
      {/* Header — big and clear */}
      <div style={{
        padding: '16px 18px',
        background: isLong ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
        borderBottom: `2px solid ${dirColor}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
          <div style={{ fontSize: '18px', fontWeight: 700, color: dirColor, fontFamily: 'IBM Plex Mono' }}>
            {action} {setup.symbol}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ConfidenceRing score={setup.confidence_score} />
            <VerdictBadge verdict={setup.verdict} />
          </div>
        </div>
        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          {conf}% confidence · {setup.timeframe}m chart · {rr ? `${rr}:1 RR` : ''} 
          {setup.has_htf_alignment ? ' · HTF aligned ✓' : ''}
          {setup.is_countertrend ? ' · ⚠ Countertrend' : ''}
        </div>
      </div>

      {/* Trade levels — big numbers */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '1px', background: 'var(--border)',
        borderBottom: '1px solid var(--border)',
      }}>
        {[
          { label: '📍 Entry', value: entry.toFixed(2), color: 'var(--blue)', bg: 'rgba(59,130,246,0.06)' },
          { label: '🛑 Stop Loss', value: stop.toFixed(2), color: '#ef4444', bg: 'rgba(239,68,68,0.06)' },
          { label: '🎯 Take Profit', value: target ? target.toFixed(2) : '—', color: '#22c55e', bg: 'rgba(34,197,94,0.06)' },
        ].map(item => (
          <div key={item.label} style={{ padding: '12px 14px', background: item.bg, textAlign: 'center' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '4px' }}>{item.label}</div>
            <div style={{ fontFamily: 'IBM Plex Mono', fontSize: '16px', fontWeight: 700, color: item.color }}>
              {item.value}
            </div>
          </div>
        ))}
      </div>

      {/* Dollar risk/reward */}
      <div style={{
        padding: '10px 18px',
        background: 'var(--bg-tertiary)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: '20px',
        fontSize: '12px',
      }}>
        <span style={{ color: 'var(--text-muted)' }}>1 MES contract:</span>
        <span>Risk <strong style={{ color: '#ef4444', fontFamily: 'IBM Plex Mono' }}>${mesDollarRisk}</strong></span>
        {mesDollarReward && (
          <span>Reward <strong style={{ color: '#22c55e', fontFamily: 'IBM Plex Mono' }}>${mesDollarReward}</strong></span>
        )}
        {rr && <span style={{ color: 'var(--text-secondary)' }}>({rr}:1 RR)</span>}
      </div>

      {/* Step by step instructions */}
      <div style={{ padding: '14px 18px' }}>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          How to execute this trade
        </div>
        {steps.map((step, i) => (
          <div key={i} style={{
            display: 'flex', gap: '12px', marginBottom: '12px',
            paddingBottom: '12px',
            borderBottom: i < steps.length - 1 ? '1px solid var(--border)' : 'none',
          }}>
            <div style={{
              width: '24px', height: '24px', borderRadius: '50%', flexShrink: 0,
              background: step.color, display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '11px', fontWeight: 700, color: '#000',
            }}>
              {step.num}
            </div>
            <div>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '3px' }}>
                {step.title}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {step.body}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Exit rules */}
      <div style={{
        margin: '0 18px 14px',
        padding: '12px',
        background: 'rgba(245,158,11,0.06)',
        border: '1px solid rgba(245,158,11,0.2)',
        borderRadius: '6px',
        fontSize: '11px',
        color: 'var(--text-secondary)',
        lineHeight: 1.7,
      }}>
        <div style={{ fontWeight: 600, color: '#f59e0b', marginBottom: '4px' }}>⚠ Exit rules</div>
        <div>• If price hits your <strong style={{ color: '#ef4444' }}>stop at {stop.toFixed(2)}</strong> — you lose ~${mesDollarRisk}. Accept it and move on.</div>
        {target && <div>• If price hits your <strong style={{ color: '#22c55e' }}>target at {target.toFixed(2)}</strong> — you win ~${mesDollarReward}. Close the trade.</div>}
        <div>• Never move your stop further away. Never add to a losing trade.</div>
      </div>

      <div style={{ padding: '0 18px 14px' }}>
        <Link href={`/paper-trading?setup=${setup.id}`} style={{ textDecoration: 'none' }}>
          <div style={{
            background: '#3b82f6', borderRadius: '6px', padding: '10px',
            textAlign: 'center', fontSize: '13px', fontWeight: 600, color: '#fff', cursor: 'pointer',
          }}>
            Log this as a paper trade →
          </div>
        </Link>
      </div>
    </Card>
  )
}

// ── Setup Detail Panel (scores) ────────────────────────────────────────────

function SetupDetailPanel({ setup, compact }: { setup: SetupEvaluation; compact?: boolean }) {
  const phases = ['environment','indication','correction','continuation','risk']
  return (
    <Card style={{ overflow: 'hidden' }}>
      {!compact && (
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="mono" style={{ fontWeight: 700, fontSize: '15px' }}>{setup.symbol}</span>
            <DirectionBadge direction={setup.direction} />
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{setup.timeframe}m</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <ConfidenceRing score={setup.confidence_score} />
            <VerdictBadge verdict={setup.verdict} />
          </div>
        </div>
      )}

      <div style={{ padding: '14px 16px' }}>
        {compact && (
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            ICC Phase Scores
          </div>
        )}
        {!compact && (
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '14px', lineHeight: 1.6 }}>
            {setup.explanation?.summary}
          </p>
        )}

        {phases.map(key => {
          const phase = setup.score_breakdown?.[key]
          if (!phase) return null
          return <ScoreBar key={key} label={key.charAt(0).toUpperCase() + key.slice(1)} score={phase.score} />
        })}

        {!compact && setup.verdict !== 'valid_trade' && (
          <div style={{ display: 'flex', gap: '6px', marginTop: '12px', flexWrap: 'wrap' }}>
            {setup.is_countertrend && (
              <span style={{ fontSize: '10px', color: 'var(--amber)', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', padding: '2px 6px', borderRadius: '4px' }}>COUNTERTREND</span>
            )}
            {setup.correction_zone_type && (
              <span style={{ fontSize: '10px', color: 'var(--cyan)', background: 'rgba(6,182,212,0.1)', border: '1px solid rgba(6,182,212,0.3)', padding: '2px 6px', borderRadius: '4px' }}>
                {setup.correction_zone_type.replace(/_/g,' ').toUpperCase()}
              </span>
            )}
          </div>
        )}

        {!compact && setup.explanation?.suggested_review_note && (
          <div style={{ marginTop: '12px', padding: '10px 12px', background: 'var(--bg-secondary)', borderRadius: '6px', fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            💡 {setup.explanation.suggested_review_note}
          </div>
        )}
      </div>
    </Card>
  )
}
