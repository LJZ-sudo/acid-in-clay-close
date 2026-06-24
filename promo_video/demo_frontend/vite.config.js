import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Standalone demo app for the promo video. Fully isolated under promo_video/.
// base './' => the built dist/ uses relative asset paths, so it runs from any
// folder / any static server (needed for portable, copy-to-another-PC playback).
export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    port: 5273,
    host: '127.0.0.1',
    open: false,
  },
})
