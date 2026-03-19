/**
 * app/analytics/page.tsx — Performance analytics
 *
 * Charts and tables for:
 * - Win rate, expectancy, profit factor
 * - Performance by symbol
 * - Setup score vs outcome correlation
 * - Verdict distribution
 */
'use client'
import { useState, useEffect } from 'react'
import { api, AnalyticsSummary, SymbolPerf, VerdictCount } from '@/lib/api'
import { StatCard, PageHeader, pnlColor } from '@/components/ui'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'

const PIE_COLORS = { valid_trade: '#22c55e', watch_only: '#f59e0b', invalid_setup: '#ef4444' }

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [bySymbol, setBySymbol] = useState<SymbolPerf[]>([])
  const [byScore, setByScore] = useState<Record<string, any>>({})
  const [verdicts, setVerdicts] = useState<VerdictCount[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.analytics.summary(),
      api.analytics.bySymbol(),
      api.analytics.byScore(),
      api.analytics.verdictCounts(),
    ]).then(([s, sym, sc, v]) => {
      setSummary(s)
      setBySymbol(sym)
      setByScore(sc)
      setVerdicts(v)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ color: 'var(--text-muted)', padding: '40px' }}>Loading analytics…</div>

  const buckets = [
    { name: 'Low (0-50)', ...byScore.low_0_50 },
    { name: 'Medium (50-75)', ...byScore.medium_50_75 },
    { name: 'High (75-100)', ...byScore.high_75_100 },
  ].filter(b => b.trades)

  const verdictPie = verdicts.map(v => ({
    name: v.verdict.replace(/_/g, ' '),
    value: v.count,
    color: PIE_COLORS[v.verdict as keyof typeof PIE_COLORS] || '#888',
  }))

  const hasTrades = (summary?.total_trades ?? 0) > 0

  return (
    <div style={{ maxWidth: '1000px' }}>
      <PageHeader title="Analytics" sub="Paper trading performance — ICC setup quality vs outcomes" />

      {/* Top stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px', marginBottom: '28px' }}>
        <StatCard label="Total Trades" value={summary?.total_trades ?? 0} />
        <StatCard
          label="Win Rate"
          value={hasTrades ? `${Math.round((summary!.win_rate) * 100)}%` : '—'}
          color={summary?.win_rate && summary.win_rate > 0.5 ? '#22c55e' : '#ef4444'}
        />
        <StatCard
          label="Expectancy"
          value={hasTrades ? `${summary!.expectancy_r > 0 ? '+' : ''}${summary!.expectancy_r}R` : '—'}
          color={pnlColor(summary?.expectancy_r)}
          sub="per trade"
        />
        <StatCard
          label="Profit Factor"
          value={hasTrades ? summary!.profit_factor : '—'}
          color={summary?.profit_factor && summary.profit_factor > 1.5 ? '#22c55e' : '#ef4444'}
        />
        <StatCard
          label="Total P&L"
          value={hasTrades ? `${summary!.total_pnl_r > 0 ? '+' : ''}${summary!.total_pnl_r}R` : '—'}
          color={pnlColor(summary?.total_pnl_r)}
        />
      </div>

      {!hasTrades ? (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px', padding: '60px', textAlign: 'center' }}>
          <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '6px' }}>No closed trades yet</div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Open and close paper trades to see performance analytics here.</div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Performance by symbol */}
          {bySymbol.length > 0 && (
            <ChartCard title="P&L by Symbol (R)">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={bySymbol} margin={{ left: -10 }}>
                  <XAxis dataKey="symbol" tick={{ fill: '#8b9099', fontSize: 11, fontFamily: 'IBM Plex Mono' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#8b9099', fontSize: 11, fontFamily: 'IBM Plex Mono' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '6px', fontSize: '12px' }}
                    labelStyle={{ color: 'var(--text-primary)', fontFamily: 'IBM Plex Mono' }}
                  />
                  <Bar dataKey="total_pnl_r" name="P&L (R)" radius={[3, 3, 0, 0]}>
                    {bySymbol.map((s, i) => (
                      <Cell key={i} fill={s.total_pnl_r >= 0 ? '#22c55e' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          )}

          {/* Verdict distribution */}
          {verdictPie.length > 0 && (
            <ChartCard title="Setup Verdict Distribution">
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={verdictPie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={75} label={({ name, value }) => `${value}`}>
                    {verdictPie.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Legend wrapperStyle={{ fontSize: '11px', color: 'var(--text-secondary)' }} />
                  <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '6px', fontSize: '12px' }} />
                </PieChart>
              </ResponsiveContainer>
            </ChartCard>
          )}

          {/* Score vs outcome */}
          {buckets.length > 0 && (
            <ChartCard title="Setup Score vs Outcome">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={buckets} margin={{ left: -10 }}>
                  <XAxis dataKey="name" tick={{ fill: '#8b9099', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#8b9099', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '6px', fontSize: '12px' }} />
                  <Bar dataKey="win_rate" name="Win Rate" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px' }}>
                Does a higher ICC confidence score predict better outcomes?
              </div>
            </ChartCard>
          )}

          {/* W/L breakdown */}
          <ChartCard title="Win / Loss Detail">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px' }}>
              <MetricRow label="Avg Winner" value={`+${summary?.avg_winner_r ?? 0}R`} color="#22c55e" />
              <MetricRow label="Avg Loser" value={`${summary?.avg_loser_r ?? 0}R`} color="#ef4444" />
              <MetricRow label="Avg RR Achieved" value={`${summary?.avg_rr ?? 0}:1`} />
              <MetricRow label="Profit Factor" value={`${summary?.profit_factor ?? 0}×`} color={summary?.profit_factor && summary.profit_factor > 1 ? '#22c55e' : '#ef4444'} />
            </div>
          </ChartCard>
        </div>
      )}
    </div>
  )
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px', padding: '16px 18px' }}>
      <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function MetricRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: 'var(--bg-tertiary)', borderRadius: '6px', padding: '10px 12px' }}>
      <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '4px' }}>{label}</div>
      <div style={{ fontFamily: 'IBM Plex Mono', fontSize: '16px', fontWeight: 600, color: color || 'var(--text-primary)' }}>{value}</div>
    </div>
  )
}
