# Trip Planner Next

基于 LangGraph + MCP 的智能旅行规划应用。后端使用 FastAPI、LangGraph 编排旅行规划流程，通过高德 MCP 服务获取外部数据，并用 Pydantic 校验最终行程结构。前端使用 Vue 3 + TypeScript + Vite + Ant Design Vue。

## 功能

- 生成多日旅行计划
- 通过高德 MCP 获取 POI、天气、路线和 POI 详情，MCP 不可用时部分能力会尝试高德 REST API 兜底
- 用 LLM 节点整合景点、酒店、天气和用户偏好
- 用 Pydantic 校验 `TripPlan`
- 结果页展示地图、预算、每日行程、天气、酒店和餐饮
- 支持结果页本地编辑、导出图片和 PDF
- 后端和前端启动时会覆盖写入本次运行日志，便于排查问题

## 后端启动

```bash
cd backend
conda create -n trip-planner-next python=3.11
conda activate trip-planner-next
pip install -r requirements.txt
copy .env.example .env
python run.py
```

后端运行配置文件是 `backend/.env`，可参考 `backend/.env.example`。常用配置项:

- `AMAP_API_KEY`
- `AMAP_MAPS_API_KEY`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL_ID`
- `LLM_TIMEOUT`
- `HOST`
- `PORT`

高德 MCP 服务由 `amap-mcp-server` 提供，当前后端会使用 stdio 模式启动，例如:

```text
amap-mcp-server stdio
```

后端日志文件:

- `backend/runtime.log`

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端运行配置文件是 `frontend/.env`，可参考 `frontend/.env.example`。常用配置项:

- `VITE_API_BASE_URL`
- `VITE_AMAP_WEB_JS_KEY`
- `VITE_AMAP_SECURITY_JS_CODE`

前端日志文件:

- `frontend/runtime.log`

## 主要接口

- `POST /api/trip/plan`
- `GET /api/trip/health`
- `GET /api/map/poi`
- `GET /api/map/weather`
- `POST /api/map/route`
- `GET /api/poi/detail/{poi_id}`
- `GET /api/poi/photo`
