'use client'
import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { api, SetupEvaluation, AnalyticsSummary } from '@/lib/api'

export default function DashboardPage() {
  const [setups, setSetups] = useState<SetupEvaluation[]>([])
  const [stats, setStats] = useState<AnalyticsSummary | null>(null)
  const [selected, setSelected] = useState<SetupEvaluation | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  const load = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([api.alerts.recent({}), api.analytics.summary()])
      setSetups(s)
      setStats(a)
      setLastUpdate(new Date())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [load])

  useEffect(() => {
    if (!selected && setups.length > 0) {
      const best = setups.find(s => s.verdict === 'valid_trade') || setups[0]
      setSelected(best)
    }
  }, [setups])

  const validSetups = setups.filter(s => s.verdict === 'valid_trade')
  const watchSetups = setups.filter(s => s.verdict === 'watch_only')
  const latestValid = validSetups[0]

  return (
    <div style={{ minHeight: '100vh', background: '#080a0f', color: '#e8eaf0', fontFamily: "'IBM Plex Mono', monospace" }}>
      
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 24px', borderBottom: '1px solid #1a1f2e',
        background: '#0a0c12',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ fontSize: '16px', fontWeight: 700, color: '#fff', letterSpacing: '0.1em' }}>
            ICC<span style={{ color: '#00ff88' }}>.</span>ELITE
          </div>
          <div style={{ fontSize: '11px', color: '#3d4459', letterSpacing: '0.05em' }}>DECISION ENGINE v1.0</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px', fontSize: '11px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#00ff88', animation: 'pulse 2s infinite' }} />
            <span style={{ color: '#3d4459' }}>LIVE</span>
          </div>
          <span style={{ color: '#3d4459' }}>Updated {lastUpdate ? lastUpdate.toLocaleTimeString() : "--:--:--"}</span>
          <button onClick={load} style={{ background: 'none', border: '1px solid #1a1f2e', color: '#3d4459', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '11px' }}>
            ↻ REFRESH
          </button>
        </div>
      </div>

      {/* Nav */}
      <div style={{ display: 'flex', gap: '0', borderBottom: '1px solid #1a1f2e', padding: '0 24px', background: '#0a0c12' }}>
        {[
          { href: '/', label: 'DASHBOARD' },
          { href: '/alerts', label: 'SIGNALS' },
          { href: '/paper-trading', label: 'PAPER TRADE' },
          { href: '/journal', label: 'JOURNAL' },
          { href: '/analytics', label: 'ANALYTICS' },
          { href: '/settings', label: 'SETTINGS' },
        ].map(item => (
          <Link key={item.href} href={item.href} style={{
            padding: '10px 16px', fontSize: '11px', color: '#3d4459',
            textDecoration: 'none', letterSpacing: '0.08em',
            borderBottom: item.href === '/' ? '2px solid #00ff88' : '2px solid transparent',
            color: item.href === '/' ? '#00ff88' : '#3d4459',
          }}>{item.label}</Link>
        ))}
      </div>

      <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
        
        {/* Hero: Latest valid trade */}
        {latestValid && (
          <div style={{
            background: 'linear-gradient(135deg, #0a1a0f 0%, #0a0c12 50%, #0a0f1a 100%)',
            border: '1px solid #00ff8820',
            borderRadius: '12px',
            padding: '28px',
            marginBottom: '24px',
            position: 'relative',
            overflow: 'hidden',
          }}>
            <div style={{
              position: 'absolute', top: 0, right: 0,
              width: '300px', height: '300px',
              background: 'radial-gradient(circle, #00ff8808 0%, transparent 70%)',
              pointerEvents: 'none',
            }} />
            
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}>
              <div>
                <div style={{ fontSize: '11px', color: '#00ff88', letterSpacing: '0.15em', marginBottom: '8px' }}>
                  ◆ LATEST VALID TRADE SIGNAL
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '12px' }}>
                  <span style={{ fontSize: '32px', fontWeight: 700, color: '#fff', letterSpacing: '0.05em' }}>
                    {latestValid.symbol}
                  </span>
                  <span style={{
                    fontSize: '13px', fontWeight: 600, padding: '4px 12px', borderRadius: '4px',
                    background: latestValid.direction === 'bullish' ? '#00ff8820' : '#ff003320',
                    color: latestValid.direction === 'bullish' ? '#00ff88' : '#ff3355',
                    border: `1px solid ${latestValid.direction === 'bullish' ? '#00ff8840' : '#ff335540'}`,
                    letterSpacing: '0.08em',
                  }}>
                    {latestValid.direction === 'bullish' ? '▲ LONG' : '▼ SHORT'}
                  </span>
                  <span style={{ fontSize: '11px', color: '#3d4459' }}>{latestValid.timeframe}M CHART</span>
                </div>
                <div style={{ fontSize: '13px', color: '#8892a4', lineHeight: 1.6, maxWidth: '500px' }}>
                  {latestValid.explanation?.summary || 'Valid ICC setup detected. All criteria met.'}
                </div>
              </div>

              {/* Score ring */}
              <div style={{ textAlign: 'center' }}>
                <ScoreRing score={latestValid.confidence_score} size={90} />
                <div style={{ fontSize: '10px', color: '#3d4459', marginTop: '6px', letterSpacing: '0.08em' }}>
                  {getTier(latestValid.confidence_score)}-TIER
                </div>
              </div>
            </div>

            {/* Trade levels */}
            {latestValid.entry_price && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1px', background: '#1a1f2e', borderRadius: '8px', overflow: 'hidden', marginTop: '20px' }}>
                {[
                  { label: '📍 ENTRY', value: latestValid.entry_price?.toFixed(2), color: '#4d9fff', bg: '#0a1525' },
                  { label: '🛑 STOP LOSS', value: latestValid.stop_price?.toFixed(2), color: '#ff3355', bg: '#150a0f' },
                  { label: '🎯 TARGET 1', value: latestValid.target_price?.toFixed(2), color: '#00ff88', bg: '#0a1510' },
                  { label: '📊 RISK/REWARD', value: latestValid.risk_reward ? `${latestValid.risk_reward}:1` : '—', color: '#f5a623', bg: '#151008' },
                ].map(item => (
                  <div key={item.label} style={{ padding: '16px', background: item.bg, textAlign: 'center' }}>
                    <div style={{ fontSize: '10px', color: '#3d4459', marginBottom: '6px', letterSpacing: '0.08em' }}>{item.label}</div>
                    <div style={{ fontSize: '22px', fontWeight: 700, color: item.color }}>{item.value || '—'}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Action button */}
            <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
              <Link href="/paper-trading" style={{
                display: 'inline-block', padding: '10px 24px',
                background: '#00ff88', color: '#000',
                borderRadius: '6px', textDecoration: 'none',
                fontSize: '12px', fontWeight: 700, letterSpacing: '0.08em',
              }}>
                → LOG PAPER TRADE
              </Link>
              <button onClick={() => setSelected(latestValid)} style={{
                padding: '10px 20px', background: 'none',
                border: '1px solid #1a1f2e', color: '#8892a4',
                borderRadius: '6px', cursor: 'pointer',
                fontSize: '12px', letterSpacing: '0.08em',
              }}>
                VIEW FULL ANALYSIS
              </button>
            </div>
          </div>
        )}

        {/* Stats row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px', marginBottom: '24px' }}>
          {[
            { label: 'VALID SIGNALS TODAY', value: validSetups.length, color: '#00ff88' },
            { label: 'WATCHING', value: watchSetups.length, color: '#f5a623' },
            { label: 'PAPER TRADES', value: stats?.total_trades ?? 0, color: '#4d9fff' },
            { label: 'WIN RATE', value: stats?.total_trades ? `${Math.round(stats.win_rate * 100)}%` : '—', color: stats?.win_rate >= 0.5 ? '#00ff88' : '#ff3355' },
            { label: 'EXPECTANCY', value: stats?.total_trades ? `${stats.expectancy_r > 0 ? '+' : ''}${stats.expectancy_r}R` : '—', color: stats?.expectancy_r > 0 ? '#00ff88' : '#ff3355' },
          ].map(item => (
            <div key={item.label} style={{ background: '#0d1017', border: '1px solid #1a1f2e', borderRadius: '8px', padding: '16px' }}>
              <div style={{ fontSize: '10px', color: '#3d4459', letterSpacing: '0.1em', marginBottom: '8px' }}>{item.label}</div>
              <div style={{ fontSize: '24px', fontWeight: 700, color: item.color }}>{item.value}</div>
            </div>
          ))}
        </div>

        {/* Signal feed + detail */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 420px', gap: '16px' }}>
          
          {/* Signal feed */}
          <div style={{ background: '#0d1017', border: '1px solid #1a1f2e', borderRadius: '8px', overflow: 'hidden' }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid #1a1f2e', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '11px', letterSpacing: '0.1em', color: '#8892a4' }}>SIGNAL FEED</span>
              <span style={{ fontSize: '10px', color: '#3d4459' }}>{setups.length} signals</span>
            </div>

            {/* Table header */}
            <div style={{
              display: 'grid', gridTemplateColumns: '80px 70px 100px 80px 80px 1fr',
              gap: '8px', padding: '8px 20px',
              fontSize: '10px', color: '#3d4459', letterSpacing: '0.08em',
              borderBottom: '1px solid #1a1f2e',
            }}>
              {['SYMBOL', 'DIR', 'VERDICT', 'SCORE', 'TIER', 'SUMMARY'].map(h => <span key={h}>{h}</span>)}
            </div>

            {loading && (
              <div style={{ padding: '40px', textAlign: 'center', color: '#3d4459', fontSize: '12px' }}>
                LOADING SIGNALS...
              </div>
            )}

            {!loading && setups.length === 0 && (
              <div style={{ padding: '60px', textAlign: 'center' }}>
                <div style={{ fontSize: '13px', color: '#3d4459', marginBottom: '8px' }}>NO SIGNALS YET</div>
                <div style={{ fontSize: '11px', color: '#252830' }}>Waiting for TradingView alerts...</div>
              </div>
            )}

            {setups.slice(0, 20).map(s => {
              const score = Math.round(s.confidence_score * 100)
              const tier = getTier(s.confidence_score)
              const isSelected = selected?.id === s.id
              return (
                <div key={s.id} onClick={() => setSelected(s)} style={{
                  display: 'grid', gridTemplateColumns: '80px 70px 100px 80px 80px 1fr',
                  gap: '8px', padding: '12px 20px',
                  borderBottom: '1px solid #0d1017',
                  cursor: 'pointer',
                  background: isSelected ? '#0a1525' : 'transparent',
                  borderLeft: isSelected ? '2px solid #4d9fff' : '2px solid transparent',
                  transition: 'background 0.15s',
                }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: '#fff' }}>{s.symbol}</span>
                  <span style={{
                    fontSize: '11px', fontWeight: 600,
                    color: s.direction === 'bullish' ? '#00ff88' : '#ff3355',
                  }}>
                    {s.direction === 'bullish' ? '▲ LONG' : '▼ SHORT'}
                  </span>
                  <VerdictBadge verdict={s.verdict} />
                  <span style={{ fontSize: '12px', color: scoreColor(s.confidence_score) }}>
                    {score}/100
                  </span>
                  <span style={{
                    fontSize: '11px', fontWeight: 700,
                    color: tier === 'S' ? '#00ff88' : tier === 'A' ? '#4d9fff' : '#f5a623',
                  }}>
                    {tier}-TIER
                  </span>
                  <span style={{ fontSize: '11px', color: '#3d4459', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s.explanation?.summary?.slice(0, 50) || '—'}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Detail panel */}
          <div>
            {selected ? <SignalDetail setup={selected} /> : (
              <div style={{ background: '#0d1017', border: '1px solid #1a1f2e', borderRadius: '8px', padding: '40px', textAlign: 'center' }}>
                <div style={{ fontSize: '12px', color: '#3d4459' }}>SELECT A SIGNAL TO VIEW DETAILS</div>
              </div>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        * { box-sizing: border-box; }
      `}</style>
    </div>
  )
}

function SignalDetail({ setup }: { setup: SetupEvaluation }) {
  const isLong = setup.direction === 'bullish'
  const dirColor = isLong ? '#00ff88' : '#ff3355'
  const entry = setup.entry_price
  const stop = setup.stop_price
  const target = setup.target_price
  const rr = setup.risk_reward
  const score = Math.round(setup.confidence_score * 100)
  const tier = getTier(setup.confidence_score)
  const exp = setup.explanation || {}

  const riskPts = entry && stop ? Math.abs(entry - stop) : 0
  const mnqRisk = Math.round(riskPts * 2)

  const phases = [
    { key: 'environment', label: 'ENV' },
    { key: 'indication', label: 'IND' },
    { key: 'correction', label: 'COR' },
    { key: 'continuation', label: 'CON' },
    { key: 'risk', label: 'RISK' },
  ]

  return (
    <div style={{ background: '#0d1017', border: '1px solid #1a1f2e', borderRadius: '8px', overflow: 'hidden' }}>
      
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        background: isLong ? '#0a1a0f' : '#1a0a0f',
        borderBottom: `1px solid ${dirColor}30`,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '18px', fontWeight: 700, color: '#fff' }}>{setup.symbol}</span>
            <span style={{ fontSize: '12px', color: dirColor, fontWeight: 600 }}>
              {isLong ? '▲ LONG' : '▼ SHORT'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ScoreRing score={setup.confidence_score} size={52} />
            <VerdictBadge verdict={setup.verdict} />
          </div>
        </div>
        <div style={{ fontSize: '12px', color: '#8892a4', lineHeight: 1.5 }}>
          {exp.summary || 'Evaluating setup...'}
        </div>
      </div>

      {/* Levels */}
      {entry && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1px', background: '#1a1f2e' }}>
          {[
            { label: 'ENTRY', value: entry.toFixed(2), color: '#4d9fff' },
            { label: 'STOP', value: stop?.toFixed(2) || '—', color: '#ff3355' },
            { label: 'TARGET', value: target?.toFixed(2) || '—', color: '#00ff88' },
          ].map(item => (
            <div key={item.label} style={{ padding: '12px', background: '#0d1017', textAlign: 'center' }}>
              <div style={{ fontSize: '9px', color: '#3d4459', letterSpacing: '0.1em', marginBottom: '4px' }}>{item.label}</div>
              <div style={{ fontSize: '17px', fontWeight: 700, color: item.color }}>{item.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* RR + dollar risk */}
      {entry && (
        <div style={{ padding: '10px 16px', background: '#0a0c12', display: 'flex', gap: '20px', fontSize: '11px', borderBottom: '1px solid #1a1f2e' }}>
          <span style={{ color: '#3d4459' }}>RR: <strong style={{ color: '#f5a623' }}>{rr ? `${rr}:1` : '—'}</strong></span>
          <span style={{ color: '#3d4459' }}>MNQ Risk: <strong style={{ color: '#ff3355' }}>${mnqRisk}</strong></span>
          <span style={{ color: '#3d4459' }}>Tier: <strong style={{ color: tier === 'S' ? '#00ff88' : tier === 'A' ? '#4d9fff' : '#f5a623' }}>{tier}</strong></span>
        </div>
      )}

      {/* Phase scores */}
      <div style={{ padding: '14px 16px', borderBottom: '1px solid #1a1f2e' }}>
        <div style={{ fontSize: '10px', color: '#3d4459', letterSpacing: '0.1em', marginBottom: '10px' }}>ICC PHASE SCORES</div>
        {phases.map(p => {
          const phase = setup.score_breakdown?.[p.key]
          if (!phase) return null
          const s = phase.score
          return (
            <div key={p.key} style={{ marginBottom: '7px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                <span style={{ fontSize: '11px', color: '#8892a4' }}>{p.label}</span>
                <span style={{ fontSize: '11px', color: scoreColor(s / 100) }}>{s}</span>
              </div>
              <div style={{ height: '3px', background: '#1a1f2e', borderRadius: '2px' }}>
                <div style={{ height: '100%', width: `${s}%`, background: scoreColor(s / 100), borderRadius: '2px', transition: 'width 0.4s' }} />
              </div>
            </div>
          )
        })}
      </div>

      {/* ICC components */}
      <div style={{ padding: '14px 16px', borderBottom: '1px solid #1a1f2e' }}>
        <div style={{ fontSize: '10px', color: '#3d4459', letterSpacing: '0.1em', marginBottom: '10px' }}>DETECTED COMPONENTS</div>
        {[
          { label: 'Indication', value: setup.indication_type },
          { label: 'Correction', value: setup.correction_zone_type },
          { label: 'Continuation', value: setup.continuation_trigger_type },
        ].map(item => item.value && (
          <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', color: '#3d4459' }}>{item.label}</span>
            <span style={{ fontSize: '11px', color: '#8892a4', fontFamily: 'IBM Plex Mono' }}>
              {item.value.replace(/_/g, ' ')}
            </span>
          </div>
        ))}
        {setup.has_htf_alignment && (
          <div style={{ fontSize: '10px', color: '#00ff88', marginTop: '6px' }}>✓ HTF ALIGNED</div>
        )}
        {setup.is_countertrend && (
          <div style={{ fontSize: '10px', color: '#f5a623', marginTop: '4px' }}>⚠ COUNTERTREND</div>
        )}
      </div>

      {/* How to execute */}
      {setup.verdict === 'valid_trade' && entry && (
        <div style={{ padding: '14px 16px' }}>
          <div style={{ fontSize: '10px', color: '#3d4459', letterSpacing: '0.1em', marginBottom: '10px' }}>HOW TO EXECUTE</div>
          {[
            { n: '1', text: `Open Tradovate → Paper Trading mode`, color: '#4d9fff' },
            { n: '2', text: `Place ${isLong ? 'BUY' : 'SELL'} Limit at ${entry.toFixed(2)} — 1 contract`, color: dirColor },
            { n: '3', text: `Set Stop Loss at ${stop?.toFixed(2)} immediately after entry`, color: '#ff3355' },
            { n: '4', text: `Set Take Profit at ${target?.toFixed(2)} — lock in your gain`, color: '#00ff88' },
            { n: '5', text: `Walk away. Max loss: $${mnqRisk} on 1 MNQ`, color: '#f5a623' },
          ].map(step => (
            <div key={step.n} style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
              <div style={{
                width: '20px', height: '20px', borderRadius: '50%', flexShrink: 0,
                background: step.color, display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '10px', fontWeight: 700, color: '#000',
              }}>{step.n}</div>
              <div style={{ fontSize: '11px', color: '#8892a4', lineHeight: 1.5 }}>{step.text}</div>
            </div>
          ))}
          <Link href="/paper-trading" style={{
            display: 'block', textAlign: 'center', padding: '10px',
            background: '#00ff88', color: '#000', borderRadius: '6px',
            textDecoration: 'none', fontSize: '12px', fontWeight: 700,
            letterSpacing: '0.08em', marginTop: '8px',
          }}>
            → LOG THIS TRADE
          </Link>
        </div>
      )}

      {setup.verdict !== 'valid_trade' && (
        <div style={{ padding: '14px 16px' }}>
          <div style={{ fontSize: '11px', color: '#f5a623', background: '#151008', padding: '12px', borderRadius: '6px', border: '1px solid #f5a62320' }}>
            {setup.verdict === 'watch_only'
              ? '👁 WATCH ONLY — Monitor this setup. Wait for continuation confirmation before entering.'
              : '🚫 INVALID SETUP — Do not trade. Not all ICC criteria are met.'}
          </div>
        </div>
      )}
    </div>
  )
}

function ScoreRing({ score, size = 60 }: { score: number; size?: number }) {
  const pct = Math.round(score <= 1 ? score * 100 : score)
  const color = pct >= 80 ? '#00ff88' : pct >= 65 ? '#4d9fff' : pct >= 50 ? '#f5a623' : '#ff3355'
  const r = size / 2 - 4
  const circ = 2 * Math.PI * r
  const dash = (Math.min(pct, 100) / 100) * circ
  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#1a1f2e" strokeWidth="3" />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="3"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: size > 70 ? '16px' : '11px', fontWeight: 700, color,
      }}>{pct}</div>
    </div>
  )
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const map: Record<string, { label: string; color: string; bg: string }> = {
    valid_trade:   { label: 'VALID',   color: '#00ff88', bg: '#00ff8815' },
    watch_only:    { label: 'WATCH',   color: '#f5a623', bg: '#f5a62315' },
    invalid_setup: { label: 'INVALID', color: '#ff3355', bg: '#ff335515' },
  }
  const s = map[verdict] || { label: verdict.toUpperCase(), color: '#8892a4', bg: '#1a1f2e' }
  return (
    <span style={{
      fontSize: '10px', fontWeight: 700, padding: '3px 8px', borderRadius: '3px',
      color: s.color, background: s.bg, letterSpacing: '0.06em',
    }}>{s.label}</span>
  )
}

function getTier(score: number): string {
  const pct = score <= 1 ? score * 100 : score
  return pct >= 80 ? 'S' : pct >= 65 ? 'A' : pct >= 50 ? 'B' : 'C'
}

function scoreColor(score: number): string {
  const pct = score <= 1 ? score * 100 : score
  return pct >= 80 ? '#00ff88' : pct >= 65 ? '#4d9fff' : pct >= 50 ? '#f5a623' : '#ff3355'
}
