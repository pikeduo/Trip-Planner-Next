"""Trip planning API routes."""

from fastapi import APIRouter, HTTPException

from app.graph.trip_graph import trip_graph
from app.core.logging_utils import log_section
from app.models.schemas import TripPlanResponse, TripRequest
from app.services.llm import llm_health
from app.services.mcp_client import mcp_health

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post("/plan", response_model=TripPlanResponse, summary="生成旅行计划")
async def plan_trip(request: TripRequest):
    try:
        log_section("📥 收到旅行规划请求:")
        print(f"   城市: {request.city}")
        print(f"   日期: {request.start_date} - {request.end_date}")
        print(f"   天数: {request.travel_days}")
        print(f"   交通: {request.transportation}")
        print(f"   住宿: {request.accommodation}")
        print(f"   偏好: {', '.join(request.preferences) if request.preferences else '无'}")
        print("\n🔄 获取旅行规划图实例...")
        result = await trip_graph.ainvoke({"request": request, "messages": [], "errors": []})
        plan = result.get("trip_plan")
        if not plan:
            raise ValueError("LangGraph 未返回旅行计划")
        message = "旅行计划生成成功"
        errors = result.get("errors") or []
        if errors:
            message += f"；部分外部数据不可用: {'; '.join(errors)}"
            print(f"⚠️ 旅行计划生成完成, 但存在 {len(errors)} 个外部数据错误:")
            for error in errors:
                print(f"   - {error}")
        print("✅ 旅行计划生成成功, 准备返回响应")
        return TripPlanResponse(success=True, message=message, data=plan)
    except Exception as exc:
        print(f"❌ 旅行计划生成失败: {exc}")
        raise HTTPException(status_code=500, detail=f"生成旅行计划失败: {exc}") from exc


@router.get("/health", summary="旅行规划服务健康检查")
async def health_check():
    mcp = await mcp_health()
    llm = llm_health()
    return {
        "status": "healthy" if mcp.get("available") and llm.get("configured") else "degraded",
        "service": "trip-planner-langgraph",
        "graph": "ready",
        "mcp": mcp,
        "llm": llm,
    }
