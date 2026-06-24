import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// Produces ONE self-contained index.html (JS + CSS + audio all inlined as
// base64). Can be opened by double-click on any machine — no server, no
// Python/Node, no internet. Used for the "send-to-teacher" package.
export default defineConfig({
  base: './',
  plugins: [react(), viteSingleFile()],
  build: {
    outDir: 'dist_single',
    assetsInlineLimit: 100 * 1024 * 1024, // inline everything (incl. mp3)
    chunkSizeWarningLimit: 100000,
    cssCodeSplit: false,
  },
})
