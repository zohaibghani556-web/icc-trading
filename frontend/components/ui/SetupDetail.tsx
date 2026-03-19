/**
 * components/ui/SetupDetail.tsx — Full setup evaluation detail panel
 *
 * Shows every rule, score, and explanation for a single ICC evaluation.
 * Displayed as a side panel when the user clicks a setup card.
 */
'use client'
import { SetupEvaluation } from '@/lib/api'
import { VerdictBadge, ScoreBar, ConfidenceRing, formatPrice } from './index'

interface Props {
  setup: SetupEvaluation
  onClose: () => void
}

export function SetupDetail({ setup, onClose }: Props) {
  const exp = setup.explanation || {}

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0,
      width: '480px', zIndex: 100,
      background: 'var(--bg-secondary)',
      borderLeft: '1px solid var(--border)',
      overflowY: 'auto',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 1,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontFamily: 'IBM Plex Mono', fontWeight: 600, fontSize: '15px' }}>
            {setup.symbol}
          </span>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            {setup.direction} · {setup.timeframe}m
          </span>
          <VerdictBadge verdict={setup.verdict} />
        </div>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: 'var(--text-muted)',
          cursor: 'pointer', fontSize: '18px', lineHeight: 1, padding: '4px',
        }}>×</button>
      </div>

      <div style={{ padding: '20px', flex: 1 }}>
        {/* Confidence + summary */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '16px',
          background: 'var(--bg-card)', borderRadius: '8px',
          border: '1px solid var(--border)', padding: '16px', marginBottom: '20px',
        }}>
          <ConfidenceRing score={setup.confidence_score} />
          <div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
              {exp.summary}
            </div>
            {setup.is_countertrend && (
              <span style={{ fontSize: '11px', color: '#f59e0b', fontFamily: 'IBM Plex Mono' }}>
                ⚠ COUNTERTREND
              </span>
            )}
          </div>
        </div>

        {/* Phase scores */}
        <Section title="Phase Scores">
          <ScoreBar score={setup.environment_score}   label="Environment" />
          <ScoreBar score={setup.indication_score}    label="Indication" />
          <ScoreBar score={setup.correction_score}    label="Correction" />
          <ScoreBar score={setup.continuation_score}  label="Continuation" />
          <ScoreBar score={setup.risk_score}          label="Risk" />
        </Section>

        {/* Trade levels */}
        {setup.verdict === 'valid_trade' && (
          <Section title="Trade Levels">
            <LevelRow label="Entry"  value={formatPrice(setup.entry_price)} color="var(--text-primary)" />
            <LevelRow label="Stop"   value={formatPrice(setup.stop_price)}  color="#ef4444" />
            <LevelRow label="Target" value={formatPrice(setup.target_price)} color="#22c55e" />
            <LevelRow label="RR"     value={setup.risk_reward ? `${setup.risk_reward}:1` : '—'} color="#3b82f6" />
          </Section>
        )}

        {/* ICC components */}
        <Section title="ICC Components">
          <LevelRow label="Indication"    value={setup.indication_type || '—'} />
          <LevelRow label="Correction"    value={setup.correction_zone_type || '—'} />
          <LevelRow label="Continuation"  value={setup.continuation_trigger_type || '—'} />
          <LevelRow label="HTF Bias"      value={setup.htf_bias || 'unknown'} color={setup.has_htf_alignment ? '#22c55e' : 'var(--text-secondary)'} />
        </Section>

        {/* Passed rules */}
        {exp.passed_rules?.length > 0 && (
          <Section title={`Passed (${exp.passed_rules.length})`}>
            {exp.passed_rules.map((r: string, i: number) => (
              <RuleLine key={i} text={r} />
            ))}
          </Section>
        )}

        {/* Failed rules */}
        {exp.failed_rules?.length > 0 && (
          <Section title={`Failed (${exp.failed_rules.length})`}>
            {exp.failed_rules.map((r: string, i: number) => (
              <RuleLine key={i} text={r} failed />
            ))}
          </Section>
        )}

        {/* Warnings */}
        {exp.warnings?.length > 0 && (
          <Section title={`Warnings (${exp.warnings.length})`}>
            {exp.warnings.map((r: string, i: number) => (
              <RuleLine key={i} text={r} warn />
            ))}
          </Section>
        )}

        {/* Suggested note */}
        {exp.suggested_review_note && (
          <div style={{
            marginTop: '8px', padding: '12px',
            background: 'rgba(59,130,246,0.08)',
            border: '1px solid rgba(59,130,246,0.2)',
            borderRadius: '6px', fontSize: '12px',
            color: 'var(--text-secondary)',
          }}>
            💡 {exp.suggested_review_note}
          </div>
        )}

        {/* Timestamp */}
        <div style={{ marginTop: '16px', fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'IBM Plex Mono' }}>
          Evaluated: {new Date(setup.evaluated_at).toLocaleString()}
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '20px' }}>
      <div style={{
        fontSize: '11px', fontWeight: 600, letterSpacing: '0.08em',
        color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '8px',
      }}>{title}</div>
      {children}
    </div>
  )
}

function LevelRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '6px 0', borderBottom: '1px solid var(--border)',
    }}>
      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{ fontFamily: 'IBM Plex Mono', fontSize: '12px', color: color || 'var(--text-primary)' }}>
        {value}
      </span>
    </div>
  )
}

function RuleLine({ text, failed, warn }: { text: string; failed?: boolean; warn?: boolean }) {
  const color = failed ? '#ef4444' : warn ? '#f59e0b' : '#22c55e'
  return (
    <div style={{
      fontSize: '11px', color: 'var(--text-secondary)',
      padding: '4px 8px', marginBottom: '2px',
      borderRadius: '4px', background: 'var(--bg-tertiary)',
      borderLeft: `2px solid ${color}`,
    }}>
      {text}
    </div>
  )
}
