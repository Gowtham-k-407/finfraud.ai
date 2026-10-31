/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      colors: {
        canvas: {
          light: '#F8FAFC',
          dark: '#090D16',
        },
        panel: {
          light: '#FFFFFF',
          dark: '#0F1623',
        },
        elevated: {
          light: '#F1F5F9',
          dark: '#162032',
        },
        risk: {
          critical: '#EF4444',
          high: '#F97316',
          medium: '#EAB308',
          low: '#3B82F6',
          ip: '#A855F7',
        },
      },
    },
  },
  plugins: [],
};

