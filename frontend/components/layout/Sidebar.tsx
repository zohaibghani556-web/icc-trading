'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const nav = [
  { href: '/',               label: 'Dashboard',     icon: '▣' },
  { href: '/alerts',         label: 'Alerts',        icon: '◈' },
  { href: '/backtest',       label: 'Backtest',      icon: '⚡' },
  { href: '/journal',        label: 'Journal',       icon: '≡' },
  { href: '/analytics',      label: 'Analytics',     icon: '◎' },
  { href: '/paper-trading',  label: 'Paper Trade',   icon: '◆' },
  { href: '/settings',       label: 'Settings',      icon: '⚙' },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '220px',
      height: '100vh',
      background: 'var(--bg-secondary)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 50,
    }}>
      {/* Logo */}
      <div style={{
        padding: '20px 20px 16px',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ fontFamily: 'IBM Plex Mono', fontWeight: 600, fontSize: '15px', color: 'var(--text-primary)' }}>
          ICC<span style={{ color: 'var(--blue)' }}>.</span>trade
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
          Decision Support v2
        </div>
      </div>

      {/* Nav links */}
      <nav style={{ padding: '12px 8px', flex: 1 }}>
        {nav.map(item => {
          const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '9px 12px',
                borderRadius: '6px',
                marginBottom: '2px',
                fontSize: '13px',
                fontWeight: active ? 500 : 400,
                color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                background: active ? 'var(--bg-tertiary)' : 'transparent',
                border: active ? '1px solid var(--border)' : '1px solid transparent',
                textDecoration: 'none',
                transition: 'all 0.15s',
              }}
            >
              <span style={{ fontSize: '14px', opacity: active ? 1 : 0.6 }}>{item.icon}</span>
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div style={{
        padding: '12px 20px',
        borderTop: '1px solid var(--border)',
        fontSize: '11px',
        color: 'var(--text-muted)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span className="live-dot" style={{
            width: '6px', height: '6px', borderRadius: '50%',
            background: 'var(--green)', display: 'inline-block',
          }} />
          Paper trading mode
        </div>
      </div>
    </aside>
  )
}
