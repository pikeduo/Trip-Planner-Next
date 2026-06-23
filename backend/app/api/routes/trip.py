"""旅行规划 API 路由。

这个模块是前端调用 AI 行程规划能力的 HTTP 入口，主要负责：
1. 接收并校验 FastAPI 层面的旅行规划请求；
2. 调用已经编译好的 LangGraph 旅行规划图；
3. 从图执行结果中取出最终 TripPlan；
4. 将图中的错误信息合并到响应提示中；
5. 提供旅行规划服务的健康检查接口。

真正的行程生成流程不在这里实现，而是在 app.graph.trip_graph 中由多个节点编排完成。
"""

from fastapi import APIRouter, HTTPException

from app.graph.trip_graph import trip_graph
from app.core.logging_utils import log_section
from app.models.schemas import TripPlanResponse, TripRequest
from app.services.llm import llm_health
from app.services.mcp_client import mcp_health

# 创建旅行规划路由器。
# 该 router 通常会在 app/api/main.py 中统一挂载到 /api，最终接口前缀是 /api/trip。
router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post("/plan", response_model=TripPlanResponse, summary="生成旅行计划")
async def plan_trip(request: TripRequest):
    """生成旅行计划。

    这是前端提交旅行规划请求的核心接口。
    路由层只负责接收 TripRequest、调用 LangGraph、封装 TripPlanResponse；
    景点搜索、天气查询、酒店搜索、LLM 生成、JSON 校验和兜底行程都由 trip_graph 内部节点完成。
    """
    try:
        log_section("📥 收到旅行规划请求:")
        print(f"   城市: {request.city}")
        print(f"   日期: {request.start_date} - {request.end_date}")
        print(f"   天数: {request.travel_days}")
        print(f"   交通: {request.transportation}")
        print(f"   住宿: {request.accommodation}")
        print(f"   偏好: {', '.join(request.preferences) if request.preferences else '无'}")

        print("\n🔄 获取旅行规划图实例...")
        # 初始化 LangGraph 的输入状态。
        # request 是用户请求；messages 预留给对话消息；errors 用来收集节点执行过程中的非致命错误。
        result = await trip_graph.ainvoke({"request": request, "messages": [], "errors": []})

        # trip_graph 执行完成后，最终计划应该写入 trip_plan 字段。
        plan = result.get("trip_plan")
        if not plan:
            raise ValueError("LangGraph 未返回旅行计划")

        message = "旅行计划生成成功"
        errors = result.get("errors") or []
        if errors:
            # 某些外部数据失败不一定导致整体失败。
            # 例如天气或酒店查询失败时，图可能仍然通过 LLM 或备用行程生成可用计划。
            message += f"；部分外部数据不可用: {'; '.join(errors)}"
            print(f"⚠️ 旅行计划生成完成, 但存在 {len(errors)} 个外部数据错误:")
            for error in errors:
                print(f"   - {error}")

        print("✅ 旅行计划生成成功, 准备返回响应")
        return TripPlanResponse(success=True, message=message, data=plan)
    except Exception as exc:
        # 将内部异常转换为 HTTP 错误响应，避免 FastAPI 直接暴露未处理异常。
        print(f"❌ 旅行计划生成失败: {exc}")
        raise HTTPException(status_code=500, detail=f"生成旅行计划失败: {exc}") from exc


@router.get("/health", summary="旅行规划服务健康检查")
async def health_check():
    """检查旅行规划服务依赖是否可用。

    旅行规划依赖两类核心能力：
    1. MCP / 高德地图能力，用于获取景点、天气、酒店等外部数据；
    2. LLM 能力，用于根据请求和外部数据生成结构化行程。

    只有两者都可用时，服务才返回 healthy；否则返回 degraded，表示服务处于降级状态。
    """
    mcp = await mcp_health()
    llm = llm_health()
    return {
        "status": "healthy" if mcp.get("available") and llm.get("configured") else "degraded",
        "service": "trip-planner-langgraph",
        "graph": "ready",
        "mcp": mcp,
        "llm": llm,
    }
