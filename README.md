# Trip Planner Next

基于 LangGraph + MCP 的智能旅行规划应用。后端使用 FastAPI, LangGraph 编排旅行规划流程, 通过 MCP 调用高德服务, 并用 Pydantic 校验最终行程结构。前端使用 Vue 3 + TypeScript + Vite + Ant Design Vue。

## 功能

- 生成多日旅行计划
- 通过高德 MCP 获取 POI、天气、路线和 POI 详情
- 用 LLM 节点整合景点、酒店、天气和用户偏好
- 用 Pydantic 校验 `TripPlan`
- 结果页展示地图、预算、每日行程、天气、酒店和餐饮
- 支持结果页本地编辑、导出图片和 PDF

## 后端启动

```bash
cd backend
conda create -n trip-planner-next python=3.11
conda activate trip-planner-next
pip install -r requirements.txt
copy .env.example .env
python run.py
```

需要配置:

- `AMAP_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

需要配置:

- `VITE_API_BASE_URL`
- `VITE_AMAP_WEB_JS_KEY`

## 主要接口

- `POST /api/trip/plan`
- `GET /api/trip/health`
- `GET /api/map/poi`
- `GET /api/map/weather`
- `POST /api/map/route`
- `GET /api/poi/detail/{poi_id}`
- `GET /api/poi/photo`
