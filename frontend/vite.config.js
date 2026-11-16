import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Настраиваем Vite Proxy для подключения к Django
export default defineConfig({
  plugins: [react()],

  server: {
    proxy: {
      // Все запросы /api отправляем на Django
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})