import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  server: {
    proxy: {
      '/upload': 'http://127.0.0.1:8080',
      '/datasets': 'http://127.0.0.1:8080',
      '/api': 'http://127.0.0.1:8080',
      '/status': 'http://127.0.0.1:8080',
      '/update_pixel': 'http://127.0.0.1:8080',
      '/reset_all_fits': 'http://127.0.0.1:8080',
      '/detect_flake': 'http://127.0.0.1:8080',
      '/rename': 'http://127.0.0.1:8080',
      '/dataset': 'http://127.0.0.1:8080',
      '/fit_stream': 'http://127.0.0.1:8080'
    }
  }
})
