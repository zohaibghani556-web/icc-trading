/**
 * app/backtest/page.tsx — ICC Backtest Command Center v3.0
 * 
 * Designed for TradingView-powered backtesting:
 * 1. User runs PineScript strategy on TradingView
 * 2. User enters the results from the Strategy Tester + dashboard
 * 3. Backend generates lessons, grades strategy, stores knowledge
 * 4. This page displays everything in plain English
 */
'use client'
import { useState, useEffect, useCallback } from 'react'

const API_URL = typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
  : 'http://localhost:8000'

async function request(path: string, options?: RequestInit) {
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

export default function BacktestPage() {
  const [tab, setTab] = useState<'submit' | 'results' | 'history'>('submit')
  const [submitting, setSubmitting] = useState(false)
  const [results, setResults] = useState<any>(null)
  const [history, setHistory] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [form, setForm] = useState({
    symbol: 'NQ1!', timeframe: '5', period_description: '1 year on 5m chart',
    total_trades: '', winners: '', losers: '',
    win_rate: '', profit_factor: '', total_pnl: '',
    max_drawdown: '', avg_winner: '', avg_loser: '',
    expectancy: '', max_consec_wins: '', max_consec_losses: '', grade: '',
    // Session
    london_trades: '', london_wins: '',
    ny_open_trades: '', ny_open_wins: '',
    ny_power_trades: '', ny_power_wins: '',
    // Tier
    s_trades: '', s_wins: '',
    a_trades: '', a_wins: '',
    bc_trades: '', bc_wins: '',
    // Setup
    bos_trades: '', bos_wins: '',
    fvg_trades: '', fvg_wins: '',
    choch_trades: '', choch_wins: '',
    sweep_trades: '', sweep_wins: '',
    // Config
    min_score: '40', min_rr: '2.0', atr_stop_mult: '1.5',
    rsi_min: '40', rsi_max: '75',
    notes: '',
  })

  const set = (k: string) => (e: React.ChangeEvent<any>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  const loadHistory = useCallback(async () => {
    try {
      const data = await request('/backtest/results')
      setHistory(data)
    } catch (e) { console.error(e) }
  }, [])

  useEffect(() => { loadHistory() }, [loadHistory])

  const submit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const payload: any = {
        symbol: form.symbol,
        timeframe: form.timeframe,
        period_description: form.period_description,
        total_trades: parseInt(form.total_trades) || 0,
        winners: parseInt(form.winners) || 0,
        losers: parseInt(form.losers) || 0,
        win_rate: parseFloat(form.win_rate) || 0,
        profit_factor: parseFloat(form.profit_factor) || 0,
        total_pnl: parseFloat(form.total_pnl) || 0,
        max_drawdown: parseFloat(form.max_drawdown) || 0,
        avg_winner: parseFloat(form.avg_winner) || 0,
        avg_loser: parseFloat(form.avg_loser) || 0,
        expectancy: parseFloat(form.expectancy) || 0,
        max_consec_wins: parseInt(form.max_consec_wins) || 0,
        max_consec_losses: parseInt(form.max_consec_losses) || 0,
        grade: form.grade || 'N/A',
        min_score: parseInt(form.min_score) || 40,
        min_rr: parseFloat(form.min_rr) || 2.0,
        atr_stop_mult: parseFloat(form.atr_stop_mult) || 1.5,
        rsi_min: parseInt(form.rsi_min) || 40,
        rsi_max: parseInt(form.rsi_max) || 75,
        notes: form.notes,
      }

      // Sessions
      if (form.london_trades) payload.london = { trades: parseInt(form.london_trades) || 0, wins: parseInt(form.london_wins) || 0 }
      if (form.ny_open_trades) payload.ny_open = { trades: parseInt(form.ny_open_trades) || 0, wins: parseInt(form.ny_open_wins) || 0 }
      if (form.ny_power_trades) payload.ny_power = { trades: parseInt(form.ny_power_trades) || 0, wins: parseInt(form.ny_power_wins) || 0 }

      // Tiers
      if (form.s_trades) payload.s_tier = { trades: parseInt(form.s_trades) || 0, wins: parseInt(form.s_wins) || 0 }
      if (form.a_trades) payload.a_tier = { trades: parseInt(form.a_trades) || 0, wins: parseInt(form.a_wins) || 0 }
      if (form.bc_trades) payload.bc_tier = { trades: parseInt(form.bc_trades) || 0, wins: parseInt(form.bc_wins) || 0 }

      // Setups
      if (form.bos_trades) payload.bos = { trades: parseInt(form.bos_trades) || 0, wins: parseInt(form.bos_wins) || 0 }
      if (form.fvg_trades) payload.fvg = { trades: parseInt(form.fvg_trades) || 0, wins: parseInt(form.fvg_wins) || 0 }
      if (form.choch_trades) payload.choch = { trades: parseInt(form.choch_trades) || 0, wins: parseInt(form.choch_wins) || 0 }
      if (form.sweep_trades) payload.liq_sweep = { trades: parseInt(form.sweep_trades) || 0, wins: parseInt(form.sweep_wins) || 0 }

      const data = await request('/backtest/submit', {
        method: 'POST',
        body: JSON.stringify(payload),
      })

      setResults(data)
      setTab('results')
      loadHistory()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const loadRun = async (runId: string) => {
    try {
      const data = await request(`/backtest/results/${runId}`)
      setResults({
        grade: data.grade,
        executive_summary: data.executive_summary,
        lessons: data.lessons,
        recommendations: data.recommendations,
        by_session: data.knowledge?.sessions || data.results?.by_session,
        by_tier: data.knowledge?.tiers || data.results?.by_tier,
        by_setup: data.knowledge?.setups || data.results?.by_setup,
      })
      setTab('results')
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#080a0f', color: '#e8eaf0', fontFamily: "'IBM Plex Mono', 'Inter', monospace" }}>
      {/* Header */}
      <div style={{ padding: '20px 28px', borderBottom: '1px solid #151a28' }}>
        <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: '0.08em' }}>
          ICC<span style={{ color: '#00ff88' }}>.</span>BACKTEST
          <span style={{ fontSize: 11, color: '#2a3050', marginLeft: 12 }}>TRADINGVIEW-POWERED v3.0</span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #151a28', padding: '0 28px' }}>
        {(['submit', 'results', 'history'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '10px 18px', fontSize: 11, letterSpacing: '0.08em',
            background: 'none', border: 'none', cursor: 'pointer',
            color: tab === t ? '#00ff88' : '#2a3050',
            borderBottom: tab === t ? '2px solid #00ff88' : '2px solid transparent',
            textTransform: 'uppercase',
          }}>{t === 'submit' ? 'Enter Results' : t}</button>
        ))}
      </div>

      <div style={{ padding: '24px 28px', maxWidth: 1300, margin: '0 auto' }}>

        {/* ═══ SUBMIT TAB ═══ */}
        {tab === 'submit' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 20 }}>
            <div>
              {/* Instructions */}
              <Panel title="HOW TO USE">
                <div style={{ fontSize: 12, color: '#5a6080', lineHeight: 1.8 }}>
                  <div style={{ marginBottom: 6 }}><span style={{ color: '#00ff88' }}>1.</span> <span style={{ color: '#8892a4' }}>Add "ICC Backtest Engine v3.0" strategy to your TradingView chart</span></div>
                  <div style={{ marginBottom: 6 }}><span style={{ color: '#00ff88' }}>2.</span> <span style={{ color: '#8892a4' }}>Set chart to 5m timeframe, zoom out to 1 year (or desired period)</span></div>
                  <div style={{ marginBottom: 6 }}><span style={{ color: '#00ff88' }}>3.</span> <span style={{ color: '#8892a4' }}>Open the "Strategy Tester" tab at the bottom of TradingView</span></div>
                  <div style={{ marginBottom: 6 }}><span style={{ color: '#00ff88' }}>4.</span> <span style={{ color: '#8892a4' }}>Read the numbers from Strategy Tester + the on-chart dashboard</span></div>
                  <div style={{ marginBottom: 6 }}><span style={{ color: '#00ff88' }}>5.</span> <span style={{ color: '#8892a4' }}>Enter them below → click Submit → get analysis + lessons</span></div>
                </div>
              </Panel>

              {/* Core Stats */}
              <Panel title="CORE STATS (from Strategy Tester)" style={{ marginTop: 16 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                  <Field label="Symbol"><select value={form.symbol} onChange={set('symbol')} style={iStyle}>
                    {['NQ1!','MNQ1!','ES1!','MES1!','YM1!','CL1!','GC1!'].map(s => <option key={s}>{s}</option>)}
                  </select></Field>
                  <Field label="Timeframe"><select value={form.timeframe} onChange={set('timeframe')} style={iStyle}>
                    {['1','3','5','15','60'].map(t => <option key={t}>{t}m</option>)}
                  </select></Field>
                  <Field label="Period"><input value={form.period_description} onChange={set('period_description')} style={iStyle} /></Field>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginTop: 10 }}>
                  <Field label="Total Trades"><input type="number" value={form.total_trades} onChange={set('total_trades')} style={iStyle} placeholder="e.g. 87" /></Field>
                  <Field label="Winners"><input type="number" value={form.winners} onChange={set('winners')} style={iStyle} placeholder="e.g. 48" /></Field>
                  <Field label="Losers"><input type="number" value={form.losers} onChange={set('losers')} style={iStyle} placeholder="e.g. 39" /></Field>
                  <Field label="Win Rate %"><input type="number" value={form.win_rate} onChange={set('win_rate')} style={iStyle} placeholder="e.g. 55.2" /></Field>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginTop: 10 }}>
                  <Field label="Profit Factor"><input type="number" value={form.profit_factor} onChange={set('profit_factor')} style={iStyle} placeholder="e.g. 1.85" /></Field>
                  <Field label="Total P&L $"><input type="number" value={form.total_pnl} onChange={set('total_pnl')} style={iStyle} placeholder="e.g. 3200" /></Field>
                  <Field label="Max Drawdown $"><input type="number" value={form.max_drawdown} onChange={set('max_drawdown')} style={iStyle} placeholder="e.g. 850" /></Field>
                  <Field label="Expectancy $"><input type="number" value={form.expectancy} onChange={set('expectancy')} style={iStyle} placeholder="e.g. 36.78" /></Field>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginTop: 10 }}>
                  <Field label="Avg Winner $"><input type="number" value={form.avg_winner} onChange={set('avg_winner')} style={iStyle} placeholder="e.g. 145" /></Field>
                  <Field label="Avg Loser $"><input type="number" value={form.avg_loser} onChange={set('avg_loser')} style={iStyle} placeholder="e.g. -85" /></Field>
                  <Field label="Max Win Streak"><input type="number" value={form.max_consec_wins} onChange={set('max_consec_wins')} style={iStyle} /></Field>
                  <Field label="Max Loss Streak"><input type="number" value={form.max_consec_losses} onChange={set('max_consec_losses')} style={iStyle} /></Field>
                </div>
              </Panel>

              {/* Session Breakdown */}
              <Panel title="BY SESSION (from dashboard)" style={{ marginTop: 16 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                  <PairField label="London" t={form.london_trades} w={form.london_wins} onT={set('london_trades')} onW={set('london_wins')} />
                  <PairField label="NY Open" t={form.ny_open_trades} w={form.ny_open_wins} onT={set('ny_open_trades')} onW={set('ny_open_wins')} />
                  <PairField label="NY Power" t={form.ny_power_trades} w={form.ny_power_wins} onT={set('ny_power_trades')} onW={set('ny_power_wins')} />
                </div>
              </Panel>

              {/* Tier Breakdown */}
              <Panel title="BY TIER (from dashboard)" style={{ marginTop: 16 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                  <PairField label="S-Tier (80+)" t={form.s_trades} w={form.s_wins} onT={set('s_trades')} onW={set('s_wins')} />
                  <PairField label="A-Tier (65-79)" t={form.a_trades} w={form.a_wins} onT={set('a_trades')} onW={set('a_wins')} />
                  <PairField label="B/C-Tier (<65)" t={form.bc_trades} w={form.bc_wins} onT={set('bc_trades')} onW={set('bc_wins')} />
                </div>
              </Panel>

              {/* Setup Breakdown */}
              <Panel title="BY SETUP TYPE (from dashboard)" style={{ marginTop: 16 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <PairField label="BOS" t={form.bos_trades} w={form.bos_wins} onT={set('bos_trades')} onW={set('bos_wins')} />
                  <PairField label="FVG" t={form.fvg_trades} w={form.fvg_wins} onT={set('fvg_trades')} onW={set('fvg_wins')} />
                  <PairField label="CHoCH" t={form.choch_trades} w={form.choch_wins} onT={set('choch_trades')} onW={set('choch_wins')} />
                  <PairField label="Liq Sweep" t={form.sweep_trades} w={form.sweep_wins} onT={set('sweep_trades')} onW={set('sweep_wins')} />
                </div>
              </Panel>

              {/* Notes */}
              <Panel title="NOTES" style={{ marginTop: 16 }}>
                <textarea value={form.notes} onChange={set('notes') as any} style={{ ...iStyle, height: 60, resize: 'vertical' }} placeholder="Any observations from the backtest..." />
              </Panel>

              {/* Submit */}
              <button onClick={submit} disabled={submitting || !form.total_trades} style={{
                width: '100%', padding: 16, marginTop: 16,
                background: submitting ? '#1a2030' : '#00ff88',
                color: submitting ? '#3d4459' : '#000',
                border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 700,
                letterSpacing: '0.08em', cursor: submitting ? 'not-allowed' : 'pointer',
              }}>
                {submitting ? 'ANALYZING...' : '▶ SUBMIT & ANALYZE'}
              </button>

              {error && <div style={{ marginTop: 12, padding: 12, background: '#1a0a0f', border: '1px solid #ff335530', borderRadius: 6, fontSize: 12, color: '#ff3355' }}>{error}</div>}
            </div>

            {/* Right sidebar — config */}
            <div>
              <Panel title="STRATEGY SETTINGS USED">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <Field label="Min Score"><input type="number" value={form.min_score} onChange={set('min_score')} style={iStyle} /></Field>
                  <Field label="Min R:R"><input type="number" value={form.min_rr} onChange={set('min_rr')} style={iStyle} /></Field>
                  <Field label="ATR Stop Mult"><input type="number" value={form.atr_stop_mult} onChange={set('atr_stop_mult')} style={iStyle} /></Field>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <Field label="RSI Min"><input type="number" value={form.rsi_min} onChange={set('rsi_min')} style={iStyle} /></Field>
                    <Field label="RSI Max"><input type="number" value={form.rsi_max} onChange={set('rsi_max')} style={iStyle} /></Field>
                  </div>
                  <Field label="Grade (from dashboard)"><input value={form.grade} onChange={set('grade')} style={iStyle} placeholder="e.g. A+, B, C" /></Field>
                </div>
              </Panel>

              <Panel title="💡 TIP" style={{ marginTop: 16 }}>
                <div style={{ fontSize: 11, color: '#5a6080', lineHeight: 1.7 }}>
                  You only need to fill in the <strong style={{ color: '#8892a4' }}>core stats</strong> section. The session, tier, and setup breakdowns are optional but give much better lessons.
                  <br /><br />
                  Run the backtest on different timeframes and symbols, then compare results in the History tab to find optimal parameters.
                </div>
              </Panel>
            </div>
          </div>
        )}

        {/* ═══ RESULTS TAB ═══ */}
        {tab === 'results' && results && <ResultsView results={results} />}
        {tab === 'results' && !results && <Empty message="No results yet" sub="Submit backtest results to see analysis here." />}

        {/* ═══ HISTORY TAB ═══ */}
        {tab === 'history' && <HistoryView history={history} onSelect={loadRun} />}
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// RESULTS VIEW
// ═══════════════════════════════════════════════════════════════════════════════

function ResultsView({ results: r }: { results: any }) {
  const grade = r.grade || 'N/A'
  const gc = grade.startsWith('A') ? '#00ff88' : grade.startsWith('B') ? '#4d9fff' : grade === 'C' ? '#f5a623' : '#ff3355'
  const lessons = r.lessons || []
  const criticals = lessons.filter((l: any) => l.severity === 'critical')
  const warnings = lessons.filter((l: any) => l.severity === 'warning')
  const positives = lessons.filter((l: any) => l.severity === 'positive')

  return (
    <div>
      {/* Grade Hero */}
      <div style={{ background: 'linear-gradient(135deg, #0a0f18 0%, #0a1a0f 50%, #0a0c12 100%)', border: '1px solid #00ff8815', borderRadius: 12, padding: 28, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
          <div style={{ width: 100, height: 100, borderRadius: '50%', border: `4px solid ${gc}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <span style={{ fontSize: 36, fontWeight: 800, color: gc }}>{grade}</span>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 10, color: '#3d4459', letterSpacing: '0.15em', marginBottom: 8 }}>STRATEGY ASSESSMENT</div>
            <div style={{ fontSize: 13, color: '#8892a4', lineHeight: 1.7 }}>{r.executive_summary}</div>
          </div>
        </div>
      </div>

      {/* Lessons */}
      {criticals.length > 0 && <LessonSection title="🔴 CRITICAL — Fix These First" lessons={criticals} color="#ff3355" />}
      {warnings.length > 0 && <LessonSection title="🟡 WARNINGS — Improve These" lessons={warnings} color="#f5a623" />}
      {positives.length > 0 && <LessonSection title="🟢 STRENGTHS — Keep Doing This" lessons={positives} color="#00ff88" />}

      {/* Breakdowns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginTop: 20 }}>
        {r.by_session && Object.keys(r.by_session).length > 0 && (
          <Panel title="BY SESSION"><BTable data={r.by_session} /></Panel>
        )}
        {r.by_tier && Object.keys(r.by_tier).length > 0 && (
          <Panel title="BY TIER"><BTable data={r.by_tier} /></Panel>
        )}
        {r.by_setup && Object.keys(r.by_setup).length > 0 && (
          <Panel title="BY SETUP TYPE"><BTable data={r.by_setup} /></Panel>
        )}
      </div>

      {/* Recommendations */}
      {r.recommendations && r.recommendations.length > 0 && (
        <Panel title="ACTION ITEMS" style={{ marginTop: 20 }}>
          {r.recommendations.map((rec: string, i: number) => (
            <div key={i} style={{ fontSize: 12, color: '#8892a4', padding: '8px 12px', marginBottom: 6, background: '#0a0f18', borderRadius: 6, borderLeft: '3px solid #f5a623' }}>
              {i + 1}. {rec}
            </div>
          ))}
        </Panel>
      )}
    </div>
  )
}


function LessonSection({ title, lessons, color }: { title: string; lessons: any[]; color: string }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color, marginBottom: 10 }}>{title}</div>
      {lessons.map((l: any, i: number) => (
        <div key={i} style={{ background: '#0d1017', border: '1px solid #151a28', borderLeft: `3px solid ${color}`, borderRadius: 6, padding: '12px 16px', marginBottom: 6 }}>
          <div style={{ fontSize: 12, color: '#c8ccd5', marginBottom: 4 }}>{l.description}</div>
          <div style={{ fontSize: 11, color, fontStyle: 'italic' }}>→ {l.recommendation}</div>
        </div>
      ))}
    </div>
  )
}


function HistoryView({ history, onSelect }: { history: any[]; onSelect: (id: string) => void }) {
  if (!history.length) return <Empty message="No previous runs" sub="Submit your first backtest to start building history." />
  return (
    <div>
      <div style={{ fontSize: 11, color: '#3d4459', marginBottom: 12 }}>{history.length} BACKTEST RUNS</div>
      {history.map((r: any) => (
        <div key={r.run_id} onClick={() => onSelect(r.run_id)} style={{ background: '#0d1017', border: '1px solid #151a28', borderRadius: 8, padding: '14px 18px', marginBottom: 8, cursor: 'pointer' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontWeight: 700, fontSize: 14 }}>{r.symbol}</span>
              <span style={{ fontSize: 16, fontWeight: 800, color: r.grade?.startsWith('A') ? '#00ff88' : r.grade?.startsWith('B') ? '#4d9fff' : '#f5a623' }}>{r.grade}</span>
            </div>
            <span style={{ fontSize: 10, color: '#3d4459' }}>{r.created_at?.slice(0, 16)}</span>
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 11, color: '#5a6080' }}>
            <span>{r.total_trades} trades</span>
            <span>WR: {typeof r.win_rate === 'number' ? (r.win_rate > 1 ? r.win_rate.toFixed(1) : (r.win_rate * 100).toFixed(1)) : '—'}%</span>
            <span>PF: {r.profit_factor?.toFixed(2)}</span>
            <span>{r.lessons_count} lessons</span>
          </div>
          {r.executive_summary && <div style={{ fontSize: 10, color: '#3d4459', marginTop: 6 }}>{r.executive_summary}</div>}
        </div>
      ))}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// SHARED COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

function Panel({ title, children, style: s }: { title: string; children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ background: '#0d1017', border: '1px solid #151a28', borderRadius: 8, padding: '16px 20px', ...s }}>
      <div style={{ fontSize: 10, color: '#3d4459', letterSpacing: '0.12em', marginBottom: 12, fontWeight: 600 }}>{title}</div>
      {children}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: '#5a6080', marginBottom: 3 }}>{label}</div>
      {children}
    </div>
  )
}

function PairField({ label, t, w, onT, onW }: { label: string; t: string; w: string; onT: any; onW: any }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: '#5a6080', marginBottom: 3 }}>{label}</div>
      <div style={{ display: 'flex', gap: 4 }}>
        <input type="number" value={t} onChange={onT} style={{ ...iStyle, width: '50%' }} placeholder="Trades" />
        <input type="number" value={w} onChange={onW} style={{ ...iStyle, width: '50%' }} placeholder="Wins" />
      </div>
    </div>
  )
}

function BTable({ data }: { data: Record<string, any> }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
      <thead>
        <tr>{['', 'Trades', 'Wins', 'WR'].map(h => <th key={h} style={{ padding: '4px 4px', textAlign: 'left', color: '#3d4459', fontSize: 9, borderBottom: '1px solid #151a28' }}>{h}</th>)}</tr>
      </thead>
      <tbody>
        {Object.entries(data).map(([k, v]: [string, any]) => (
          <tr key={k}>
            <td style={{ padding: '4px', color: '#8892a4' }}>{k}</td>
            <td style={{ padding: '4px', color: '#5a6080' }}>{v.trades}</td>
            <td style={{ padding: '4px', color: '#00ff88' }}>{v.wins}</td>
            <td style={{ padding: '4px', color: v.win_rate >= 0.55 ? '#00ff88' : v.win_rate < 0.4 ? '#ff3355' : '#f5a623' }}>
              {(v.win_rate * 100).toFixed(0)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Empty({ message, sub }: { message: string; sub: string }) {
  return (
    <div style={{ textAlign: 'center', padding: 60 }}>
      <div style={{ fontSize: 14, color: '#3d4459', marginBottom: 8 }}>{message}</div>
      <div style={{ fontSize: 11, color: '#252830' }}>{sub}</div>
    </div>
  )
}

const iStyle: React.CSSProperties = {
  width: '100%', padding: '7px 10px', background: '#0a0c12',
  border: '1px solid #151a28', borderRadius: 4, color: '#c8ccd5',
  fontSize: 12, fontFamily: 'IBM Plex Mono', outline: 'none',
}
