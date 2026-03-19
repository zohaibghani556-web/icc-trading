/**
 * components/ui/index.tsx — All shared UI components
 *
 * Every page imports from here. This is the design system for the dashboard.
 * Dark terminal aesthetic — IBM Plex Mono for numbers, Inter for text.
 */

'use client'
import { SetupEvaluation } from '@/lib/api'

// ── Helpers ────────────────────────────────────────────────────────────────

export function formatPrice(value?: number | null, digits = 2): string {
  if (value == null) return '—'
  return value.toFixed(digits)
}

export function pnlColor(value?: number | null): string {
  if (value == null) return 'var(--text-secondary)'
  return value > 0 ? 'var(--green)' : value < 0 ? 'var(--red)' : 'var(--text-secondary)'
}

// ── Verdict Badge ──────────────────────────────────────────────────────────

export function VerdictBadge({ verdict }: { verdict: string }) {
  const map: Record<string, { label: string; color: string; bg: string; border: string }> = {
    valid_trade:   { label: 'VALID TRADE',  color: '#22c55e', bg: 'rgba(34,197,94,0.1)',   border: 'rgba(34,197,94,0.3)' },
    watch_only:    { label: 'WATCH ONLY',   color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.3)' },
    invalid_setup: { label: 'INVALID',      color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.3)' },
  }
  const s = map[verdict] ?? { label: verdict.toUpperCase(), color: '#8b9099', bg: 'rgba(139,144,153,0.1)', border: 'rgba(139,144,153,0.3)' }
  return (
    <span style={{
      fontFamily: 'IBM Plex Mono, monospace',
      fontSize: '10px', fontWeight: 600, letterSpacing: '0.05em',
      padding: '3px 7px', borderRadius: '4px', whiteSpace: 'nowrap',
      color: s.color, background: s.bg, border: `1px solid ${s.border}`,
    }}>
      {s.label}
    </span>
  )
}

// ── Direction Badge ────────────────────────────────────────────────────────

export function DirectionBadge({ direction }: { direction: string }) {
  const isBull = direction === 'bullish' || direction === 'long'
  return (
    <span style={{
      fontFamily: 'IBM Plex Mono, monospace',
      fontSize: '10px', fontWeight: 600, padding: '3px 7px', borderRadius: '4px', whiteSpace: 'nowrap',
      color: isBull ? '#22c55e' : '#ef4444',
      background: isBull ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
      border: `1px solid ${isBull ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
    }}>
      {isBull ? '▲ LONG' : '▼ SHORT'}
    </span>
  )
}

// Alias for backwards compatibility
export const DirectionPill = DirectionBadge

// ── Status Badge ───────────────────────────────────────────────────────────

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; bg: string }> = {
    open:      { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)' },
    closed:    { color: '#8b9099', bg: 'rgba(139,144,153,0.1)' },
    cancelled: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)' },
  }
  const s = map[status] ?? { color: '#8b9099', bg: 'rgba(139,144,153,0.1)' }
  return (
    <span style={{
      fontFamily: 'IBM Plex Mono, monospace',
      fontSize: '10px', fontWeight: 600, padding: '2px 6px', borderRadius: '4px',
      color: s.color, background: s.bg,
    }}>
      {status.toUpperCase()}
    </span>
  )
}

// ── Score Bar ──────────────────────────────────────────────────────────────

export function ScoreBar({ score, label }: { score: number; label: string }) {
  const color = score >= 70 ? '#22c55e' : score >= 45 ? '#f59e0b' : '#ef4444'
  return (
    <div style={{ marginBottom: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: '12px', fontWeight: 600, color }}>{score}</span>
      </div>
      <div style={{ height: '4px', background: 'var(--bg-tertiary)', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.min(score, 100)}%`, background: color, borderRadius: '2px', transition: 'width 0.4s ease' }} />
      </div>
    </div>
  )
}

// ── Confidence Ring ────────────────────────────────────────────────────────

export function ConfidenceRing({ score }: { score: number }) {
  const pct = Math.round((score <= 1 ? score * 100 : score))
  const color = pct >= 70 ? '#22c55e' : pct >= 45 ? '#f59e0b' : '#ef4444'
  const r = 20
  const circ = 2 * Math.PI * r
  const dash = (Math.min(pct, 100) / 100) * circ
  return (
    <div style={{ position: 'relative', width: 52, height: 52, flexShrink: 0 }}>
      <svg width="52" height="52" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="26" cy="26" r={r} fill="none" stroke="var(--bg-tertiary)" strokeWidth="3" />
        <circle cx="26" cy="26" r={r} fill="none" stroke={color} strokeWidth="3"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'IBM Plex Mono, monospace', fontSize: '11px', fontWeight: 600, color,
      }}>
        {pct}
      </div>
    </div>
  )
}

// ── Stat Card ──────────────────────────────────────────────────────────────

export function StatCard({
  label, value, sub, color,
}: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: '8px', padding: '16px 20px',
    }}>
      <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '8px' }}>
        {label}
      </div>
      <div style={{
        fontFamily: 'IBM Plex Mono, monospace', fontSize: '24px', fontWeight: 600,
        color: color || 'var(--text-primary)', lineHeight: 1,
      }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>{sub}</div>}
    </div>
  )
}

// ── Card ───────────────────────────────────────────────────────────────────

export function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: '8px', overflow: 'hidden', ...style,
    }}>
      {children}
    </div>
  )
}

// ── Page Header ────────────────────────────────────────────────────────────

export function PageHeader({ title, sub, action }: { title: string; sub?: string; action?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '24px' }}>
      <div>
        <h1 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>{title}</h1>
        {sub && <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>{sub}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  )
}

// Alias
export const SectionHeader = PageHeader

// ── Empty State ────────────────────────────────────────────────────────────

export function EmptyState({ message, sub }: { message: string; sub?: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '48px 20px', color: 'var(--text-muted)' }}>
      <div style={{ fontSize: '28px', marginBottom: '12px', opacity: 0.3 }}>◎</div>
      <div style={{ fontSize: '14px', marginBottom: sub ? '6px' : 0 }}>{message}</div>
      {sub && <div style={{ fontSize: '12px', marginTop: '4px' }}>{sub}</div>}
    </div>
  )
}

// ── Loading Spinner ────────────────────────────────────────────────────────

export function LoadingSpinner() {
  return (
    <div style={{ textAlign: 'center', padding: '48px 20px', color: 'var(--text-muted)', fontSize: '13px' }}>
      Loading...
    </div>
  )
}

// ── Setup Card — used in feeds ─────────────────────────────────────────────

export function SetupCard({ setup, onClick, selected }: {
  setup: SetupEvaluation
  onClick?: () => void
  selected?: boolean
}) {
  const phases = [
    { key: 'environment_score' as const, label: 'Env' },
    { key: 'indication_score'  as const, label: 'Ind' },
    { key: 'correction_score'  as const, label: 'Cor' },
    { key: 'continuation_score'as const, label: 'Con' },
  ]

  return (
    <div
      onClick={onClick}
      style={{
        padding: '12px 16px',
        borderBottom: '1px solid var(--border)',
        borderLeft: selected ? '2px solid var(--blue)' : '2px solid transparent',
        background: selected ? 'var(--bg-tertiary)' : 'transparent',
        cursor: onClick ? 'pointer' : 'default',
        display: 'flex', alignItems: 'center', gap: '12px',
      }}
    >
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontWeight: 700, fontSize: '13px' }}>{setup.symbol}</span>
          <DirectionBadge direction={setup.direction} />
          <VerdictBadge verdict={setup.verdict} />
          <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: '11px', color: 'var(--text-muted)' }}>{setup.timeframe}m</span>
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {setup.explanation?.summary || '—'}
        </div>
        <div style={{ display: 'flex', gap: '12px', marginTop: '6px' }}>
          {phases.map(p => {
            const score = setup[p.key] as number
            const c = score >= 70 ? '#22c55e' : score >= 45 ? '#f59e0b' : '#ef4444'
            return (
              <div key={p.key} style={{ textAlign: 'center' }}>
                <div style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: '11px', color: c, fontWeight: 600 }}>{score}</div>
                <div style={{ fontSize: '9px', color: 'var(--text-muted)' }}>{p.label}</div>
              </div>
            )
          })}
        </div>
      </div>
      <ConfidenceRing score={setup.confidence_score} />
    </div>
  )
}

// ── Price display ──────────────────────────────────────────────────────────

export function Price({ value, digits = 2 }: { value?: number | null; digits?: number }) {
  if (value == null) return <span style={{ color: 'var(--text-muted)' }}>—</span>
  return <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: '13px' }}>{value.toFixed(digits)}</span>
}

// ── Skeleton loader ────────────────────────────────────────────────────────

export function Skeleton({ height = 40, width = '100%' }: { height?: number; width?: string | number }) {
  return (
    <div style={{
      height, width,
      background: 'var(--bg-tertiary)',
      borderRadius: '4px',
    }} />
  )
}
