# 前端协作说明

本目录是 `trip-planner-next` 的前端部分，使用 Vite/Vue 项目结构。

## 目录结构

- `src/App.vue`：前端根组件。
- `src/main.ts`：前端入口文件。
- `src/services/`：前端服务与接口调用。
- `src/types/`：TypeScript 类型定义。
- `src/views/`：页面视图。
- `index.html`：Vite HTML 入口。
- `vite.config.ts`：Vite 配置。
- `tsconfig.json`：TypeScript 配置。
- `package.json`：前端脚本和依赖声明。

## 环境配置

- 前端运行配置文件是 `frontend/.env`。
- 示例配置文件是 `frontend/.env.example`。
- 当前示例配置包含 `VITE_API_BASE_URL` 和 `VITE_AMAP_WEB_JS_KEY`。
- Vite 暴露给浏览器的变量应使用 `VITE_` 前缀。
- 不要在前端提交真实密钥；前端变量会进入浏览器运行环境。

## 开发约定

- 修改页面时优先遵循 `src/views/` 中已有组织方式。
- 修改接口调用时优先放在 `src/services/`。
- 修改类型时优先放在 `src/types/`。
- 不要把后端专用配置写入前端 `.env`。
- 避免无关格式化、依赖安装或构建产物提交。
