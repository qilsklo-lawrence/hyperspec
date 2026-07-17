import { defineConfig } from 'vite'

// Every backend route goes through the dev proxy, so under `npm run dev`
// the app only ever talks to the local Flask server on :8080.
const backend = 'http://127.0.0.1:8080'
const backendRoutes = [
  '/api',
  '/datasets',
  '/dataset',
  '/status',
  '/config',
  '/logout',
  '/import',
  '/upload_direct',
  '/generate_upload_url',
  '/process_gcs_file',
  '/update_pixel',
  '/reset_all_fits',
  '/detect_flake',
  '/rename',
  '/fit_stream',
]

export default defineConfig({
  base: './',
  server: {
    proxy: Object.fromEntries(backendRoutes.map((route) => [route, backend])),
  },
})
