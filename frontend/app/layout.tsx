import type { Metadata } from 'next'
import './globals.css'
import { Sidebar } from '@/components/layout/Sidebar'

export const metadata: Metadata = {
  title: 'ICC Trading Assistant',
  description: 'Futures decision-support platform — Indication, Correction, Continuation',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
        <div style={{ display: 'flex', minHeight: '100vh' }}>
          <Sidebar />
          <main style={{
            flex: 1,
            marginLeft: '220px',
            padding: '24px',
            minHeight: '100vh',
            background: 'var(--bg-primary)',
          }}>
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}
