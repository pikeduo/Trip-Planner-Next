"""旅行规划 LangGraph 状态定义。

LangGraph 中每个节点都通过 state 共享和传递数据。
这个模块定义了旅行规划图的状态结构，描述一次行程生成过程中会逐步累积哪些字段。

注意：这里只定义“状态长什么样”，不负责执行业务逻辑；
真正的节点执行流程在 app.graph.trip_graph 中编排。
"""

from typing import Any, List, Optional, TypedDict

from app.models.schemas import TripPlan, TripRequest


class TripGraphState(TypedDict, total=False):
    """旅行规划图在节点之间流动的共享状态。

    total=False 表示这些字段不是一开始都必须存在。
    例如图刚启动时通常只有 request；随着节点依次执行，
    attractions_raw、weather_raw、draft_plan、trip_plan 等字段才会逐步写入。
    """

    # 用户提交的旅行规划请求，是整个图的输入源。
    # validate_request、地图搜索节点和 LLM 生成节点都会读取它。
    request: TripRequest

    # 预留的消息列表字段，可用于保存多轮对话消息或 LangChain 消息历史。
    # 当前主流程主要通过 SystemMessage / HumanMessage 临时构造消息，因此该字段暂时不是核心路径。
    messages: List[Any]

    # 景点搜索原始结果，由 search_attractions_llm 写入，供 compose_plan_llm 打包给大模型参考。
    attractions_raw: Any

    # 天气查询原始结果，由 search_weather_llm 写入，供大模型规划每日行程时参考天气因素。
    weather_raw: Any

    # 酒店搜索原始结果，由 search_hotels_llm 写入，供大模型结合住宿偏好生成行程建议。
    hotels_raw: Any

    # LLM 首次生成的行程草稿，通常是字符串或可解析为 JSON 的文本。
    # validate_trip_plan 会读取它，提取 JSON 并用 TripPlan 模型校验。
    draft_plan: Any

    # 最终校验通过或兜底生成的旅行计划，是图执行完成后最重要的输出字段。
    trip_plan: Optional[TripPlan]

    # 流程中收集的错误信息列表。
    # 某些节点失败时不会立刻中断整个图，而是把错误写入这里，让后续节点继续尝试兜底。
    errors: List[str]
