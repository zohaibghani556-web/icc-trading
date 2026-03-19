/**
 * app/settings/page.tsx — ICC rule configuration
 *
 * All ICC thresholds and toggles are configurable here.
 * Changes take effect on the next webhook evaluation.
 */
'use client'
import { useState, useEffect } from 'react'
import { api, ICCConfig } from '@/lib/api'
import { PageHeader } from '@/components/ui'

export default function SettingsPage() {
  const [config, setConfig] = useState<ICCConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.config.get().then(c => { setConfig(c); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const update = (k: keyof ICCConfig, v: any) => {
    if (!config) return
    setConfig({ ...config, [k]: v })
  }

  const save = async () => {
    if (!config) return
    setSaving(true)
    try {
      await api.config.update(config)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div style={{ color: 'var(--text-muted)' }}>Loading config…</div>
  if (!config) return <div style={{ color: '#ef4444' }}>Could not load configuration.</div>

  return (
    <div style={{ maxWidth: '680px' }}>
      <PageHeader
        title="ICC Settings"
        sub="All rule thresholds are configurable. Changes take effect on the next alert."
        action={
          <button onClick={save} disabled={saving} style={{
            padding: '8px 18px', fontSize: '12px', cursor: 'pointer',
            borderRadius: '6px', border: 'none', fontWeight: 500,
            background: saved ? '#22c55e' : '#3b82f6', color: '#fff',
          }}>
            {saving ? 'Saving…' : saved ? '✓ Saved' : 'Save Changes'}
          </button>
        }
      />

      {/* Environment */}
      <Section title="Environment Rules" desc="Controls when the engine will evaluate setups at all.">
        <ToggleField
          label="Require higher timeframe bias"
          desc="If enabled, setups without HTF bias get reduced scores."
          value={config.require_htf_bias}
          onChange={v => update('require_htf_bias', v)}
        />
        <SessionField
          value={config.allowed_sessions}
          onChange={v => update('allowed_sessions', v)}
        />
      </Section>

      {/* Indication */}
      <Section title="Indication Rules" desc="What counts as a valid directional signal.">
        <NumberField
          label="Min structure break (points)"
          desc="Minimum move size to qualify as an indication."
          value={config.min_retracement_pct}
          min={0} step={0.5}
          onChange={v => update('min_retracement_pct', v)}
        />
      </Section>

      {/* Correction */}
      <Section title="Correction Rules" desc="Controls valid pullback depth and zone requirements.">
        <NumberField
          label="Min retracement"
          desc="Minimum pullback as a decimal (0.236 = 23.6% fib)."
          value={config.min_retracement_pct}
          min={0.1} max={0.5} step={0.001}
          onChange={v => update('min_retracement_pct', v)}
        />
        <NumberField
          label="Max retracement"
          desc="Maximum pullback before structure is considered broken."
          value={config.max_retracement_pct}
          min={0.3} max={0.85} step={0.001}
          onChange={v => update('max_retracement_pct', v)}
        />
        <ToggleField
          label="Require correction zone"
          desc="If enabled, correction must land in a recognized zone (FVG, OB, etc.)."
          value={config.require_correction_zone}
          onChange={v => update('require_correction_zone', v)}
        />
      </Section>

      {/* Risk */}
      <Section title="Risk Rules" desc="Position sizing and daily trading limits.">
        <NumberField
          label="Minimum RR required"
          desc="Trades with lower RR than this will be blocked."
          value={config.min_risk_reward}
          min={1} max={10} step={0.5}
          onChange={v => update('min_risk_reward', v)}
        />
        <NumberField
          label="Max risk per trade (%)"
          desc="Maximum account risk per single trade."
          value={config.max_risk_per_trade_pct}
          min={0.25} max={5} step={0.25}
          onChange={v => update('max_risk_per_trade_pct', v)}
        />
        <NumberField
          label="Daily max loss (%)"
          desc="Stop trading for the day after losing this much."
          value={config.daily_max_loss_pct}
          min={1} max={10} step={0.5}
          onChange={v => update('daily_max_loss_pct', v)}
        />
        <NumberField
          label="Max consecutive losses"
          desc="Pause and review after this many losses in a row."
          value={config.max_consecutive_losses}
          min={1} max={10} step={1}
          onChange={v => update('max_consecutive_losses', v)}
        />
        <NumberField
          label="Max open positions"
          desc="Never hold more than this many simultaneous trades."
          value={config.max_open_positions}
          min={1} max={5} step={1}
          onChange={v => update('max_open_positions', v)}
        />
      </Section>

      {/* Scoring */}
      <Section title="Scoring Modifiers">
        <NumberField
          label="Countertrend penalty (points)"
          desc="Deducted from confidence score for setups against the HTF bias."
          value={config.countertrend_score_penalty}
          min={0} max={50} step={5}
          onChange={v => update('countertrend_score_penalty', v)}
        />
      </Section>

      {/* Webhook info */}
      <Section title="Webhook Setup">
        <div style={{ background: 'var(--bg-tertiary)', borderRadius: '6px', padding: '14px', fontSize: '12px', color: 'var(--text-secondary)' }}>
          <p style={{ marginBottom: '8px' }}>Send TradingView webhooks to:</p>
          <code style={{ display: 'block', fontFamily: 'IBM Plex Mono', color: '#3b82f6', background: 'var(--bg-card)', padding: '8px 12px', borderRadius: '4px', marginBottom: '8px' }}>
            POST {typeof window !== 'undefined' ? window.location.origin.replace('3000', '8000') : 'http://localhost:8000'}/api/v1/alerts/webhook
          </code>
          <p>Required header: <code style={{ fontFamily: 'IBM Plex Mono', color: '#f59e0b' }}>X-Webhook-Token: your-WEBHOOK_SECRET</code></p>
          <p style={{ marginTop: '6px', color: 'var(--text-muted)' }}>See <code>/docs/TRADINGVIEW_ALERT_FORMAT.md</code> for full JSON format.</p>
        </div>
      </Section>
    </div>
  )
}

function Section({ title, desc, children }: { title: string; desc?: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '28px' }}>
      <div style={{ marginBottom: '12px', paddingBottom: '10px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)' }}>{title}</div>
        {desc && <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>{desc}</div>}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {children}
      </div>
    </div>
  )
}

function NumberField({
  label, desc, value, min, max, step, onChange,
}: {
  label: string; desc?: string; value: number;
  min?: number; max?: number; step?: number;
  onChange: (v: number) => void
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
      <div>
        <div style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{label}</div>
        {desc && <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>{desc}</div>}
      </div>
      <input
        type="number" value={value} min={min} max={max} step={step}
        onChange={e => onChange(parseFloat(e.target.value))}
        style={{
          width: '100px', padding: '7px 10px', textAlign: 'right',
          background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
          borderRadius: '5px', color: 'var(--text-primary)', fontSize: '13px',
          fontFamily: 'IBM Plex Mono', outline: 'none', flexShrink: 0,
        }}
      />
    </div>
  )
}

function ToggleField({
  label, desc, value, onChange,
}: { label: string; desc?: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
      <div>
        <div style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{label}</div>
        {desc && <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>{desc}</div>}
      </div>
      <button
        onClick={() => onChange(!value)}
        style={{
          width: '44px', height: '24px', borderRadius: '12px', border: 'none',
          background: value ? '#3b82f6' : 'var(--border)', cursor: 'pointer',
          position: 'relative', flexShrink: 0, transition: 'background 0.2s',
        }}
      >
        <span style={{
          position: 'absolute', top: '3px',
          left: value ? '22px' : '3px',
          width: '18px', height: '18px', borderRadius: '50%',
          background: '#fff', transition: 'left 0.2s',
        }} />
      </button>
    </div>
  )
}

function SessionField({
  value, onChange,
}: { value: string[]; onChange: (v: string[]) => void }) {
  const all = ['us_premarket', 'us_regular', 'us_afterhours', 'globex', 'london', 'asia']
  const toggle = (s: string) => {
    if (value.includes(s)) onChange(value.filter(x => x !== s))
    else onChange([...value, s])
  }

  return (
    <div>
      <div style={{ fontSize: '13px', color: 'var(--text-primary)', marginBottom: '4px' }}>Allowed Sessions</div>
      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px' }}>Setups outside these sessions will be blocked.</div>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {all.map(s => (
          <button key={s} onClick={() => toggle(s)} style={{
            padding: '5px 11px', fontSize: '11px', cursor: 'pointer',
            borderRadius: '4px', border: '1px solid',
            borderColor: value.includes(s) ? '#3b82f6' : 'var(--border)',
            background: value.includes(s) ? 'rgba(59,130,246,0.12)' : 'var(--bg-tertiary)',
            color: value.includes(s) ? '#3b82f6' : 'var(--text-muted)',
          }}>{s.replace(/_/g, ' ')}</button>
        ))}
      </div>
    </div>
  )
}
