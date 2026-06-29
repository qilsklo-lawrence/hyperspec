import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  server: {
    proxy: {
      '/upload': 'http://127.0.0.1:8080',
      '/datasets': 'http://127.0.0.1:8080',
      '/api': 'http://127.0.0.1:8080'
    }
  }
})
