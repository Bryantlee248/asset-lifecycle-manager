/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: 'var(--canvas)',
        surface: 'var(--surface)',
        border: 'var(--border)',
        'command-bar': 'var(--command-bar)',
        'command-bar-fg': 'var(--command-bar-fg)',
        brand: 'var(--brand)',
        'brand-hover': 'var(--brand-hover)',
        link: 'var(--link)',
        'risk-critical': 'var(--risk-critical)',
        'risk-warning': 'var(--risk-warning)',
        'risk-caution': 'var(--risk-caution)',
        'risk-ok': 'var(--risk-ok)',
      },
      borderRadius: {
        panel: 'var(--radius)',
      },
      boxShadow: {
        float: 'var(--shadow)',
      },
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'system-ui', 'sans-serif'],
      },
      transitionDuration: {
        150: '150ms',
        200: '200ms',
      },
    },
  },
  plugins: [],
}
