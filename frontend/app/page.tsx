/**
 * app/page.tsx — Main Dashboard
 *
 * Live overview of recent setups, quick stats, and today's activity.
 * The selected row on the left populates the detail panel on the right.
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

  const validCount   = setups.filter(s => s.verdict === 'valid_trade').length
  const watchCount   = setups.filter(s => s.verdict === 'watch_only').length

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
          sub={stats ? `${stats.winners}W / ${stats.losers}L` : undefined}
          color={stats && stats.win_rate >= 0.5 ? 'var(--green)' : 'var(--red)'}
        />
      </div>

      {/* Feed + detail split */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: '16px' }}>

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

        {/* Detail panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {selected ? <SetupDetailPanel setup={selected} /> : (
            <Card style={{ padding: '24px' }}>
              <EmptyState message="Select a setup" sub="Click any row" />
            </Card>
          )}
          {selected?.verdict === 'valid_trade' && (
            <Link href={`/paper-trading?setup=${selected.id}`} style={{ textDecoration: 'none' }}>
              <div style={{
                background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.4)',
                borderRadius: '8px', padding: '14px 16px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--blue)' }}>Open paper trade</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {selected.symbol} · RR {selected.risk_reward?.toFixed(1) || '?'}:1
                  </div>
                </div>
                <span style={{ fontSize: '18px', color: 'var(--blue)' }}>→</span>
              </div>
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}

function SetupDetailPanel({ setup }: { setup: SetupEvaluation }) {
  const phases = ['environment','indication','correction','continuation','risk']
  return (
    <Card style={{ overflow: 'hidden' }}>
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

      <div style={{ padding: '14px 16px' }}>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '14px', lineHeight: 1.6 }}>
          {setup.explanation?.summary}
        </p>

        {phases.map(key => {
          const phase = setup.score_breakdown?.[key]
          if (!phase) return null
          return <ScoreBar key={key} label={key.charAt(0).toUpperCase() + key.slice(1)} score={phase.score} />
        })}

        {setup.verdict === 'valid_trade' && setup.entry_price && (
          <div style={{ marginTop: '14px', padding: '12px', background: 'var(--bg-tertiary)', borderRadius: '6px', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Trade levels</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '8px' }}>
              {[
                { label: 'Entry',  value: setup.entry_price,  color: 'var(--blue)' },
                { label: 'Stop',   value: setup.stop_price,   color: 'var(--red)' },
                { label: 'Target', value: setup.target_price, color: 'var(--green)' },
                { label: 'RR',     value: setup.risk_reward ? `${setup.risk_reward}:1` : '—', color: 'var(--text-primary)' },
              ].map(item => (
                <div key={item.label} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{item.label}</div>
                  <div className="mono" style={{ fontSize: '13px', fontWeight: 600, color: item.color, marginTop: '2px' }}>
                    {typeof item.value === 'number' ? item.value.toFixed(2) : (item.value ?? '—')}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: 'flex', gap: '6px', marginTop: '12px', flexWrap: 'wrap' }}>
          {setup.is_countertrend && (
            <span style={{ fontSize: '10px', color: 'var(--amber)', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', padding: '2px 6px', borderRadius: '4px' }}>COUNTERTREND</span>
          )}
          {setup.has_htf_alignment && (
            <span style={{ fontSize: '10px', color: 'var(--green)', background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', padding: '2px 6px', borderRadius: '4px' }}>HTF ALIGNED</span>
          )}
          {setup.correction_zone_type && (
            <span style={{ fontSize: '10px', color: 'var(--cyan)', background: 'rgba(6,182,212,0.1)', border: '1px solid rgba(6,182,212,0.3)', padding: '2px 6px', borderRadius: '4px' }}>
              {setup.correction_zone_type.replace(/_/g,' ').toUpperCase()}
            </span>
          )}
        </div>

        {setup.explanation?.suggested_review_note && (
          <div style={{ marginTop: '12px', padding: '10px 12px', background: 'var(--bg-secondary)', borderRadius: '6px', fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            💡 {setup.explanation.suggested_review_note}
          </div>
        )}

        <Link href={`/alerts/${setup.id}`} style={{ textDecoration: 'none' }}>
          <div style={{ marginTop: '12px', fontSize: '12px', color: 'var(--blue)', textAlign: 'right' }}>Full detail →</div>
        </Link>
      </div>
    </Card>
  )
}
