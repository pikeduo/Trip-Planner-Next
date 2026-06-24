import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// Vite 前端工程配置。
// 这里集中配置 Vue 插件、环境变量目录、源码路径别名和本地开发代理。
// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 按当前运行模式读取 frontend 目录下的 VITE_ 环境变量，供开发代理等配置使用。
  const env = loadEnv(mode, __dirname, 'VITE_')

  return {
    // 指定前端环境变量文件所在目录，适合前后端放在同一个仓库中的项目结构。
    envDir: __dirname,

    // 启用 Vue 插件，让 Vite 可以编译 .vue 单文件组件。
    plugins: [vue()],

    resolve: {
      alias: {
        // 将 @ 映射到 src 目录，业务代码可以用 @/xxx 引用源码文件。
        '@': resolve(__dirname, 'src')
      }
    },

    server: {
      // 前端本地开发服务器端口。
      port: 5173,
      proxy: {
        // 开发环境下把 /api 开头的请求转发到后端服务，方便前后端联调。
        '/api': {
          // 优先使用环境变量中的后端地址；未配置时默认连接本地 FastAPI 服务。
          target: env.VITE_API_BASE_URL || 'http://localhost:8000',
          // 调整代理请求来源信息，提升本地代理转发的兼容性。
          changeOrigin: true
        }
      }
    }
  }
})
