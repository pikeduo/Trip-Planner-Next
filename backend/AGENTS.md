# 后端协作说明

本目录是 `trip-planner-next` 的后端部分。

## 目录结构

- `app/api/`：接口相关代码。
- `app/core/`：核心配置与基础能力。
- `app/graph/`：行程规划或流程编排相关代码。
- `app/models/`：数据模型。
- `app/services/`：业务服务。
- `app/utils/`：通用工具。
- `run.py`：后端启动入口。
- `requirements.txt`：Python 依赖清单。

## 环境配置

- 后端运行配置文件是 `backend/.env`。
- 示例配置文件是 `backend/.env.example`。
- 当前示例配置包含 LLM、服务监听地址、跨域来源、高德地图和 Unsplash 相关变量。
- LLM 配置使用 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_ID` 和 `LLM_TIMEOUT`。
- 高德 MCP 服务使用 `AMAP_MAPS_API_KEY`，高德 REST API 兜底可使用 `AMAP_API_KEY` 或 `AMAP_MAPS_API_KEY`。
- 不要在文档或代码中写入真实 API Key。
- 调整新增配置时，请优先保持配置读取逻辑集中在现有配置模块中。

## 运行日志与 MCP

- 后端通过 `run.py` 启动时会覆盖写入 `backend/runtime.log`。
- 高德 MCP 服务由 `amap-mcp-server` 提供，当前使用 stdio 模式启动，命令应包含 `stdio`。
- 排查 MCP 问题时，优先查看 `backend/runtime.log` 中的 MCP 启动命令、工具加载数量、工具命中情况和 REST API 兜底原因。

## 开发约定

- 修改接口、服务或模型时，先确认现有 `app/` 下的分层方式。
- 新代码应放在与职责匹配的现有目录中。
- 不要把前端 `VITE_` 配置写入后端配置。
- 不要在仓库中提交虚拟环境、缓存目录或本地运行产物。
