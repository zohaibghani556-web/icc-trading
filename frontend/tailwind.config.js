/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        // IBM Plex Mono for data / numbers — feels like a real terminal
        mono: ['IBM Plex Mono', 'monospace'],
        // Inter for UI text
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Dark terminal theme — professional trading aesthetic
        background: {
          primary: '#0d0f12',
          secondary: '#141720',
          tertiary: '#1a1e2a',
          card: '#1e2330',
          border: '#2a3045',
        },
        text: {
          primary: '#e8eaf0',
          secondary: '#8b9099',
          muted: '#555b6a',
        },
        accent: {
          blue: '#3b82f6',
          green: '#22c55e',
          red: '#ef4444',
          amber: '#f59e0b',
          purple: '#a855f7',
          cyan: '#06b6d4',
        },
        verdict: {
          valid: '#22c55e',
          watch: '#f59e0b',
          invalid: '#ef4444',
        },
      },
    },
  },
  plugins: [],
}
