/**
 * app/backtest/page.tsx — ICC Backtest Command Center
 * 
 * Full backtest dashboard with:
 * - Run configuration panel
 * - Live status tracking
 * - Results with equity curve, breakdowns, lessons
 * - Plain English report
 * - Historical run comparison
 */
'use client'
import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'

type BacktestStatus = 'idle' | 'running' | 'complete' | 'failed'

export default function BacktestPage() {
  const [status, setStatus] = useState<BacktestStatus>('idle')
  const [runId, setRunId] = useState<string | null>(null)
  const [results, setResults] = useState<any>(null)
  const [history, setHistory] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)
  const [selectedRun, setSelectedRun] = useState<any>(null)
  const [tab, setTab] = useState<'run' | 'results' | 'lessons' | 'trades' | 'history'>('run')

  // Config
  const [config, setConfig] = useState({
    symbol: 'NQ', days: 60, min_rr: 2.0, min_score: 40,
    require_4h_bias: false, require_volume: false,
    rsi_min: 40, rsi_max: 75, atr_stop_mult: 1.5,
    t2_rr: 3.0, t3_rr: 5.0, session_filter: 'all',
  })

  const loadHistory = useCallback(async () => {
    try {
      const data = await request('/backtest/results')
      setHistory(data)
    } catch (e) { console.error(e) }
  }, [])

  useEffect(() => { loadHistory() }, [loadHistory])

  // Poll for results
  useEffect(() => {
    if (status !== 'running' || !runId) return
    const interval = setInterval(async () => {
      try {
        const data = await request(`/backtest/status/${runId}`)
        if (data.status === 'complete') {
          setResults(data.results)
          setStatus('complete')
          setTab('results')
          loadHistory()
        } else if (data.status === 'failed') {
          setError(data.error || 'Backtest failed')
          setStatus('failed')
        }
      } catch (e) { console.error(e) }
    }, 2000)
    return () => clearInterval(interval)
  }, [status, runId, loadHistory])

  const startBacktest = async () => {
    setStatus('running')
    setError(null)
    setResults(null)
    try {
      const params = new URLSearchParams({
        symbol: config.symbol, days: String(config.days),
        min_rr: String(config.min_rr), min_score: String(config.min_score),
        require_4h_bias: String(config.require_4h_bias),
        require_volume: String(config.require_volume),
        rsi_min: String(config.rsi_min), rsi_max: String(config.rsi_max),
        atr_stop_mult: String(config.atr_stop_mult),
        t2_rr: String(config.t2_rr), t3_rr: String(config.t3_rr),
        session_filter: config.session_filter,
      })
      const data = await request(`/backtest/run?${params}`, { method: 'POST' })
      setRunId(data.run_id)
    } catch (e: any) {
      setError(e.message || 'Failed to start backtest')
      setStatus('failed')
    }
  }

  const loadRun = async (rid: string) => {
    try {
      const data = await request(`/backtest/status/${rid}`)
      if (data.status === 'complete') {
        setResults(data.results)
        setStatus('complete')
        setTab('results')
      }
    } catch (e) { console.error(e) }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#080a0f', color: '#e8eaf0', fontFamily: "'IBM Plex Mono', 'Inter', monospace" }}>
      {/* Header */}
      <div style={{ padding: '20px 28px', borderBottom: '1px solid #151a28', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: '18px', fontWeight: 700, letterSpacing: '0.08em' }}>
            ICC<span style={{ color: '#00ff88' }}>.</span>BACKTEST
            <span style={{ fontSize: '11px', color: '#2a3050', marginLeft: 12 }}>LEARNING ENGINE v3.0</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {status === 'running' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#f5a623' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#f5a623', animation: 'pulse 1s infinite' }} />
              ANALYZING...
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #151a28', padding: '0 28px' }}>
        {(['run', 'results', 'lessons', 'trades', 'history'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '10px 18px', fontSize: 11, letterSpacing: '0.08em',
            background: 'none', border: 'none', cursor: 'pointer',
            color: tab === t ? '#00ff88' : '#2a3050',
            borderBottom: tab === t ? '2px solid #00ff88' : '2px solid transparent',
            textTransform: 'uppercase',
          }}>{t === 'run' ? 'Configure & Run' : t}</button>
        ))}
      </div>

      <div style={{ padding: '24px 28px', maxWidth: 1400, margin: '0 auto' }}>

        {/* ═══ TAB: CONFIGURE & RUN ═══ */}
        {tab === 'run' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            <Panel title="BACKTEST CONFIGURATION">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <Field label="Symbol">
                  <select value={config.symbol} onChange={e => setConfig(c => ({ ...c, symbol: e.target.value }))} style={selectStyle}>
                    {['NQ', 'ES', 'YM', 'CL', 'GC'].map(s => <option key={s}>{s}</option>)}
                  </select>
                </Field>
                <Field label="Period (days)">
                  <select value={config.days} onChange={e => setConfig(c => ({ ...c, days: +e.target.value }))} style={selectStyle}>
                    {[7, 14, 30, 60, 90, 180, 365].map(d => <option key={d} value={d}>{d} days</option>)}
                  </select>
                </Field>
                <Field label="Min Score">
                  <input type="number" value={config.min_score} onChange={e => setConfig(c => ({ ...c, min_score: +e.target.value }))} style={inputStyle} />
                </Field>
                <Field label="Min R:R">
                  <input type="number" value={config.min_rr} step={0.5} onChange={e => setConfig(c => ({ ...c, min_rr: +e.target.value }))} style={inputStyle} />
                </Field>
                <Field label="ATR Stop Mult">
                  <input type="number" value={config.atr_stop_mult} step={0.1} onChange={e => setConfig(c => ({ ...c, atr_stop_mult: +e.target.value }))} style={inputStyle} />
                </Field>
                <Field label="RSI Range">
                  <div style={{ display: 'flex', gap: 6 }}>
                    <input type="number" value={config.rsi_min} onChange={e => setConfig(c => ({ ...c, rsi_min: +e.target.value }))} style={{ ...inputStyle, width: '50%' }} placeholder="Min" />
                    <input type="number" value={config.rsi_max} onChange={e => setConfig(c => ({ ...c, rsi_max: +e.target.value }))} style={{ ...inputStyle, width: '50%' }} placeholder="Max" />
                  </div>
                </Field>
                <Field label="Session">
                  <select value={config.session_filter} onChange={e => setConfig(c => ({ ...c, session_filter: e.target.value }))} style={selectStyle}>
                    <option value="all">All Sessions</option>
                    <option value="ny_open">NY Open</option>
                    <option value="london">London</option>
                    <option value="ny_power">NY Power Hour</option>
                    <option value="overlap">London/NY Overlap</option>
                  </select>
                </Field>
                <Field label="Target 2 RR">
                  <input type="number" value={config.t2_rr} step={0.5} onChange={e => setConfig(c => ({ ...c, t2_rr: +e.target.value }))} style={inputStyle} />
                </Field>
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                <Toggle label="Require 4H Bias" checked={config.require_4h_bias}
                  onChange={v => setConfig(c => ({ ...c, require_4h_bias: v }))} />
                <Toggle label="Require Volume" checked={config.require_volume}
                  onChange={v => setConfig(c => ({ ...c, require_volume: v }))} />
              </div>

              <button onClick={startBacktest} disabled={status === 'running'} style={{
                width: '100%', padding: '14px', marginTop: 20,
                background: status === 'running' ? '#1a2030' : '#00ff88',
                color: status === 'running' ? '#3d4459' : '#000',
                border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 700,
                letterSpacing: '0.08em', cursor: status === 'running' ? 'not-allowed' : 'pointer',
              }}>
                {status === 'running' ? '⏳ RUNNING BACKTEST...' : '▶ RUN BACKTEST'}
              </button>

              {error && (
                <div style={{ marginTop: 12, padding: 12, background: '#1a0a0f', border: '1px solid #ff335530', borderRadius: 6, fontSize: 12, color: '#ff3355' }}>
                  {error}
                </div>
              )}
            </Panel>

            <Panel title="WHAT THIS DOES">
              <div style={{ fontSize: 12, color: '#5a6080', lineHeight: 1.8 }}>
                <p style={{ marginBottom: 12 }}>The ICC Learning Backtester simulates your exact strategy on historical data, then <strong style={{ color: '#8892a4' }}>learns from every trade</strong> to make the live engine smarter.</p>
                <div style={{ marginBottom: 8 }}>
                  <span style={{ color: '#00ff88' }}>1.</span> <span style={{ color: '#8892a4' }}>Fetches real market data from Yahoo Finance</span>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <span style={{ color: '#00ff88' }}>2.</span> <span style={{ color: '#8892a4' }}>Computes ALL indicators (EMAs, RSI, MACD, VWAP, ATR, volume)</span>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <span style={{ color: '#00ff88' }}>3.</span> <span style={{ color: '#8892a4' }}>Runs the ICC composite scorer on every bar</span>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <span style={{ color: '#00ff88' }}>4.</span> <span style={{ color: '#8892a4' }}>Simulates entries, stops, and targets with MFE/MAE tracking</span>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <span style={{ color: '#00ff88' }}>5.</span> <span style={{ color: '#8892a4' }}>Analyzes patterns: what works, what fails, and WHY</span>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <span style={{ color: '#00ff88' }}>6.</span> <span style={{ color: '#8892a4' }}>Stores lessons in the Knowledge Base for live signal reference</span>
                </div>
                <div style={{ marginTop: 16, padding: 12, background: '#0a1510', borderRadius: 6, border: '1px solid #00ff8820' }}>
                  <div style={{ fontSize: 10, color: '#00ff88', letterSpacing: '0.1em', marginBottom: 6 }}>💡 SELF-IMPROVING</div>
                  <div style={{ fontSize: 11, color: '#8892a4' }}>Every backtest run adds to the knowledge base. Live signals are scored with backtest-learned adjustments — the system gets smarter over time.</div>
                </div>
              </div>
            </Panel>
          </div>
        )}

        {/* ═══ TAB: RESULTS ═══ */}
        {tab === 'results' && results && (
          <ResultsView results={results} />
        )}
        {tab === 'results' && !results && (
          <EmptyPanel message="No results yet" sub="Run a backtest to see results here." />
        )}

        {/* ═══ TAB: LESSONS ═══ */}
        {tab === 'lessons' && results && (
          <LessonsView results={results} />
        )}
        {tab === 'lessons' && !results && (
          <EmptyPanel message="No lessons yet" sub="Lessons are generated after a backtest completes." />
        )}

        {/* ═══ TAB: TRADES ═══ */}
        {tab === 'trades' && results && (
          <TradesView trades={results.trades || []} />
        )}

        {/* ═══ TAB: HISTORY ═══ */}
        {tab === 'history' && (
          <HistoryView history={history} onSelect={(rid) => loadRun(rid)} />
        )}
      </div>

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
      `}</style>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// RESULTS VIEW
// ═══════════════════════════════════════════════════════════════════════════════

function ResultsView({ results: r }: { results: any }) {
  const grade = r.grade || 'N/A'
  const gradeColor = grade.startsWith('A') ? '#00ff88' : grade.startsWith('B') ? '#4d9fff' : grade === 'C' ? '#f5a623' : '#ff3355'

  return (
    <div>
      {/* Grade + Summary Hero */}
      <div style={{
        background: 'linear-gradient(135deg, #0a0f18 0%, #0a1a0f 50%, #0a0c12 100%)',
        border: '1px solid #00ff8815', borderRadius: 12, padding: 28, marginBottom: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 28 }}>
          <div style={{
            width: 100, height: 100, borderRadius: '50%',
            border: `4px solid ${gradeColor}`, display: 'flex',
            alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            <span style={{ fontSize: 36, fontWeight: 800, color: gradeColor }}>{grade}</span>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 10, color: '#3d4459', letterSpacing: '0.15em', marginBottom: 8 }}>STRATEGY GRADE</div>
            <pre style={{
              fontSize: 12, color: '#8892a4', lineHeight: 1.7,
              whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: 0,
            }}>{r.executive_summary}</pre>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8, marginBottom: 20 }}>
        <Stat label="TRADES" value={r.total_trades} />
        <Stat label="WIN RATE" value={`${(r.win_rate * 100).toFixed(1)}%`} color={r.win_rate >= 0.5 ? '#00ff88' : '#ff3355'} />
        <Stat label="EXPECTANCY" value={`${r.expectancy_r > 0 ? '+' : ''}${r.expectancy_r?.toFixed(3)}R`} color={r.expectancy_r > 0 ? '#00ff88' : '#ff3355'} />
        <Stat label="PROFIT FACTOR" value={r.profit_factor?.toFixed(2)} color={r.profit_factor >= 1.5 ? '#00ff88' : r.profit_factor >= 1 ? '#f5a623' : '#ff3355'} />
        <Stat label="TOTAL P&L" value={`${r.total_pnl_r > 0 ? '+' : ''}${r.total_pnl_r?.toFixed(1)}R`} color={r.total_pnl_r > 0 ? '#00ff88' : '#ff3355'} />
        <Stat label="MAX DD" value={`${r.max_drawdown_r?.toFixed(1)}R`} color={r.max_drawdown_r <= 5 ? '#00ff88' : '#ff3355'} />
      </div>

      {/* Equity Curve */}
      {r.equity_curve && r.equity_curve.length > 1 && (
        <Panel title="EQUITY CURVE (R)">
          <EquityCurve data={r.equity_curve} />
        </Panel>
      )}

      {/* Breakdowns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
        <Panel title="BY TIER">
          <BreakdownTable data={r.by_tier} />
        </Panel>
        <Panel title="BY SESSION">
          <BreakdownTable data={r.by_session} />
        </Panel>
        <Panel title="BY INDICATION TYPE">
          <BreakdownTable data={r.by_indication_type} />
        </Panel>
        <Panel title="BY SCORE BUCKET">
          <BreakdownTable data={r.by_score_bucket} />
        </Panel>
        <Panel title="BY HOUR (UTC)">
          <BreakdownTable data={r.by_hour} />
        </Panel>
        <Panel title="BY HTF ALIGNMENT">
          <BreakdownTable data={r.by_htf_alignment} />
        </Panel>
      </div>

      {/* MFE/MAE */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 16 }}>
        <Stat label="AVG MAE (all)" value={`${r.avg_mae_r?.toFixed(2)}R`} small />
        <Stat label="AVG MFE (all)" value={`${r.avg_mfe_r?.toFixed(2)}R`} small />
        <Stat label="T1 HIT RATE" value={`${(r.t1_hit_rate * 100).toFixed(0)}%`} small />
        <Stat label="T2 HIT RATE" value={`${(r.t2_hit_rate * 100).toFixed(0)}%`} small />
      </div>

      {/* Recommendations */}
      {r.recommendations && r.recommendations.length > 0 && (
        <Panel title="RECOMMENDATIONS" style={{ marginTop: 16 }}>
          {r.recommendations.map((rec: string, i: number) => (
            <div key={i} style={{
              fontSize: 12, color: '#8892a4', padding: '8px 12px', marginBottom: 6,
              background: '#0a0f18', borderRadius: 6,
              borderLeft: '3px solid #f5a623',
            }}>
              {rec}
            </div>
          ))}
        </Panel>
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// LESSONS VIEW
// ═══════════════════════════════════════════════════════════════════════════════

function LessonsView({ results: r }: { results: any }) {
  const lessons = r.lessons_learned || []
  const criticals = lessons.filter((l: any) => l.severity === 'critical')
  const warnings = lessons.filter((l: any) => l.severity === 'warning')
  const positives = lessons.filter((l: any) => l.severity === 'positive')
  const infos = lessons.filter((l: any) => l.severity === 'info')

  return (
    <div>
      <div style={{ fontSize: 11, color: '#3d4459', letterSpacing: '0.1em', marginBottom: 20 }}>
        {lessons.length} LESSONS EXTRACTED FROM {r.total_trades} TRADES
      </div>

      {criticals.length > 0 && (
        <LessonSection title="🔴 CRITICAL — Fix These First" lessons={criticals} color="#ff3355" />
      )}
      {warnings.length > 0 && (
        <LessonSection title="🟡 WARNINGS — Room for Improvement" lessons={warnings} color="#f5a623" />
      )}
      {positives.length > 0 && (
        <LessonSection title="🟢 STRENGTHS — Keep Doing This" lessons={positives} color="#00ff88" />
      )}
      {infos.length > 0 && (
        <LessonSection title="ℹ️ INSIGHTS" lessons={infos} color="#4d9fff" />
      )}

      {/* Detailed Report */}
      {r.detailed_report && (
        <Panel title="FULL REPORT" style={{ marginTop: 20 }}>
          <pre style={{
            fontSize: 11, color: '#8892a4', lineHeight: 1.6,
            whiteSpace: 'pre-wrap', fontFamily: 'IBM Plex Mono, monospace', margin: 0,
          }}>{r.detailed_report}</pre>
        </Panel>
      )}
    </div>
  )
}

function LessonSection({ title, lessons, color }: { title: string; lessons: any[]; color: string }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color, marginBottom: 10 }}>{title}</div>
      {lessons.map((l: any, i: number) => (
        <div key={i} style={{
          background: '#0d1017', border: '1px solid #151a28',
          borderLeft: `3px solid ${color}`,
          borderRadius: 6, padding: '14px 16px', marginBottom: 8,
        }}>
          <div style={{ fontSize: 12, color: '#c8ccd5', marginBottom: 6 }}>{l.description}</div>
          <div style={{ fontSize: 11, color, fontStyle: 'italic' }}>→ {l.recommendation}</div>
          <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 10, color: '#3d4459' }}>
            {l.sample_size > 0 && <span>{l.sample_size} trades</span>}
            {l.win_rate > 0 && <span>WR: {(l.win_rate * 100).toFixed(0)}%</span>}
            {l.confidence > 0 && <span>Confidence: {(l.confidence * 100).toFixed(0)}%</span>}
          </div>
        </div>
      ))}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// TRADES VIEW
// ═══════════════════════════════════════════════════════════════════════════════

function TradesView({ trades }: { trades: any[] }) {
  const [page, setPage] = useState(0)
  const perPage = 25
  const total = trades.length
  const paged = trades.slice(page * perPage, (page + 1) * perPage)

  return (
    <div>
      <div style={{ fontSize: 11, color: '#3d4459', marginBottom: 12 }}>
        {total} TRADES — Showing {page * perPage + 1}-{Math.min((page + 1) * perPage, total)}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #151a28' }}>
              {['#', 'Time', 'Dir', 'Score', 'Tier', 'Entry', 'Stop', 'Target', 'Exit', 'Exit Reason', 'P&L', 'MAE', 'MFE', 'Indication'].map(h => (
                <th key={h} style={{ padding: '8px 6px', textAlign: 'left', color: '#3d4459', fontSize: 10, letterSpacing: '0.06em' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map((t: any) => (
              <tr key={t.id} style={{ borderBottom: '1px solid #0d1017' }}>
                <td style={tdS}>{t.id}</td>
                <td style={tdS}>{t.entry_time?.slice(0, 16)}</td>
                <td style={{ ...tdS, color: t.direction === 'bullish' ? '#00ff88' : '#ff3355' }}>
                  {t.direction === 'bullish' ? '▲' : '▼'}
                </td>
                <td style={tdS}>{t.composite_score}</td>
                <td style={{ ...tdS, color: t.signal_tier === 'S' ? '#00ff88' : t.signal_tier === 'A' ? '#4d9fff' : '#f5a623' }}>{t.signal_tier}</td>
                <td style={tdS}>{t.entry_price}</td>
                <td style={{ ...tdS, color: '#ff3355' }}>{t.stop_price}</td>
                <td style={{ ...tdS, color: '#00ff88' }}>{t.target_price}</td>
                <td style={tdS}>{t.exit_price}</td>
                <td style={{ ...tdS, color: t.exit_reason === 't1_hit' ? '#00ff88' : t.exit_reason === 'stop_hit' ? '#ff3355' : '#f5a623' }}>
                  {t.exit_reason?.replace('_', ' ')}
                </td>
                <td style={{ ...tdS, color: t.pnl_r > 0 ? '#00ff88' : '#ff3355', fontWeight: 600 }}>
                  {t.pnl_r > 0 ? '+' : ''}{t.pnl_r?.toFixed(2)}R
                </td>
                <td style={tdS}>{t.mae_r?.toFixed(1)}R</td>
                <td style={tdS}>{t.mfe_r?.toFixed(1)}R</td>
                <td style={{ ...tdS, fontSize: 10, color: '#5a6080' }}>{t.indication_type?.replace(/_/g, ' ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total > perPage && (
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 12 }}>
          <PageBtn onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>← Prev</PageBtn>
          <span style={{ fontSize: 11, color: '#3d4459', padding: '6px 12px' }}>
            Page {page + 1} of {Math.ceil(total / perPage)}
          </span>
          <PageBtn onClick={() => setPage(p => p + 1)} disabled={(page + 1) * perPage >= total}>Next →</PageBtn>
        </div>
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// HISTORY VIEW
// ═══════════════════════════════════════════════════════════════════════════════

function HistoryView({ history, onSelect }: { history: any[]; onSelect: (rid: string) => void }) {
  if (!history.length) return <EmptyPanel message="No previous runs" sub="Run your first backtest to start building history." />

  return (
    <div>
      <div style={{ fontSize: 11, color: '#3d4459', marginBottom: 12 }}>
        {history.length} PREVIOUS BACKTEST RUNS
      </div>
      {history.map((r: any) => (
        <div key={r.run_id} onClick={() => r.status === 'complete' && onSelect(r.run_id)} style={{
          background: '#0d1017', border: '1px solid #151a28', borderRadius: 8,
          padding: '14px 18px', marginBottom: 8, cursor: r.status === 'complete' ? 'pointer' : 'default',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontWeight: 700, fontSize: 14 }}>{r.symbol}</span>
              <span style={{
                fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                color: r.status === 'complete' ? '#00ff88' : r.status === 'running' ? '#f5a623' : '#ff3355',
                background: r.status === 'complete' ? '#00ff8815' : r.status === 'running' ? '#f5a62315' : '#ff335515',
              }}>{r.status?.toUpperCase()}</span>
              {r.grade && <span style={{ fontSize: 14, fontWeight: 800, color: r.grade?.startsWith('A') ? '#00ff88' : r.grade?.startsWith('B') ? '#4d9fff' : '#f5a623' }}>{r.grade}</span>}
            </div>
            <span style={{ fontSize: 10, color: '#3d4459' }}>{r.created_at?.slice(0, 16)}</span>
          </div>
          {r.status === 'complete' && (
            <div style={{ display: 'flex', gap: 20, fontSize: 11, color: '#5a6080' }}>
              <span>{r.total_trades} trades</span>
              <span>WR: {(r.win_rate * 100).toFixed(1)}%</span>
              <span>Exp: {r.expectancy_r?.toFixed(3)}R</span>
              <span>PF: {r.profit_factor?.toFixed(2)}</span>
              <span style={{ color: r.total_pnl_r > 0 ? '#00ff88' : '#ff3355' }}>P&L: {r.total_pnl_r > 0 ? '+' : ''}{r.total_pnl_r?.toFixed(1)}R</span>
            </div>
          )}
          {r.executive_summary && (
            <div style={{ fontSize: 10, color: '#3d4459', marginTop: 6 }}>{r.executive_summary}</div>
          )}
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
      <div style={{ fontSize: 10, color: '#3d4459', letterSpacing: '0.12em', marginBottom: 14, fontWeight: 600 }}>{title}</div>
      {children}
    </div>
  )
}

function Stat({ label, value, color, small }: { label: string; value: any; color?: string; small?: boolean }) {
  return (
    <div style={{ background: '#0d1017', border: '1px solid #151a28', borderRadius: 6, padding: small ? '10px 12px' : '14px 16px' }}>
      <div style={{ fontSize: 9, color: '#3d4459', letterSpacing: '0.1em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: small ? 14 : 20, fontWeight: 700, color: color || '#c8ccd5' }}>{value}</div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: '#5a6080', marginBottom: 4 }}>{label}</div>
      {children}
    </div>
  )
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!checked)} style={{
      padding: '6px 12px', fontSize: 11, borderRadius: 4, cursor: 'pointer',
      border: `1px solid ${checked ? '#00ff8840' : '#151a28'}`,
      background: checked ? '#00ff8815' : '#0a0c12',
      color: checked ? '#00ff88' : '#3d4459',
    }}>{label}: {checked ? 'ON' : 'OFF'}</button>
  )
}

function BreakdownTable({ data }: { data: Record<string, any> }) {
  if (!data || Object.keys(data).length === 0) return <div style={{ fontSize: 11, color: '#3d4459' }}>No data</div>
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
      <thead>
        <tr>
          {['Key', 'Trades', 'Win Rate', 'Avg R', 'Total R'].map(h => (
            <th key={h} style={{ padding: '4px 6px', textAlign: 'left', color: '#3d4459', fontSize: 10, borderBottom: '1px solid #151a28' }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {Object.entries(data).map(([k, v]: [string, any]) => (
          <tr key={k}>
            <td style={{ padding: '4px 6px', color: '#8892a4' }}>{k}</td>
            <td style={{ padding: '4px 6px', color: '#5a6080' }}>{v.trades}</td>
            <td style={{ padding: '4px 6px', color: v.win_rate >= 0.55 ? '#00ff88' : v.win_rate < 0.4 ? '#ff3355' : '#f5a623' }}>
              {(v.win_rate * 100).toFixed(0)}%
            </td>
            <td style={{ padding: '4px 6px', color: v.avg_r > 0 ? '#00ff88' : '#ff3355' }}>{v.avg_r > 0 ? '+' : ''}{v.avg_r?.toFixed(2)}</td>
            <td style={{ padding: '4px 6px', color: v.total_r > 0 ? '#00ff88' : '#ff3355', fontWeight: 600 }}>{v.total_r > 0 ? '+' : ''}{v.total_r?.toFixed(1)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function EquityCurve({ data }: { data: any[] }) {
  if (!data || data.length < 2) return null
  const max = Math.max(...data.map(d => d.equity))
  const min = Math.min(...data.map(d => d.equity))
  const range = max - min || 1
  const w = 800
  const h = 160
  const pad = 20

  const points = data.map((d, i) => {
    const x = pad + (i / (data.length - 1)) * (w - pad * 2)
    const y = h - pad - ((d.equity - min) / range) * (h - pad * 2)
    return `${x},${y}`
  }).join(' ')

  const final = data[data.length - 1]?.equity ?? 0
  const lineColor = final >= 0 ? '#00ff88' : '#ff3355'

  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 160 }}>
      <line x1={pad} y1={h - pad - ((-min) / range) * (h - pad * 2)} x2={w - pad} y2={h - pad - ((-min) / range) * (h - pad * 2)}
        stroke="#1a1f2e" strokeWidth="1" strokeDasharray="4" />
      <polyline points={points} fill="none" stroke={lineColor} strokeWidth="2" />
      <text x={pad} y={12} fill="#3d4459" fontSize="9" fontFamily="IBM Plex Mono">{max.toFixed(1)}R</text>
      <text x={pad} y={h - 4} fill="#3d4459" fontSize="9" fontFamily="IBM Plex Mono">{min.toFixed(1)}R</text>
      <text x={w - pad} y={12} fill={lineColor} fontSize="10" fontFamily="IBM Plex Mono" textAnchor="end">
        {final >= 0 ? '+' : ''}{final.toFixed(1)}R
      </text>
    </svg>
  )
}

function EmptyPanel({ message, sub }: { message: string; sub: string }) {
  return (
    <div style={{ textAlign: 'center', padding: 60 }}>
      <div style={{ fontSize: 14, color: '#3d4459', marginBottom: 8 }}>{message}</div>
      <div style={{ fontSize: 11, color: '#252830' }}>{sub}</div>
    </div>
  )
}

function PageBtn({ onClick, disabled, children }: { onClick: () => void; disabled: boolean; children: React.ReactNode }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: '6px 14px', fontSize: 11, cursor: disabled ? 'not-allowed' : 'pointer',
      background: '#0d1017', border: '1px solid #151a28', borderRadius: 4,
      color: disabled ? '#1a1f2e' : '#5a6080',
    }}>{children}</button>
  )
}

// Styles
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', background: '#0a0c12',
  border: '1px solid #151a28', borderRadius: 4, color: '#c8ccd5',
  fontSize: 12, fontFamily: 'IBM Plex Mono', outline: 'none',
}
const selectStyle: React.CSSProperties = { ...inputStyle }
const tdS: React.CSSProperties = { padding: '6px', color: '#8892a4' }

// API helper
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
