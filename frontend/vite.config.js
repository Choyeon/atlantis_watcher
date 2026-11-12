import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite 配置
// 构建产物输出到 ../static/dist，由 FastAPI 通过 StaticFiles 挂载
export default defineConfig({
  plugins: [vue()],

  /*
    资源基础路径使用相对路径（'./'）：
      - FastAPI 托管：页面在 /，index.html 在 /static/dist/ 下会解析成
        /static/dist/assets/xxx.js —— 但 FastAPI 实际把 index.html 挂在 /
        故需配合下方 build.rollupOptions 的相对化处理
      - Capacitor APK：页面在 https://localhost/，解析成 /assets/xxx.js
        正好命中 assets/public/assets/ 目录

    绝不能用绝对路径 '/static/dist/'：APK 内没有这一层级，会 404 导致白屏。
  */
  base: './',

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },

  server: {
    port: 5173,
    strictPort: false,
    // 开发环境代理到 FastAPI 后端，避免跨域
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:26541',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://127.0.0.1:26541',
        ws: true
      },
      '/health': {
        target: 'http://127.0.0.1:26541',
        changeOrigin: true
      }
    }
  },

  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
    assetsDir: 'assets',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        // 手动分包，避免单个 vendor 块过大
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia']
        }
      }
    }
  }
})
