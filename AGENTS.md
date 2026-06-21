# 项目协作说明

本仓库是 `trip-planner-next`，由后端 `backend` 和前端 `frontend` 两部分组成。

## 目录结构

- `backend/`：后端应用，主要代码位于 `backend/app/`。
- `frontend/`：前端应用，主要代码位于 `frontend/src/`。
- `README.md`：项目说明文档。

## 工作边界

- 修改后端相关内容前，先阅读 `backend/AGENTS.md`。
- 修改前端相关内容前，先阅读 `frontend/AGENTS.md`。
- 不要访问frontend/node_modules目录。
- 不要把后端和前端的配置混在一起。
- 不要提交本地密钥、令牌或真实环境变量值。

## 环境配置

- 后端使用 `backend/.env` 作为运行配置文件，可参考 `backend/.env.example`。
- 前端使用 `frontend/.env` 作为运行配置文件，可参考 `frontend/.env.example`。
- 修改配置项时，应同步检查对应的 `.env.example` 是否需要更新。
- 后端运行日志写入 `backend/runtime.log`，前端运行日志写入 `frontend/runtime.log`；每次通过项目脚本启动会覆盖上一次日志。

## 开发约定

- 保持改动聚焦在当前任务范围内。
- 避免无关重构、格式化或依赖变更。
- 新增功能时优先遵循现有目录和命名风格。
