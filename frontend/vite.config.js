import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 前端 dev server:端口 5173,/api 代理到后端 FastAPI(localhost:8000)
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
