/** @type {import('tailwindcss').Config} */
// Design tokens (paper/frontend_redesign_v2_zh.md §3):
//   Element-Plus 风味的产品色板 + 品牌渐变 + 软阴影 + hover 抬升微动画。
//   primary 全段保留 50–900 是因为 Tailwind utility (`bg-primary-50` 等)
//   仍被当前页面大量引用,直接改基色会破坏所有 hover/disabled 灰阶。
//   主色 #409EFF 落到 primary-500,与 Element-Plus 默认蓝完全一致。
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  '#ecf5ff',
          100: '#d9ecff',
          200: '#a0cfff',
          300: '#79bbff',
          400: '#53a8ff',
          500: '#409EFF',
          600: '#337ecc',
          700: '#2762a4',
          800: '#1d4d83',
          900: '#163961',
        },
        success: {
          DEFAULT: '#67C23A',
          50:  '#f0f9eb',
          500: '#67C23A',
          600: '#529b2e',
        },
        warning: {
          DEFAULT: '#E6A23C',
          50:  '#fdf6ec',
          500: '#E6A23C',
          600: '#b88230',
        },
        danger: {
          DEFAULT: '#F56C6C',
          50:  '#fef0f0',
          500: '#F56C6C',
          600: '#c45656',
        },
        info: {
          DEFAULT: '#909399',
          50:  '#f4f4f5',
          500: '#909399',
          600: '#73767a',
        },
        sidebar: {
          DEFAULT: '#304156',
          hover:   '#263445',
          active:  '#409EFF',
          text:    '#bfcbd9',
          textActive: '#ffffff',
        },
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        'brand-gradient-soft': 'linear-gradient(135deg, rgba(102,126,234,0.08) 0%, rgba(118,75,162,0.08) 100%)',
      },
      boxShadow: {
        card:       '0 2px 8px rgba(0, 0, 0, 0.08)',
        'card-hover': '0 4px 16px rgba(0, 0, 0, 0.12)',
        header:     '0 2px 8px rgba(0, 0, 0, 0.15)',
      },
      transitionTimingFunction: {
        'ease-product': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
    },
  },
  plugins: [],
}
