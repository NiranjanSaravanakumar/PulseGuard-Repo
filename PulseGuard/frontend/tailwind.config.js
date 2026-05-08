/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        pulse: {
          bg:      '#0d1117',
          surface: '#161b22',
          border:  '#30363d',
          accent:  '#58a6ff',
          success: '#3fb950',
          warning: '#d29922',
          danger:  '#f85149',
          muted:   '#8b949e',
        },
      },
      keyframes: {
        pulseBorder: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(248,81,73,0)' },
          '50%':      { boxShadow: '0 0 0 8px rgba(248,81,73,0.55)' },
        },
        bgFlash: {
          '0%, 100%': { backgroundColor: '#0d1117' },
          '50%':      { backgroundColor: '#1a0c0c' },
        },
      },
      animation: {
        'pulse-border': 'pulseBorder 1.4s ease-in-out infinite',
        'bg-flash':     'bgFlash 1.4s ease-in-out infinite',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
